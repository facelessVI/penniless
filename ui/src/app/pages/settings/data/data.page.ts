import { ChangeDetectionStrategy, Component, OnInit, ViewEncapsulation, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatDialog } from "@angular/material/dialog";
import { RouterLink } from "@angular/router";
import { ConfirmDialog } from "@app/dialogs/confirm/confirm.dialog";
import { ConfirmDialogData } from "@app/shared/interfaces/confirm.interface";
import { DataPageService } from "./data.service";

const DIALOG_WIDTH = "30rem";

@Component({
	selector: "penniless-settings-data",
	imports: [RouterLink, MatButtonModule],
	templateUrl: "./data.page.html",
	styleUrl: "./data.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SettingsDataPage implements OnInit {
	private readonly dialog = inject(MatDialog);

	protected readonly service = inject(DataPageService);

	ngOnInit(): void {
		this.service.load();
	}

	protected onApplyRules(): void {
		this.service.applyRules();
	}

	protected onBackfill(): void {
		const data: ConfirmDialogData = {
			title: "Backfill 12 months",
			message:
				"This spends 5 of the 24 daily SimpleFIN requests for this access URL and refetches the last 12 months. Existing transactions are updated in place, not duplicated.",
			confirmLabel: "Backfill 12 months",
		};
		const dialogRef = this.dialog.open(ConfirmDialog, { width: DIALOG_WIDTH, data });

		dialogRef.afterClosed().subscribe((confirmed: boolean | undefined) => {
			if (!confirmed) {
				return;
			}

			this.service.backfill();
		});
	}
}
