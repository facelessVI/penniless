export type TransactionMatchType = "exact" | "contains";

export type TransactionKeywordSource = "description" | "rule" | "token" | "phrase";

export interface TransactionItem {
	connectionId: string;
	accountId: string;
	accountName: string;
	transactionId: string;
	postedDate: string;
	description: string;
	category: string;
	amountCents: number;
}

export interface TransactionListResponse {
	items: TransactionItem[];
	total: number;
	limit: number;
	offset: number;
}

export interface TransactionCategoryContract {
	connectionId: string;
	accountId: string;
	transactionId: string;
	matchType: TransactionMatchType;
	pattern: string;
	category: string;
}

export interface TransactionCategoryResponse {
	description: string;
	matchType: TransactionMatchType;
	pattern: string;
	category: string;
	matched: number;
	updated: number;
	ruleDeleted: boolean;
}

export interface TransactionKeywordRule {
	matchType: TransactionMatchType;
	pattern: string;
	category: string;
}

export interface TransactionKeywordOption {
	matchType: TransactionMatchType;
	pattern: string;
	category: string | null;
	source: TransactionKeywordSource;
	matched: number;
}

export interface TransactionKeywordResponse {
	description: string;
	effectiveRule: TransactionKeywordRule | null;
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
