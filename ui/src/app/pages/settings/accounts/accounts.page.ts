import {
	ChangeDetectionStrategy,
	Component,
	DestroyRef,
	ElementRef,
	OnDestroy,
	OnInit,
	ViewEncapsulation,
	afterRenderEffect,
	computed,
	inject,
	signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { ReactiveFormsModule } from "@angular/forms";
import { MatAutocompleteModule, MatAutocompleteSelectedEvent } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MatDialog } from "@angular/material/dialog";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatSnackBar } from "@angular/material/snack-bar";
import { ActivatedRoute, ParamMap, Router, RouterLink } from "@angular/router";
import { AccountDialog } from "@app/dialogs/account/account.dialog";
import { ConfirmDialog } from "@app/dialogs/confirm/confirm.dialog";
import { AccountResponse, accountKey, accountKeyOf, isManualAccount, resolvedAccountName } from "@shared/api/accounts/model";
import { MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH } from "@shared/api/accounts/standard";
import { ApiClientService } from "@shared/api/api-client.service";
import { AccountDialogData, AccountDialogResult } from "@shared/interfaces/account.interface";
import { ConfirmDialogData } from "@shared/interfaces/confirm.interface";
import { formatCents } from "@shared/utils/money.util";
import { AccountsPageService } from "./accounts.service";

const SNACKBAR_DURATION_MS = 4_000;

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
	private readonly router = inject(Router);
	private readonly dialog = inject(MatDialog);
	private readonly snackBar = inject(MatSnackBar);
	private readonly apiClient = inject(ApiClientService);
	private readonly destroyRef = inject(DestroyRef);
	private readonly hostElement = inject<ElementRef<HTMLElement>>(ElementRef);
	private hasScrolledToDeepLink = false;

	protected readonly service = inject(AccountsPageService);
	protected readonly accountName = resolvedAccountName;
	protected readonly accountKey = accountKey;
	protected readonly isManualAccount = isManualAccount;
	protected readonly accountBalance = (account: AccountResponse): string => formatCents(account.balanceCents, account.currency);
	protected readonly maximumDescriptionLength = MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH;

	private readonly expandedKeys = signal<ReadonlySet<string>>(new Set());
	private readonly deepLinkKey = signal<string | null>(null);

	/** A deep link opens its own panel once per key, and only scrolls to it once its row has rendered. */
	private readonly scrollToDeepLinkedPanel = afterRenderEffect(() => {
		const key = this.deepLinkKey();

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
		// The router reuses this component when only the key in the address changes, which is what a created
		// cash account navigates to, so the panel and the list are re-read on every key rather than once.
		this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
			const key = deepLinkedAccountKey(params);

			this.deepLinkKey.set(key);
			this.hasScrolledToDeepLink = false;

			if (key !== null) {
				this.expandedKeys.update((keys) => new Set(keys).add(key));
			}

			this.service.load();
		});
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

	protected onCreate(): void {
		const data: AccountDialogData = { labelVocabulary: this.service.accounts().flatMap((account) => account.labels) };
		const dialogRef = this.dialog.open(AccountDialog, { width: "30rem", data });

		dialogRef.afterClosed().subscribe((result: AccountDialogResult | undefined) => {
			if (!result) {
				return;
			}

			const created = result.account;

			this.snackBar.open(`${resolvedAccountName(created)} created`, undefined, { duration: SNACKBAR_DURATION_MS });
			// The key in the address is what opens and scrolls to the new panel, on a fresh mount or a reused one.
			void this.router.navigate(["/settings/accounts", created.connectionId, created.accountId]);
		});
	}

	protected onDelete(account: AccountResponse): void {
		const name = resolvedAccountName(account);
		const data: ConfirmDialogData = {
			title: "Delete cash account",
			message: `Delete ${name}? It is the only record of this money, and nothing can restore it.`,
			confirmLabel: "Delete account",
			destructive: true,
		};
		const dialogRef = this.dialog.open(ConfirmDialog, { width: "30rem", data });

		dialogRef.afterClosed().subscribe((confirmed: boolean | undefined) => {
			if (!confirmed) {
				return;
			}

			this.apiClient.accounts.standard.deleteAccount(account.connectionId, account.accountId).subscribe({
				next: (accounts) => {
					this.service.setAccounts(accounts);
					this.snackBar.open(`${name} deleted`, undefined, { duration: SNACKBAR_DURATION_MS });

					if (this.deepLinkKey() === accountKey(account)) {
						void this.router.navigate(["/settings/accounts"]);
					}
				},
				error: () => undefined,
			});
		});
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
