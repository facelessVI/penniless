export interface CategoryItem {
	name: string;
	position: number;
	transaction_count: number;
	rule_count: number;
	protected: boolean;
}

export interface CategoriesResponse {
	categories: CategoryItem[];
	uncategorized: string;
}

export interface CategoryNameContract {
	name: string;
}

export interface CategoryDeleteResponse extends CategoriesResponse {
	moved_transactions: number;
	deleted_rules: number;
}

export interface ApplyCategoriesResponse {
	updated: number;
	uncategorized: number;
}
