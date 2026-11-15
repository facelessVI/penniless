import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, ViewEncapsulation, computed, inject, signal } from "@angular/core";
import { ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { RouterLink } from "@angular/router";
import { AccountResponse, accountKey, resolvedAccountName } from "@shared/api/accounts/model";
import { MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH } from "@shared/api/accounts/standard";
import { AccountsPageService } from "./accounts.service";

@Component({
	selector: "penniless-settings-accounts",
	imports: [ReactiveFormsModule, RouterLink, MatButtonModule, MatExpansionModule, MatFormFieldModule, MatInputModule],
	templateUrl: "./accounts.page.html",
	styleUrl: "./accounts.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SettingsAccountsPage implements OnInit, OnDestroy {
	protected readonly service = inject(AccountsPageService);
	protected readonly accountName = resolvedAccountName;
	protected readonly accountKey = accountKey;
	protected readonly maximumDescriptionLength = MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH;

	private readonly expandedKeys = signal<ReadonlySet<string>>(new Set());

	protected readonly allExpanded = computed(() => {
		const accounts = this.service.accounts();
		const expanded = this.expandedKeys();

		return accounts.length > 0 && accounts.every((account) => expanded.has(accountKey(account)));
	});

	protected readonly toggleAllLabel = computed(() => (this.allExpanded() ? "Collapse all" : "Expand all"));

	ngOnInit(): void {
		this.service.load();
	}

	ngOnDestroy(): void {
		this.service.reset();
	}

	protected isExpanded(account: AccountResponse): boolean {
		return this.expandedKeys().has(accountKey(account));
	}

	protected setExpanded(account: AccountResponse, expanded: boolean): void {
		this.expandedKeys.update((keys) => {
			const next = new Set(keys);

			if (expanded) {
				next.add(accountKey(account));
			} else {
				next.delete(accountKey(account));
			}

			return next;
		});
	}

	protected toggleAll(): void {
		this.expandedKeys.set(this.allExpanded() ? new Set() : new Set(this.service.accounts().map(accountKey)));
	}

	protected canSave(account: AccountResponse): boolean {
		const form = this.service.formFor(account);

		return form.valid && this.service.hasChanges(account) && !this.service.isSaving(account);
	}

	protected onSave(account: AccountResponse): void {
		if (!this.canSave(account)) {
			return;
		}

		this.service.save(account);
	}
}
