import { Injectable, computed, inject, signal } from "@angular/core";
import { AccountResponse } from "@shared/api/accounts/model";
import { ApiClientService } from "@shared/api/api-client.service";
import { BackfillContract } from "@shared/api/setup/model";
import { SummaryResponse } from "@shared/api/summary/model";
import { StatusService } from "@shared/services/status.service";
import { firstDayOfMonth, fromIsoDate, toIsoDate } from "@shared/utils/date.util";
import { formatCents, formatSignedCents } from "@shared/utils/money.util";

export const BACKFILL_MONTHS = 12;

export interface DashboardSummaryStrip {
	totalIn: string;
	totalOut: string;
	net: string;
	cash: string;
	uncategorizedCount: number;
	transactionCount: number;
	periodLabel: string;
}

export interface DashboardAccountRow extends AccountResponse {
	balanceLabel: string;
}

const PERIOD_DATE_FORMAT = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
const PERIOD_DATE_FORMAT_WITH_YEAR = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });

@Injectable({ providedIn: "root" })
export class DashboardPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly statusService = inject(StatusService);

	readonly accounts = signal<AccountResponse[]>([]);
	readonly summary = signal<SummaryResponse | null>(null);
	readonly status = this.statusService.status;
	readonly loading = signal(true);
	readonly busy = signal(false);
	readonly rulesMessage = signal<string | null>(null);

	readonly accountRows = computed<DashboardAccountRow[]>(() =>
		this.accounts().map((account) => ({
			...account,
			balanceLabel: formatCents(account.balance_cents, account.currency),
		})),
	);

	readonly summaryStrip = computed<DashboardSummaryStrip | null>(() => {
		const summary = this.summary();

		if (summary === null) {
			return null;
		}

		return {
			totalIn: formatCents(summary.total_in_cents),
			totalOut: formatCents(summary.total_out_cents),
			net: formatSignedCents(summary.net_cents),
			cash: formatCents(summary.cash_total_cents),
			uncategorizedCount: summary.uncategorized_count,
			transactionCount: summary.transaction_count,
			periodLabel: this.formatPeriod(summary.start, summary.end),
		};
	});

	readonly hasAccounts = computed(() => this.accounts().length > 0);
	readonly fetchFailed = computed(() => this.status()?.last_fetch_status === "error");

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

	setIncludeInCash(account: AccountResponse, includeInCash: boolean): void {
		this.busy.set(true);

		this.apiClient.accounts.standard.updateIncludeInCash(account.connection_id, account.account_id, { include_in_cash: includeInCash }).subscribe({
			next: (updated) => {
				this.accounts.update((accounts) => accounts.map((candidate) => (candidate.account_id === updated.account_id ? updated : candidate)));
				this.busy.set(false);
				this.refreshSummary();
			},
			error: () => {
				this.busy.set(false);
				this.reloadAccounts();
			},
		});
	}

	refresh(): void {
		this.busy.set(true);

		this.apiClient.setup.standard.refresh().subscribe({
			next: () => {
				this.busy.set(false);
				this.load();
			},
			error: () => {
				this.busy.set(false);
				// A 429 means the guard is active: reload the status so the reason is shown.
				this.statusService.refresh().subscribe({ next: () => undefined });
			},
		});
	}

	applyRules(): void {
		this.busy.set(true);
		this.rulesMessage.set(null);

		this.apiClient.categories.standard.applyCategories().subscribe({
			next: (result) => {
				this.busy.set(false);
				this.rulesMessage.set(
					`Rules applied: ${result.updated} transaction${result.updated === 1 ? "" : "s"} re-categorized, ${result.uncategorized} left uncategorized.`,
				);
				this.load();
			},
			error: () => this.busy.set(false),
		});
	}

	backfill(): void {
		const contract: BackfillContract = { months: BACKFILL_MONTHS };

		this.busy.set(true);

		this.apiClient.setup.standard.backfill(contract).subscribe({
			next: () => {
				this.busy.set(false);
				this.load();
			},
			error: () => this.busy.set(false),
		});
	}

	reset(): void {
		this.accounts.set([]);
		this.summary.set(null);
		this.loading.set(true);
		this.busy.set(false);
		this.rulesMessage.set(null);
	}

	private refreshSummary(): void {
		const today = new Date();

		this.apiClient.summary.standard.getSummary(toIsoDate(firstDayOfMonth(today)), toIsoDate(today)).subscribe({
			next: (summary) => this.summary.set(summary),
		});
	}

	private reloadAccounts(): void {
		this.apiClient.accounts.standard.getAccounts().subscribe({
			next: (accounts) => this.accounts.set(accounts),
		});
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
