export type TransactionMatchType = "exact" | "contains";

export type TransactionKeywordSource = "description" | "rule" | "token" | "phrase";

export interface TransactionItem {
	connection_id: string;
	account_id: string;
	account_name: string;
	transaction_id: string;
	posted_date: string;
	description: string;
	category: string;
	amount_cents: number;
}

export interface TransactionListResponse {
	items: TransactionItem[];
	total: number;
	limit: number;
	offset: number;
}

export interface TransactionCategoryContract {
	connection_id: string;
	account_id: string;
	transaction_id: string;
	match_type: TransactionMatchType;
	pattern: string;
	category: string;
}

export interface TransactionCategoryResponse {
	description: string;
	match_type: TransactionMatchType;
	pattern: string;
	category: string;
	matched: number;
	updated: number;
	rule_deleted: boolean;
}

export interface TransactionKeywordRule {
	match_type: TransactionMatchType;
	pattern: string;
	category: string;
}

export interface TransactionKeywordOption {
	match_type: TransactionMatchType;
	pattern: string;
	category: string | null;
	source: TransactionKeywordSource;
	matched: number;
}

export interface TransactionKeywordResponse {
	description: string;
	effective_rule: TransactionKeywordRule | null;
	options: TransactionKeywordOption[];
}

export interface TransactionKeywordQuery {
	connectionId: string;
	accountId: string;
	transactionId: string;
}

export interface TransactionQuery {
	accountId?: string | null;
	category?: string | null;
	start?: string | null;
	end?: string | null;
	includeTransfers?: boolean;
	limit?: number;
	offset?: number;
}
