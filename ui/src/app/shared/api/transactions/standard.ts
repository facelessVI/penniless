import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import {
	TransactionCategoryContract,
	TransactionCategoryResponse,
	TransactionKeywordQuery,
	TransactionKeywordResponse,
	TransactionListResponse,
	TransactionQuery,
} from "./model";

export const DEFAULT_TRANSACTION_PAGE_SIZE = 50;
export const MAXIMUM_TRANSACTION_PAGE_SIZE = 200;

@Injectable({ providedIn: "root" })
export class TransactionsStandardService {
	private readonly http = inject(HttpClient);

	getTransactions(query: TransactionQuery = {}) {
		const url = "/api/transactions";
		const limit = query.limit ?? DEFAULT_TRANSACTION_PAGE_SIZE;
		const offset = query.offset ?? 0;
		let params = new HttpParams().set("limit", limit.toString()).set("offset", offset.toString());

		if (query.accountId) {
			params = params.set("account_id", query.accountId);
		}

		if (query.category) {
			params = params.set("category", query.category);
		}

		if (query.start) {
			params = params.set("start", query.start);
		}

		if (query.end) {
			params = params.set("end", query.end);
		}

		if (query.includeTransfers) {
			params = params.set("include_transfers", "true");
		}

		return this.http.get<TransactionListResponse>(url, { params });
	}

	assignCategory(contract: TransactionCategoryContract) {
		const url = "/api/transactions/category";
		const body = contract;

		return this.http.post<TransactionCategoryResponse>(url, body);
	}

	getKeywordOptions(query: TransactionKeywordQuery) {
		const url = "/api/transactions/keywords";
		const params = new HttpParams()
			.set("connection_id", query.connectionId)
			.set("account_id", query.accountId)
			.set("transaction_id", query.transactionId);

		return this.http.get<TransactionKeywordResponse>(url, { params });
	}
}
