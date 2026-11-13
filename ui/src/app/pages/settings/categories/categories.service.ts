import { Injectable, inject, signal } from "@angular/core";
import { ApiClientService } from "@shared/api/api-client.service";
import { CategoriesResponse, CategoryItem } from "@shared/api/categories/model";

@Injectable({ providedIn: "root" })
export class CategoriesPageService {
	private readonly apiClient = inject(ApiClientService);

	readonly loading = signal(false);
	readonly categories = signal<CategoryItem[]>([]);
	readonly uncategorized = signal("Uncategorized");

	load(): void {
		this.loading.set(true);
		this.apiClient.categories.standard.getCategories().subscribe({
			next: (response) => {
				this.setCategories(response);
				this.loading.set(false);
			},
			error: () => {
				this.loading.set(false);
			},
		});
	}

	setCategories(response: CategoriesResponse): void {
		this.categories.set(response.categories);
		this.uncategorized.set(response.uncategorized);
	}

	reset(): void {
		this.categories.set([]);
		this.uncategorized.set("Uncategorized");
		this.loading.set(false);
	}
}
