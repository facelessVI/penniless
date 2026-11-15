import { Injectable, inject, signal } from "@angular/core";
import { FormControl, FormGroup, Validators } from "@angular/forms";
import { AccountResponse, AccountUpdateContract, accountKey } from "@shared/api/accounts/model";
import { MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH } from "@shared/api/accounts/standard";
import { ApiClientService } from "@shared/api/api-client.service";

export interface AccountFormValue {
	displayName: string;
	description: string;
}

export type AccountForm = FormGroup<{
	displayName: FormControl<string>;
	description: FormControl<string>;
}>;

/** One autocomplete row: a vocabulary label, or the name the user is about to create. */
export interface LabelOption {
	value: string;
	create: boolean;
}

const toFormValue = (account: AccountResponse): AccountFormValue => ({
	displayName: account.displayName ?? "",
	description: account.description ?? "",
});

const toForm = (account: AccountResponse): AccountForm => {
	const value = toFormValue(account);

	return new FormGroup({
		displayName: new FormControl(value.displayName, { nonNullable: true }),
		description: new FormControl(value.description, {
			nonNullable: true,
			validators: [Validators.maxLength(MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH)],
		}),
	});
};

@Injectable({ providedIn: "root" })
export class AccountsPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly forms = new Map<string, AccountForm>();
	private readonly labelInputs = new Map<string, FormControl<string>>();

	readonly accounts = signal<AccountResponse[]>([]);
	readonly loading = signal(true);
	/** The account whose save is in flight, so only that panel's Save button is disabled. */
	readonly savingKey = signal<string | null>(null);
	/** The accounts whose label write is in flight, so only their own chip controls wait. */
	readonly labelsBusyKeys = signal<ReadonlySet<string>>(new Set());

	load(): void {
		this.loading.set(true);

		this.apiClient.accounts.standard.getAccounts().subscribe({
			next: (accounts) => {
				this.accounts.set(accounts);
				this.forms.clear();
				this.labelInputs.clear();
				accounts.forEach((account) => this.forms.set(accountKey(account), toForm(account)));
				this.loading.set(false);
			},
			error: () => this.loading.set(false),
		});
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

		return value.displayName !== loaded.displayName || value.description !== loaded.description;
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
		const typed = this.labelInputFor(account).value.trim().toLowerCase();
		const attached = new Set(account.labels.map((label) => label.toLowerCase()));
		const vocabulary = new Map<string, string>();

		for (const candidate of this.accounts()) {
			for (const label of candidate.labels) {
				const key = label.toLowerCase();

				if (!vocabulary.has(key)) {
					vocabulary.set(key, label);
				}
			}
		}

		if (typed === "") {
			return [];
		}

		const matching = [...vocabulary.entries()].filter(([key]) => key.includes(typed)).sort(([first], [second]) => first.localeCompare(second));

		if (matching.length === 0) {
			return [{ value: this.labelInputFor(account).value.trim(), create: true }];
		}

		return matching.filter(([key]) => !attached.has(key)).map(([, label]) => ({ value: label, create: false }));
	}

	isSavingLabels(account: AccountResponse): boolean {
		return this.labelsBusyKeys().has(accountKey(account));
	}

	attachLabel(account: AccountResponse, name: string): void {
		const trimmed = name.trim();

		if (trimmed === "" || this.isSavingLabels(account)) {
			return;
		}

		this.writeLabels(account, [...account.labels, trimmed]);
	}

	detachLabel(account: AccountResponse, label: string): void {
		if (this.isSavingLabels(account)) {
			return;
		}

		this.writeLabels(
			account,
			account.labels.filter((candidate) => candidate !== label),
		);
	}

	save(account: AccountResponse): void {
		const form = this.formFor(account);
		const value = form.getRawValue();
		const contract: AccountUpdateContract = { displayName: value.displayName, description: value.description };

		this.savingKey.set(accountKey(account));

		this.apiClient.accounts.standard.updateAccount(account.connectionId, account.accountId, contract).subscribe({
			next: (updated) => {
				this.accounts.update((accounts) => accounts.map((candidate) => (accountKey(candidate) === accountKey(updated) ? updated : candidate)));
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
		this.labelsBusyKeys.set(new Set());
		this.loading.set(true);
	}

	private writeLabels(account: AccountResponse, labels: string[]): void {
		const key = accountKey(account);

		this.setLabelsBusy(key, true);

		this.apiClient.accounts.standard.updateAccount(account.connectionId, account.accountId, { labels }).subscribe({
			next: (updated) => {
				this.accounts.update((accounts) => accounts.map((candidate) => (accountKey(candidate) === accountKey(updated) ? updated : candidate)));
				this.labelInputFor(updated).setValue("");
				this.setLabelsBusy(key, false);
			},
			// The banner has already reported it, and the panel keeps the labels it had.
			error: () => this.setLabelsBusy(key, false),
		});
	}

	private setLabelsBusy(key: string, busy: boolean): void {
		this.labelsBusyKeys.update((keys) => {
			const next = new Set(keys);

			if (busy) {
				next.add(key);
			} else {
				next.delete(key);
			}

			return next;
		});
	}
}
