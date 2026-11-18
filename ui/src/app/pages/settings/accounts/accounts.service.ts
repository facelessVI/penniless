import { Injectable, inject, signal } from "@angular/core";
import { AbstractControl, FormControl, FormGroup, ValidationErrors, Validators } from "@angular/forms";
import { AccountResponse, AccountUpdateContract, accountKey, isManualAccount } from "@shared/api/accounts/model";
import { MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH } from "@shared/api/accounts/standard";
import { ApiClientService } from "@shared/api/api-client.service";
import { LabelOption, labelOptions } from "@shared/utils/label.util";
import { centsToInput, parseCents } from "@shared/utils/money.util";

export interface AccountFormValue {
	displayName: string;
	description: string;
	/** The balance as typed: plain digits to two decimals, edited only on an account the user created. */
	balance: string;
}

export type AccountForm = FormGroup<{
	displayName: FormControl<string>;
	description: FormControl<string>;
	balance: FormControl<string>;
}>;

function money(control: AbstractControl<string>): ValidationErrors | null {
	return parseCents(control.value) === null ? { money: true } : null;
}

const toFormValue = (account: AccountResponse): AccountFormValue => ({
	displayName: account.displayName ?? "",
	description: account.description ?? "",
	balance: centsToInput(account.balanceCents),
});

const toForm = (account: AccountResponse): AccountForm => {
	const value = toFormValue(account);

	return new FormGroup({
		displayName: new FormControl(value.displayName, { nonNullable: true }),
		description: new FormControl(value.description, {
			nonNullable: true,
			validators: [Validators.maxLength(MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH)],
		}),
		balance: new FormControl(value.balance, { nonNullable: true, validators: [money] }),
	});
};

@Injectable({ providedIn: "root" })
export class AccountsPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly forms = new Map<string, AccountForm>();
	private readonly labelInputs = new Map<string, FormControl<string>>();

	readonly accounts = signal<AccountResponse[]>([]);
	readonly loading = signal(true);
	/** The account whose form save is in flight, so only that panel's Save button is disabled. */
	readonly savingKey = signal<string | null>(null);
	/** The accounts whose immediate write is in flight, so only their own switches wait. */
	readonly writingKeys = signal<ReadonlySet<string>>(new Set());

	load(): void {
		this.loading.set(true);

		this.apiClient.accounts.standard.getAccounts().subscribe({
			next: (accounts) => {
				this.setAccounts(accounts);
				this.loading.set(false);
			},
			error: () => this.loading.set(false),
		});
	}

	/** Replace the list and rebuild every form, so a saved or removed account has no stale draft left behind. */
	setAccounts(accounts: AccountResponse[]): void {
		this.accounts.set(accounts);
		this.forms.clear();
		this.labelInputs.clear();
		accounts.forEach((account) => this.forms.set(accountKey(account), toForm(account)));
	}

	formFor(account: AccountResponse): AccountForm {
		const key = accountKey(account);
		const stored = this.forms.get(key);

		if (stored !== undefined) {
			return stored;
		}

		const created = toForm(account);
		this.forms.set(key, created);

		return created;
	}

	hasChanges(account: AccountResponse): boolean {
		const value = this.formFor(account).getRawValue();
		const loaded = toFormValue(account);

		return value.displayName !== loaded.displayName || value.description !== loaded.description || value.balance !== loaded.balance;
	}

	isSaving(account: AccountResponse): boolean {
		return this.savingKey() === accountKey(account);
	}

	labelInputFor(account: AccountResponse): FormControl<string> {
		const key = accountKey(account);
		const stored = this.labelInputs.get(key);

		if (stored !== undefined) {
			return stored;
		}

		const created = new FormControl("", { nonNullable: true });
		this.labelInputs.set(key, created);

		return created;
	}

	/**
	 * The vocabulary this account can attach from: every label in use minus the ones it already
	 * carries. An unknown typed name becomes a create row, so one selection does both steps.
	 */
	labelOptionsFor(account: AccountResponse): LabelOption[] {
		const vocabulary = this.accounts().flatMap((candidate) => candidate.labels);

		return labelOptions(vocabulary, account.labels, this.labelInputFor(account).value);
	}

	isWriting(account: AccountResponse): boolean {
		return this.writingKeys().has(accountKey(account));
	}

	attachLabel(account: AccountResponse, name: string): void {
		const trimmed = name.trim();

		if (trimmed === "" || this.isWriting(account)) {
			return;
		}

		this.writeLabels(account, [...account.labels, trimmed]);
	}

	detachLabel(account: AccountResponse, label: string): void {
		if (this.isWriting(account)) {
			return;
		}

		this.writeLabels(
			account,
			account.labels.filter((candidate) => candidate !== label),
		);
	}

	setIncludeInCash(account: AccountResponse, includeInCash: boolean): void {
		if (this.isWriting(account)) {
			return;
		}

		const key = accountKey(account);

		this.setWriting(key, true);

		this.apiClient.accounts.standard.updateAccount(account.connectionId, account.accountId, { includeInCash }).subscribe({
			next: (updated) => {
				this.replaceAccount(updated);
				this.setWriting(key, false);
			},
			// The banner has already reported it; the switch keeps what the user picked, so a retry is one more click.
			error: () => this.setWriting(key, false),
		});
	}

	save(account: AccountResponse): void {
		const form = this.formFor(account);
		const value = form.getRawValue();
		const balanceCents = parseCents(value.balance);
		const contract: AccountUpdateContract = { displayName: value.displayName, description: value.description };

		// Only a cash account's balance is the user's to write; the API refuses the field on any other.
		if (isManualAccount(account) && balanceCents !== null) {
			contract.balanceCents = balanceCents;
		}

		this.savingKey.set(accountKey(account));

		this.apiClient.accounts.standard.updateAccount(account.connectionId, account.accountId, contract).subscribe({
			next: (updated) => {
				this.replaceAccount(updated);
				form.setValue(toFormValue(updated));
				this.savingKey.set(null);
			},
			// The banner has already reported it, and the typed values stay in the form so the save can be retried.
			error: () => this.savingKey.set(null),
		});
	}

	reset(): void {
		this.accounts.set([]);
		this.forms.clear();
		this.labelInputs.clear();
		this.savingKey.set(null);
		this.writingKeys.set(new Set());
		this.loading.set(true);
	}

	private writeLabels(account: AccountResponse, labels: string[]): void {
		const key = accountKey(account);

		this.setWriting(key, true);

		this.apiClient.accounts.standard.updateAccount(account.connectionId, account.accountId, { labels }).subscribe({
			next: (updated) => {
				this.replaceAccount(updated);
				this.labelInputFor(updated).setValue("");
				this.setWriting(key, false);
			},
			// The banner has already reported it, and the panel keeps the labels it had.
			error: () => this.setWriting(key, false),
		});
	}

	private replaceAccount(updated: AccountResponse): void {
		this.accounts.update((accounts) => accounts.map((candidate) => (accountKey(candidate) === accountKey(updated) ? updated : candidate)));
	}

	private setWriting(key: string, writing: boolean): void {
		this.writingKeys.update((keys) => {
			const next = new Set(keys);

			if (writing) {
				next.add(key);
			} else {
				next.delete(key);
			}

			return next;
		});
	}
}
