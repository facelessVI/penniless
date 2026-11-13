import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, ViewEncapsulation, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatDialog } from "@angular/material/dialog";
import { MatSnackBar } from "@angular/material/snack-bar";
import { MatTableModule } from "@angular/material/table";
import { ApiClientService } from "@shared/api/api-client.service";
import { CategoryDeleteResponse, CategoryItem } from "@shared/api/categories/model";
import { CategoryDialog } from "@app/dialogs/category/category.dialog";
import { ConfirmDialog } from "@app/dialogs/confirm/confirm.dialog";
import { CategoriesPageService } from "./categories.service";
import { CategoryDialogData, CategoryDialogResult } from "@app/shared/interfaces/category.interface";
import { ConfirmDialogData } from "@app/shared/interfaces/confirm.interface";

const SNACKBAR_DURATION_MS = 4_000;

/** `1 transaction`, `4 transactions`: the noun agrees with the count. */
const pluralize = (count: number, noun: string): string => `${count} ${noun}${count === 1 ? "" : "s"}`;

@Component({
	selector: "penniless-settings-categories",
	imports: [MatButtonModule, MatTableModule],
	templateUrl: "./categories.page.html",
	styleUrl: "./categories.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SettingsCategoriesPage implements OnInit, OnDestroy {
	private readonly dialog = inject(MatDialog);
	private readonly snackBar = inject(MatSnackBar);
	private readonly apiClient = inject(ApiClientService);

	protected readonly service = inject(CategoriesPageService);
	protected readonly columns = ["name", "transactions", "rules", "actions"];

	ngOnInit(): void {
		this.service.load();
	}

	ngOnDestroy(): void {
		this.service.reset();
	}

	protected onCreate(): void {
		const dialogWidth = "26rem";
		const data: CategoryDialogData = { mode: "create", name: "" };
		const dialogRef = this.dialog.open(CategoryDialog, { width: dialogWidth, data });

		dialogRef.afterClosed().subscribe((result: CategoryDialogResult | undefined) => {
			if (!result) {
				return;
			}

			this.service.setCategories(result.response);
			this.snackBar.open(`Category ${result.name} created`, undefined, { duration: SNACKBAR_DURATION_MS });
		});
	}

	protected onRename(category: CategoryItem): void {
		const dialogWidth = "26rem";
		const data: CategoryDialogData = { mode: "rename", name: category.name };
		const dialogRef = this.dialog.open(CategoryDialog, { width: dialogWidth, data });

		dialogRef.afterClosed().subscribe((result: CategoryDialogResult | undefined) => {
			if (!result) {
				return;
			}

			this.service.setCategories(result.response);
			this.snackBar.open(`Category ${category.name} renamed to ${result.name}`, undefined, { duration: SNACKBAR_DURATION_MS });
		});
	}

	protected onDelete(category: CategoryItem): void {
		const dialogWidth = "30rem";
		const data: ConfirmDialogData = {
			title: "Delete category",
			message: this.buildDeleteMessage(category),
			confirmLabel: "Delete category",
			destructive: true,
		};
		const dialogRef = this.dialog.open(ConfirmDialog, { width: dialogWidth, data });

		dialogRef.afterClosed().subscribe((confirmed: boolean | undefined) => {
			if (!confirmed) {
				return;
			}

			this.apiClient.categories.standard.deleteCategory(category.name).subscribe({
				next: (response) => {
					this.service.setCategories(response);
					this.snackBar.open(this.buildDeletedMessage(category.name, response), undefined, { duration: SNACKBAR_DURATION_MS });
				},
				error: () => undefined,
			});
		});
	}

	protected renameLabel(category: CategoryItem): string {
		return category.protected ? `${category.name} is built in and cannot be renamed` : `Rename ${category.name}`;
	}

	protected deleteLabel(category: CategoryItem): string {
		return category.protected ? `${category.name} is built in and cannot be deleted` : `Delete ${category.name}`;
	}

	private buildDeleteMessage(category: CategoryItem): string {
		if (category.transactionCount === 0 && category.ruleCount === 0) {
			return "Nothing uses this category";
		}

		const moved = this.buildMoveSummary(category.transactionCount, category.ruleCount);
		const verb = category.transactionCount + category.ruleCount === 1 ? "moves" : "move";

		return `${moved} ${verb} to ${this.service.uncategorized()}`;
	}

	private buildDeletedMessage(name: string, response: CategoryDeleteResponse): string {
		if (response.movedTransactions === 0 && response.deletedRules === 0) {
			return `Category ${name} deleted`;
		}

		const moved = this.buildMoveSummary(response.movedTransactions, response.deletedRules);

		return `Category ${name} deleted. ${moved} moved to ${this.service.uncategorized()}`;
	}

	private buildMoveSummary(transactions: number, rules: number): string {
		const parts = [transactions > 0 ? pluralize(transactions, "transaction") : "", rules > 0 ? pluralize(rules, "rule") : ""].filter(
			(part) => part.length > 0,
		);

		return parts.join(" and ");
	}
}
