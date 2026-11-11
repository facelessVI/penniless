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
	category: string;
}

export interface TransactionCategoryResponse {
	description: string;
	category: string;
	updated: number;
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
