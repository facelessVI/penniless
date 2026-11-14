export interface CategoryItem {
	name: string;
	position: number;
	transactionCount: number;
	ruleCount: number;
	protected: boolean;
}

export interface CategoriesResponse {
	categories: CategoryItem[];
	uncategorized: string;
}

export interface CategoryNameContract {
	name: string;
}

export interface CategoryOrderContract {
	names: string[];
}

export interface CategoryDeleteResponse extends CategoriesResponse {
	movedTransactions: number;
	deletedRules: number;
}

export interface ApplyCategoriesResponse {
	updated: number;
	uncategorized: number;
}
