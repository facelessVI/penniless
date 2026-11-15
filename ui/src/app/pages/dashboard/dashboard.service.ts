import { Injectable, computed, inject, signal } from "@angular/core";
import { AccountResponse, resolvedAccountName } from "@shared/api/accounts/model";
import { ApiClientService } from "@shared/api/api-client.service";
import { SummaryResponse } from "@shared/api/summary/model";
import { DataOperationService } from "@shared/services/data-operation.service";
import { StatusService } from "@shared/services/status.service";
import { firstDayOfMonth, fromIsoDate, toIsoDate } from "@shared/utils/date.util";
import { formatCents, formatSignedCents } from "@shared/utils/money.util";

export interface DashboardSummaryStrip {
	totalIn: string;
	totalOut: string;
	net: string;
	cash: string;
	netWorth: string;
	transactionCount: number;
	periodLabel: string;
}

export interface DashboardAccountRow extends AccountResponse {
	balanceLabel: string;
}

export type DashboardSortColumn = "connection" | "balance";
export type DashboardSortDirection = "asc" | "desc";

const compareConnections = (first: DashboardAccountRow, second: DashboardAccountRow): number =>
	first.connectionName.localeCompare(second.connectionName) || resolvedAccountName(first).localeCompare(resolvedAccountName(second));

const compareBalances = (first: DashboardAccountRow, second: DashboardAccountRow): number =>
	first.balanceCents - second.balanceCents || compareConnections(first, second);

const SORT_COMPARATORS: Record<DashboardSortColumn, (first: DashboardAccountRow, second: DashboardAccountRow) => number> = {
	connection: compareConnections,
	balance: compareBalances,
};

const PERIOD_DATE_FORMAT = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
const PERIOD_DATE_FORMAT_WITH_YEAR = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });

@Injectable({ providedIn: "root" })
export class DashboardPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly statusService = inject(StatusService);
	private readonly dataOperation = inject(DataOperationService);

	readonly accounts = signal<AccountResponse[]>([]);
	readonly summary = signal<SummaryResponse | null>(null);
	readonly status = this.statusService.status;
	/** The page's own first paint: summary and accounts, joined so the tables do not pop in one at a time. */
	readonly loading = signal(true);
	/** An action that must not overlap another one is running; the one long state the app shares. */
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
	readonly sortColumn = signal<DashboardSortColumn | null>(null);
	readonly sortDirection = signal<DashboardSortDirection | null>(null);

	readonly accountRows = computed<DashboardAccountRow[]>(() => {
		const rows = this.accounts().map((account) => ({
			...account,
			balanceLabel: formatCents(account.balanceCents, account.currency),
		}));
		const column = this.sortColumn();
		const direction = this.sortDirection();

		if (column === null || direction === null) {
			return rows;
		}

		const comparator = SORT_COMPARATORS[column];
		const order = direction === "desc" ? -1 : 1;

		return [...rows].sort((first, second) => order * comparator(first, second));
	});

	readonly summaryStrip = computed<DashboardSummaryStrip | null>(() => {
		const summary = this.summary();

		if (summary === null) {
			return null;
		}

		return {
			totalIn: formatCents(summary.totalInCents),
			totalOut: formatCents(summary.totalOutCents),
			net: formatSignedCents(summary.netCents),
			cash: formatCents(summary.cashTotalCents),
			netWorth: formatCents(summary.netWorthCents),
			transactionCount: summary.transactionCount,
			periodLabel: this.formatPeriod(summary.start, summary.end),
		};
	});

	readonly hasAccounts = computed(() => this.accounts().length > 0);
	readonly fetchFailed = computed(() => this.status()?.lastFetchStatus === "error");

	load(): void {
		this.loading.set(true);

		const today = new Date();
		const periodStart = toIsoDate(firstDayOfMonth(today));
		const periodEnd = toIsoDate(today);
		let pendingRequests = 2;

		const settle = (): void => {
			pendingRequests -= 1;

			if (pendingRequests === 0) {
				this.loading.set(false);
			}
		};

		this.apiClient.summary.standard.getSummary(periodStart, periodEnd).subscribe({
			next: (summary) => {
				this.summary.set(summary);
				settle();
			},
			error: () => settle(),
		});

		this.apiClient.accounts.standard.getAccounts().subscribe({
			next: (accounts) => {
				this.accounts.set(accounts);
				settle();
			},
			error: () => settle(),
		});

		this.statusService.refresh().subscribe({ next: () => undefined });
	}

	setSort(column: DashboardSortColumn | null, direction: DashboardSortDirection | null): void {
		this.sortColumn.set(column);
		this.sortDirection.set(direction);
	}

	refresh(): void {
		this.dataOperation.start("refresh");

		this.apiClient.setup.standard.refresh().subscribe({
			next: () => {
				this.dataOperation.stop();
				this.load();
			},
			error: () => {
				this.dataOperation.stop();
				// A 429 means the guard is active: reload the status so the reason is shown.
				this.statusService.refresh().subscribe({ next: () => undefined });
			},
		});
	}

	reset(): void {
		this.accounts.set([]);
		this.summary.set(null);
		this.loading.set(true);
		this.sortColumn.set(null);
		this.sortDirection.set(null);
	}

	private formatPeriod(start: string, end: string): string {
		const startDate = fromIsoDate(start);
		const endDate = fromIsoDate(end);

		if (startDate === null || endDate === null) {
			return "";
		}

		return `${PERIOD_DATE_FORMAT.format(startDate)} - ${PERIOD_DATE_FORMAT_WITH_YEAR.format(endDate)}`;
	}
}
