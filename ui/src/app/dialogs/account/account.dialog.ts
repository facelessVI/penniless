import { A11yModule } from "@angular/cdk/a11y";
import { ChangeDetectionStrategy, Component, inject, signal } from "@angular/core";
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from "@angular/forms";
import { MatAutocompleteModule, MatAutocompleteSelectedEvent } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { AccountCreateContract } from "@shared/api/accounts/model";
import { MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH } from "@shared/api/accounts/standard";
import { ApiClientService } from "@shared/api/api-client.service";
import { AccountDialogData, AccountDialogResult } from "@shared/interfaces/account.interface";
import { centsToInput, parseCents } from "@shared/utils/money.util";
import { LabelOption, labelOptions } from "@shared/utils/label.util";

function nonBlank(control: AbstractControl<string>): ValidationErrors | null {
	return control.value.trim().length > 0 ? null : { required: true };
}

function money(control: AbstractControl<string>): ValidationErrors | null {
	return parseCents(control.value) === null ? { money: true } : null;
}

@Component({
	selector: "penniless-account-dialog",
	imports: [A11yModule, ReactiveFormsModule, MatAutocompleteModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
	templateUrl: "./account.dialog.html",
	styleUrl: "./account.dialog.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccountDialog {
	private readonly apiClient = inject(ApiClientService);
	private readonly dialogRef = inject(MatDialogRef<AccountDialog>);
	protected readonly data: AccountDialogData = inject(MAT_DIALOG_DATA);

	protected readonly form = new FormGroup({
		name: new FormControl("", { nonNullable: true, validators: [nonBlank] }),
		balance: new FormControl(centsToInput(0), { nonNullable: true, validators: [money] }),
		description: new FormControl("", {
			nonNullable: true,
			validators: [Validators.maxLength(MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH)],
		}),
	});
	protected readonly labelInput = new FormControl("", { nonNullable: true });
	protected readonly labels = signal<string[]>([]);
	protected readonly loading = signal(false);
	protected readonly maximumDescriptionLength = MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH;

	/** A method rather than a `computed`: a `FormControl` is not a signal, so a memoized list would never follow the typed text. */
	protected labelChoices(): LabelOption[] {
		return labelOptions(this.data.labelVocabulary, this.labels(), this.labelInput.value);
	}

	protected isSubmitDisabled(): boolean {
		return this.loading() || this.form.invalid;
	}

	protected onLabelSelected(event: MatAutocompleteSelectedEvent): void {
		const label = String(event.option.value);
		const attached = this.labels();

		if (!attached.some((candidate) => candidate.toLowerCase() === label.toLowerCase())) {
			this.labels.set([...attached, label]);
		}

		this.labelInput.setValue("");
	}

	protected onDetachLabel(label: string): void {
		this.labels.set(this.labels().filter((candidate) => candidate !== label));
	}

	protected submit(): void {
		const value = this.form.getRawValue();
		const balanceCents = parseCents(value.balance);

		if (this.isSubmitDisabled()) {
			this.form.markAllAsTouched();
			return;
		}

		if (balanceCents === null) {
			return;
		}

		const contract: AccountCreateContract = {
			name: value.name.trim(),
			balanceCents,
			description: value.description,
			labels: this.labels(),
		};

		this.loading.set(true);

		this.apiClient.accounts.standard.createAccount(contract).subscribe({
			next: (account) => {
				this.loading.set(false);
				this.dialogRef.close({ account } satisfies AccountDialogResult);
			},
			// The error interceptor has already shown the message. The dialog stays open with what was typed
			// so the create can be retried.
			error: () => this.loading.set(false),
		});
	}
}
