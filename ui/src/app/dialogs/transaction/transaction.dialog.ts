import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectChange, MatSelectModule } from "@angular/material/select";
import { ApiClientService } from "@shared/api/api-client.service";
import {
	TransactionCategoryContract,
	TransactionCategoryResponse,
	TransactionItem,
	TransactionKeywordOption,
	TransactionKeywordResponse,
} from "@shared/api/transactions/model";
import { formatSignedCents } from "@shared/utils/money.util";

/** The bucket a rule removal is expressed through: there is no separate delete action. */
const UNCATEGORIZED_CATEGORY = "Uncategorized";

export interface TransactionDialogData {
	transaction: TransactionItem;
	categories: string[];
}

@Component({
	selector: "penniless-transaction-dialog",
	imports: [MatButtonModule, MatDialogModule, MatFormFieldModule, MatSelectModule],
	templateUrl: "./transaction.dialog.html",
	styleUrl: "./transaction.dialog.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TransactionDialog implements OnInit {
	private readonly apiClient = inject(ApiClientService);
	private readonly dialogRef = inject(MatDialogRef<TransactionDialog>);
	protected readonly data: TransactionDialogData = inject(MAT_DIALOG_DATA);

	protected readonly options = signal<TransactionKeywordOption[]>([]);
	protected readonly optionsLoading = signal(true);
	protected readonly optionsFailed = signal(false);
	protected readonly selected = signal<TransactionKeywordOption | null>(null);
	protected readonly selectedCategory = signal(this.data.transaction.category);
	protected readonly loading = signal(false);
	protected readonly amountLabel = formatSignedCents(this.data.transaction.amountCents);

	/** The rule for this description as written, which outranks every keyword it also matches. */
	private readonly exactRule = computed(() => this.options().find((option) => option.matchType === "exact" && option.category !== null) ?? null);

	private readonly isDelete = computed(() => this.selectedCategory() === UNCATEGORIZED_CATEGORY);

	/** The selected keyword cannot take effect, so the note has to name the rule that outranks it. */
	private readonly isShadowed = computed(() => {
		const selected = this.selected();
		const exactRule = this.exactRule();

		return (
			!this.isDelete() &&
			selected !== null &&
			selected.matchType === "contains" &&
			exactRule !== null &&
			exactRule.category !== this.selectedCategory()
		);
	});

	/**
	 * Why Save is unavailable, or `null` when nothing needs explaining. A disabled Save with no note is
	 * the default when the selection has nothing to do; only a keyword shadowed by an exact rule
	 * looks like it should have worked, so only that one - and a failed load - gets a line.
	 */
	protected readonly saveReason = computed<string | null>(() => {
		if (this.optionsFailed()) {
			return "Keywords could not be loaded, so nothing can be saved here.";
		}

		const exactRule = this.exactRule();

		if (this.isShadowed() && exactRule !== null) {
			return `${exactRule.pattern} has its own description rule at ${exactRule.category}; change that one instead.`;
		}

		return null;
	});

	protected readonly canSave = computed(() => {
		if (this.optionsLoading() || this.optionsFailed() || this.loading()) {
			return false;
		}

		const selected = this.selected();

		if (selected === null) {
			return false;
		}

		if (this.isDelete()) {
			// `Uncategorized` means "delete this keyword's rule", so there has to be a rule.
			return selected.category !== null;
		}

		return selected.category !== this.selectedCategory() && !this.isShadowed();
	});

	ngOnInit(): void {
		this.loadKeywordOptions();
	}

	protected onKeywordChange(event: MatSelectChange): void {
		this.selected.set(event.value as TransactionKeywordOption);
	}

	protected onCategoryChange(event: MatSelectChange): void {
		this.selectedCategory.set(event.value as string);
	}

	/** Material compares select values by identity; options are rebuilt on every open. */
	protected compareOptions(first: TransactionKeywordOption | null, second: TransactionKeywordOption | null): boolean {
		return first?.matchType === second?.matchType && first?.pattern === second?.pattern;
	}

	protected optionLabel(option: TransactionKeywordOption): string {
		const transactions = `${option.matched} transaction${option.matched === 1 ? "" : "s"}`;

		return option.category === null ? `${option.pattern} · ${transactions}` : `${option.pattern} · ${transactions} · ${option.category}`;
	}

	protected save(): void {
		const selected = this.selected();

		if (!this.canSave() || selected === null) {
			return;
		}

		const transaction = this.data.transaction;
		const contract: TransactionCategoryContract = {
			connectionId: transaction.connectionId,
			accountId: transaction.accountId,
			transactionId: transaction.transactionId,
			matchType: selected.matchType,
			pattern: selected.pattern,
			category: this.selectedCategory(),
		};

		this.loading.set(true);

		this.apiClient.transactions.standard.assignCategory(contract).subscribe({
			next: (response) => {
				this.loading.set(false);
				this.dialogRef.close(response);
			},
			// The error interceptor has already shown the message. The dialog stays open with the selection
			// intact so the save can be retried.
			error: () => this.loading.set(false),
		});
	}

	private loadKeywordOptions(): void {
		const transaction = this.data.transaction;

		this.apiClient.transactions.standard
			.getKeywordOptions({
				connectionId: transaction.connectionId,
				accountId: transaction.accountId,
				transactionId: transaction.transactionId,
			})
			.subscribe({
				next: (response) => {
					this.options.set(response.options);
					this.selected.set(this.initialOption(response));
					this.optionsLoading.set(false);
				},
				error: () => {
					this.optionsFailed.set(true);
					this.optionsLoading.set(false);
				},
			});
	}

	/** Open on the rule that decides the row, or on the whole description when nothing matches it. */
	private initialOption(response: TransactionKeywordResponse): TransactionKeywordOption | null {
		const effectiveRule = response.effectiveRule;

		if (effectiveRule !== null) {
			return response.options.find((option) => option.matchType === effectiveRule.matchType && option.pattern === effectiveRule.pattern) ?? null;
		}

		return response.options.find((option) => option.source === "description") ?? null;
	}
}

export type TransactionDialogResult = TransactionCategoryResponse;
