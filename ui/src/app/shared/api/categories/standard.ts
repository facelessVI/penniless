import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { ApplyCategoriesResponse, CategoriesResponse, CategoryDeleteResponse, CategoryNameContract, CategoryOrderContract } from "./model";

@Injectable({ providedIn: "root" })
export class CategoriesStandardService {
	private readonly http = inject(HttpClient);

	getCategories() {
		const url = "/api/categories";

		return this.http.get<CategoriesResponse>(url);
	}

	createCategory(contract: CategoryNameContract) {
		const url = "/api/categories";
		const body = contract;

		return this.http.post<CategoriesResponse>(url, body);
	}

	renameCategory(name: string, contract: CategoryNameContract) {
		const url = `/api/categories/${encodeURIComponent(name)}`;
		const body = contract;

		return this.http.patch<CategoriesResponse>(url, body);
	}

	reorderCategories(names: string[]) {
		const url = "/api/categories/order";
		const body: CategoryOrderContract = { names };

		return this.http.put<CategoriesResponse>(url, body);
	}

	deleteCategory(name: string) {
		const url = `/api/categories/${encodeURIComponent(name)}`;

		return this.http.delete<CategoryDeleteResponse>(url);
	}

	applyCategories() {
		const url = "/api/categories/apply";

		return this.http.post<ApplyCategoriesResponse>(url, null);
	}
}
