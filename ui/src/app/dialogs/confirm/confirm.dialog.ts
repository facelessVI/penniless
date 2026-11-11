import { ChangeDetectionStrategy, Component, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MAT_DIALOG_DATA, MatDialogModule } from "@angular/material/dialog";

export interface ConfirmDialogData {
	title: string;
	message: string;
	confirmLabel: string;
	cancelLabel?: string;
	destructive?: boolean;
}

/**
 * A yes or no dialog for an action that needs confirming, destructive deletes first.
 *
 * Closes `true` on confirm and `false` on cancel or Escape. It makes no API call: the caller owns the
 * action and only asks this dialog whether to run it.
 */
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
