import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { ApplyCategoriesResponse, CategoriesResponse } from "./model";

@Injectable({ providedIn: "root" })
export class CategoriesStandardService {
	private readonly http = inject(HttpClient);

	getCategories() {
		const url = "/api/categories";

		return this.http.get<CategoriesResponse>(url);
	}

	applyCategories() {
		const url = "/api/categories/apply";

		return this.http.post<ApplyCategoriesResponse>(url, null);
	}
}
