import { ChangeDetectionStrategy, Component, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MAT_DIALOG_DATA, MatDialogModule } from "@angular/material/dialog";
import { ConfirmDialogData } from "@app/shared/interfaces/confirm.interface";
@Component({
	selector: "penniless-confirm-dialog",
	imports: [MatButtonModule, MatDialogModule],
	templateUrl: "./confirm.dialog.html",
	styleUrl: "./confirm.dialog.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfirmDialog {
	protected readonly data: ConfirmDialogData = inject(MAT_DIALOG_DATA);
	protected readonly cancelLabel = this.data.cancelLabel ?? "Cancel";
	protected readonly destructive = this.data.destructive ?? false;
}
