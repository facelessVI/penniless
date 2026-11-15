import {
	ChangeDetectionStrategy,
	Component,
	ElementRef,
	OnDestroy,
	OnInit,
	ViewEncapsulation,
	afterRenderEffect,
	computed,
	inject,
	signal,
} from "@angular/core";
import { ReactiveFormsModule } from "@angular/forms";
import { MatAutocompleteModule, MatAutocompleteSelectedEvent } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { ActivatedRoute, ParamMap, RouterLink } from "@angular/router";
import { AccountResponse, accountKey, accountKeyOf, resolvedAccountName } from "@shared/api/accounts/model";
import { MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH } from "@shared/api/accounts/standard";
import { AccountsPageService } from "./accounts.service";

const deepLinkedAccountKey = (params: ParamMap): string | null => {
	const connectionId = params.get("connectionId");
	const accountId = params.get("accountId");

	return connectionId === null || accountId === null ? null : accountKeyOf(connectionId, accountId);
};

@Component({
	selector: "penniless-settings-accounts",
	imports: [
		ReactiveFormsModule,
		RouterLink,
		MatAutocompleteModule,
		MatButtonModule,
		MatExpansionModule,
		MatFormFieldModule,
		MatInputModule,
		MatSlideToggleModule,
	],
	templateUrl: "./accounts.page.html",
	styleUrl: "./accounts.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SettingsAccountsPage implements OnInit, OnDestroy {
	private readonly route = inject(ActivatedRoute);
	private readonly hostElement = inject<ElementRef<HTMLElement>>(ElementRef);
	private readonly deepLinkKey = deepLinkedAccountKey(this.route.snapshot.paramMap);
	private hasScrolledToDeepLink = false;

	protected readonly service = inject(AccountsPageService);
	protected readonly accountName = resolvedAccountName;
	protected readonly accountKey = accountKey;
	protected readonly maximumDescriptionLength = MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH;

	private readonly expandedKeys = signal<ReadonlySet<string>>(new Set());

	/** A deep link opens its own panel once, and only scrolls to it the first time the list arrives. */
	private readonly scrollToDeepLinkedPanel = afterRenderEffect(() => {
		const key = this.deepLinkKey;

		if (key === null || this.hasScrolledToDeepLink || this.service.accounts().length === 0) {
			return;
		}

		this.hasScrolledToDeepLink = true;
		this.hostElement.nativeElement.querySelector<HTMLElement>(`[data-account-key="${key}"]`)?.scrollIntoView({ block: "start" });
	});

	protected readonly allExpanded = computed(() => {
		const accounts = this.service.accounts();
		const expanded = this.expandedKeys();

		return accounts.length > 0 && accounts.every((account) => expanded.has(accountKey(account)));
	});

	protected readonly toggleAllLabel = computed(() => (this.allExpanded() ? "Collapse all" : "Expand all"));

	ngOnInit(): void {
		if (this.deepLinkKey !== null) {
			this.expandedKeys.set(new Set([this.deepLinkKey]));
		}

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

	protected onLabelSelected(account: AccountResponse, event: MatAutocompleteSelectedEvent): void {
		this.service.attachLabel(account, String(event.option.value));
	}

	protected onDetachLabel(account: AccountResponse, label: string): void {
		this.service.detachLabel(account, label);
	}

	protected onCashToggle(account: AccountResponse, includeInCash: boolean): void {
		this.service.setIncludeInCash(account, includeInCash);
	}
}
