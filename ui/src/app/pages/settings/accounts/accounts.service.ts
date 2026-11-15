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

	readonly accounts = signal<AccountResponse[]>([]);
	readonly loading = signal(true);
	/** The account whose save is in flight, so only that panel's Save button is disabled. */
	readonly savingKey = signal<string | null>(null);

	load(): void {
		this.loading.set(true);

		this.apiClient.accounts.standard.getAccounts().subscribe({
			next: (accounts) => {
				this.accounts.set(accounts);
				this.forms.clear();
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
		this.savingKey.set(null);
		this.loading.set(true);
	}
}
