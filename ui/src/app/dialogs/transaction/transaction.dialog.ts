import { ChangeDetectionStrategy, Component, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectChange, MatSelectModule } from "@angular/material/select";
import { ApiClientService } from "@shared/api/api-client.service";
import { TransactionCategoryContract, TransactionCategoryResponse, TransactionItem } from "@shared/api/transactions/model";
import { formatSignedCents } from "@shared/utils/money.util";

export interface TransactionDialogData {
	transaction: TransactionItem;
	categories: string[];
}

/** One transaction's details plus the category select that teaches its description a category. */
@Component({
	selector: "penniless-transaction-dialog",
	imports: [MatButtonModule, MatDialogModule, MatFormFieldModule, MatSelectModule],
	templateUrl: "./transaction.dialog.html",
	styleUrl: "./transaction.dialog.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TransactionDialog {
	private readonly apiClient = inject(ApiClientService);
	private readonly dialogRef = inject(MatDialogRef<TransactionDialog>);
	protected readonly data: TransactionDialogData = inject(MAT_DIALOG_DATA);

	protected readonly loading = signal(false);
	protected readonly selectedCategory = signal(this.data.transaction.category);
	protected readonly amountLabel = formatSignedCents(this.data.transaction.amount_cents);
	protected readonly isUnchanged = computed(() => this.selectedCategory() === this.data.transaction.category);

	protected onCategoryChange(event: MatSelectChange): void {
		this.selectedCategory.set(event.value as string);
	}

	protected save(): void {
		if (this.loading() || this.isUnchanged()) {
			return;
		}

		const transaction = this.data.transaction;
		const contract: TransactionCategoryContract = {
			connection_id: transaction.connection_id,
			account_id: transaction.account_id,
			transaction_id: transaction.transaction_id,
			category: this.selectedCategory(),
		};

		this.loading.set(true);

		this.apiClient.transactions.standard.assignCategory(contract).subscribe({
			next: (response) => {
				this.loading.set(false);
				this.dialogRef.close(response);
			},
			// The interceptor has already shown the message. The dialog stays open with the selection
			// intact so the save can be retried.
			error: () => this.loading.set(false),
		});
	}
}

export type TransactionDialogResult = TransactionCategoryResponse;
