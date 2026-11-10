import { Injectable, computed, inject, signal } from "@angular/core";
import { AccountResponse } from "@shared/api/accounts/model";
import { ApiClientService } from "@shared/api/api-client.service";
import { TransactionItem, TransactionQuery } from "@shared/api/transactions/model";
import { DEFAULT_TRANSACTION_PAGE_SIZE, MAXIMUM_TRANSACTION_PAGE_SIZE } from "@shared/api/transactions/standard";
import { firstDayOfMonth, lastDayOfMonth, toIsoDate } from "@shared/utils/date.util";
import { formatSignedCents } from "@shared/utils/money.util";

export type DatePreset = "this-month" | "last-month" | "last-3-months" | "year-to-date" | "custom";

export const PAGE_SIZE_OPTIONS = [50, 100, MAXIMUM_TRANSACTION_PAGE_SIZE];

export interface TransactionRow extends TransactionItem {
	amountLabel: string;
}

@Injectable({ providedIn: "root" })
export class TransactionsPageService {
	private readonly apiClient = inject(ApiClientService);

	readonly items = signal<TransactionItem[]>([]);
	readonly total = signal(0);
	readonly accounts = signal<AccountResponse[]>([]);
	readonly categories = signal<string[]>([]);
	readonly loading = signal(true);

	readonly preset = signal<DatePreset>("last-3-months");
	readonly customStart = signal<Date | null>(null);
	readonly customEnd = signal<Date | null>(null);
	readonly accountId = signal<string | null>(null);
	readonly category = signal<string | null>(null);
	readonly includeTransfers = signal(false);
	readonly pageNumber = signal(1);
	readonly pageSize = signal(DEFAULT_TRANSACTION_PAGE_SIZE);

	readonly rows = computed<TransactionRow[]>(() => this.items().map((item) => ({ ...item, amountLabel: formatSignedCents(item.amount_cents) })));

	readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));

	readonly rangeLabel = computed(() => {
		const total = this.total();

		if (total === 0) {
			return "No transactions";
		}

		const first = (this.pageNumber() - 1) * this.pageSize() + 1;
		const last = Math.min(this.pageNumber() * this.pageSize(), total);

		return `${first}-${last} of ${total}`;
	});

	/** Applies a filter from outside the page without firing a request. */
	initCategory(category: string | null): void {
		this.category.set(category);
	}

	loadFilterOptions(): void {
		this.apiClient.accounts.standard.getAccounts().subscribe({ next: (accounts) => this.accounts.set(accounts) });

		this.apiClient.categories.standard.getCategories().subscribe({
			next: (response) => this.categories.set(response.categories),
		});
	}

	setPreset(preset: DatePreset): void {
		this.preset.set(preset);
		this.pageNumber.set(1);
		this.getPage();
	}

	setCustomStart(start: Date | null): void {
		this.customStart.set(start);
		this.pageNumber.set(1);
		this.getPage();
	}

	setCustomEnd(end: Date | null): void {
		this.customEnd.set(end);
		this.pageNumber.set(1);
		this.getPage();
	}

	setAccountId(accountId: string | null): void {
		this.accountId.set(accountId);
		this.pageNumber.set(1);
		this.getPage();
	}

	setCategory(category: string | null): void {
		this.category.set(category);
		this.pageNumber.set(1);
		this.getPage();
	}

	setIncludeTransfers(includeTransfers: boolean): void {
		this.includeTransfers.set(includeTransfers);
		this.pageNumber.set(1);
		this.getPage();
	}

	setPageNumber(pageNumber: number): void {
		const bounded = Math.min(Math.max(1, pageNumber), this.totalPages());
		this.pageNumber.set(bounded);
		this.getPage();
	}

	setPageSize(pageSize: number): void {
		this.pageSize.set(pageSize);
		this.pageNumber.set(1);
		this.getPage();
	}

	getPage(): void {
		this.loading.set(true);

		this.apiClient.transactions.standard.getTransactions(this.buildQuery()).subscribe({
			next: (response) => {
				this.items.set(response.items);
				this.total.set(response.total);
				this.loading.set(false);
			},
			error: () => this.loading.set(false),
		});
	}

	reset(): void {
		this.items.set([]);
		this.total.set(0);
		this.categories.set([]);
		this.accounts.set([]);
		this.preset.set("last-3-months");
		this.customStart.set(null);
		this.customEnd.set(null);
		this.accountId.set(null);
		this.category.set(null);
		this.includeTransfers.set(false);
		this.pageNumber.set(1);
		this.pageSize.set(DEFAULT_TRANSACTION_PAGE_SIZE);
		this.loading.set(true);
	}

	private buildQuery(): TransactionQuery {
		const range = this.resolveRange();

		return {
			accountId: this.accountId(),
			category: this.category(),
			start: range.start,
			end: range.end,
			includeTransfers: this.includeTransfers(),
			limit: this.pageSize(),
			offset: (this.pageNumber() - 1) * this.pageSize(),
		};
	}

	private resolveRange(): { start: string | null; end: string | null } {
		const today = new Date();
		const customStart = this.customStart();
		const customEnd = this.customEnd();

		switch (this.preset()) {
			case "this-month":
				return { start: toIsoDate(firstDayOfMonth(today)), end: toIsoDate(today) };
			case "last-month": {
				const previousMonth = firstDayOfMonth(today, 1);

				return { start: toIsoDate(previousMonth), end: toIsoDate(lastDayOfMonth(previousMonth)) };
			}
			case "last-3-months":
				return { start: toIsoDate(firstDayOfMonth(today, 2)), end: toIsoDate(today) };
			case "year-to-date":
				return { start: toIsoDate(new Date(today.getFullYear(), 0, 1)), end: toIsoDate(today) };
			case "custom":
				return {
					start: customStart === null ? null : toIsoDate(customStart),
					end: customEnd === null ? null : toIsoDate(customEnd),
				};
		}
	}
}
