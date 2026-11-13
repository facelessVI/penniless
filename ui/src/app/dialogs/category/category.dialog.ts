import { ChangeDetectionStrategy, Component, inject, signal } from "@angular/core";
import { A11yModule } from "@angular/cdk/a11y";
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { ApiClientService } from "@shared/api/api-client.service";
import { CategoryDialogData, CategoryDialogResult } from "@app/shared/interfaces/category.interface";

export const MAXIMUM_CATEGORY_NAME_LENGTH = 40;

function nonBlank(control: AbstractControl<string>): ValidationErrors | null {
	return control.value.trim().length > 0 ? null : { required: true };
}

@Component({
	selector: "penniless-category-dialog",
	imports: [A11yModule, ReactiveFormsModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
	templateUrl: "./category.dialog.html",
	styleUrl: "./category.dialog.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CategoryDialog {
	private readonly apiClient = inject(ApiClientService);
	private readonly dialogRef = inject(MatDialogRef<CategoryDialog>);
	protected readonly data: CategoryDialogData = inject(MAT_DIALOG_DATA);

	protected readonly form = new FormGroup({
		name: new FormControl(this.data.name, {
			nonNullable: true,
			validators: [nonBlank, Validators.maxLength(MAXIMUM_CATEGORY_NAME_LENGTH)],
		}),
	});
	protected readonly loading = signal(false);
	protected readonly title = this.data.mode === "create" ? "New category" : "Rename category";
	protected readonly submitLabel = this.data.mode === "create" ? "Create" : "Save";
	protected readonly maximumNameLength = MAXIMUM_CATEGORY_NAME_LENGTH;

	protected submit(): void {
		const name = this.form.controls.name.value.trim();

		if (this.isSubmitDisabled()) {
			this.form.markAllAsTouched();
			return;
		}

		this.loading.set(true);

		const contract = { name };
		const request$ =
			this.data.mode === "create"
				? this.apiClient.categories.standard.createCategory(contract)
				: this.apiClient.categories.standard.renameCategory(this.data.name, contract);

		request$.subscribe({
			next: (response) => {
				this.loading.set(false);
				this.dialogRef.close({ response, name } satisfies CategoryDialogResult);
			},
			// The error interceptor has already shown the message. The dialog stays open with the name intact
			// so the save can be retried.
			error: () => this.loading.set(false),
		});
	}

	protected isSubmitDisabled(): boolean {
		const name = this.form.controls.name.value.trim();
		const isUnchanged = this.data.mode === "rename" && name === this.data.name;

		return this.loading() || this.form.invalid || isUnchanged;
	}
}
