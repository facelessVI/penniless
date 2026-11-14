import { Injectable, computed, inject } from "@angular/core";
import { MatSnackBar } from "@angular/material/snack-bar";
import { ApiClientService } from "@shared/api/api-client.service";
import { BackfillContract, StatusResponse } from "@shared/api/setup/model";
import { DataOperationService } from "@shared/services/data-operation.service";
import { StatusService } from "@shared/services/status.service";

export const BACKFILL_MONTHS = 12;

const SNACKBAR_DURATION_MS = 4_000;

const TIMESTAMP_FORMAT = new Intl.DateTimeFormat("en-US", {
	month: "short",
	day: "numeric",
	year: "numeric",
	hour: "numeric",
	minute: "2-digit",
});

export interface DataMetadataRow {
	label: string;
	value: string;
	failed?: boolean;
}

@Injectable({ providedIn: "root" })
export class DataPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly statusService = inject(StatusService);
	private readonly dataOperation = inject(DataOperationService);
	private readonly snackBar = inject(MatSnackBar);

	readonly status = this.statusService.status;
	readonly connected = computed(() => this.status()?.connected ?? false);
	readonly busy = this.dataOperation.busy;
	readonly operationLabel = computed(() => {
		switch (this.dataOperation.active()) {
			case "refresh":
				return "Refreshing…";
			case "backfill":
				return "Backfilling 12 months…";
			case "apply-rules":
				return "Re-applying rules…";
			case "connect":
				return "Connecting…";
			case null:
				return null;
		}
	});

	/** Null until the status read lands. */
	readonly metadata = computed<DataMetadataRow[] | null>(() => {
		const status = this.status();

		if (status === null) {
			return null;
		}

		return [
			{ label: "Connection", value: status.connected ? "Connected" : "Not connected" },
			{ label: "Source", value: status.source === "live" ? "Live" : "Fixture" },
			{ label: "Credential claimed", value: this.formatTimestamp(status.credentialClaimedAt) },
			{ label: "Accounts", value: `${status.accountCount}` },
			{ label: "Transactions", value: `${status.transactionCount}` },
			{ label: "Last fetch", ...this.describeLastFetch(status) },
			{ label: "Refresh", value: this.describeRefresh(status) },
		];
	});

	readonly refreshIntervalNote = computed(() => {
		const status = this.status();

		if (status === null) {
			return null;
		}

		return `Refreshes are refused for ${status.refreshMinIntervalHours} hours after a success.`;
	});

	load(): void {
		this.statusService.refresh().subscribe({ next: () => undefined });
	}

	applyRules(): void {
		this.dataOperation.start("apply-rules");

		this.apiClient.categories.standard.applyCategories().subscribe({
			next: (result) => {
				this.dataOperation.stop();
				this.snackBar.open(
					`${result.updated} transaction${result.updated === 1 ? "" : "s"} re-categorized, ${result.uncategorized} left uncategorized.`,
					undefined,
					{ duration: SNACKBAR_DURATION_MS },
				);
				this.load();
			},
			error: () => this.dataOperation.stop(),
		});
	}

	backfill(): void {
		const contract: BackfillContract = { months: BACKFILL_MONTHS };

		this.dataOperation.start("backfill");

		this.apiClient.setup.standard.backfill(contract).subscribe({
			next: (result) => {
				this.dataOperation.stop();
				this.snackBar.open(`Backfill stored ${result.transactionsStored} transactions across ${result.windows} windows.`, undefined, {
					duration: SNACKBAR_DURATION_MS,
				});
				this.load();
			},
			error: () => this.dataOperation.stop(),
		});
	}

	private describeLastFetch(status: StatusResponse): Pick<DataMetadataRow, "value" | "failed"> {
		if (status.lastFetchedAt === null) {
			return { value: "Never" };
		}

		const outcome = status.lastFetchStatus === "error" ? "Failed" : "Succeeded";
		const code = status.lastFetchErrorCode === null ? "" : ` (${status.lastFetchErrorCode})`;

		return { value: `${outcome} ${this.formatTimestamp(status.lastFetchedAt)}${code}`, failed: status.lastFetchStatus === "error" };
	}

	private describeRefresh(status: StatusResponse): string {
		if (status.refreshAllowed || status.nextRefreshAllowedAt === null) {
			return "Allowed now";
		}

		return `Next allowed ${this.formatTimestamp(status.nextRefreshAllowedAt)}`;
	}

	private formatTimestamp(value: string | null): string {
		if (value === null) {
			return "Never";
		}

		const date = new Date(value);

		return Number.isNaN(date.getTime()) ? "Never" : TIMESTAMP_FORMAT.format(date);
	}
}
