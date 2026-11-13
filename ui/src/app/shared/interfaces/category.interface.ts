import { CategoriesResponse } from "../api/categories/model";

export interface CategoryDialogData {
	mode: "create" | "rename";
	name: string;
}

export interface CategoryDialogResult {
	response: CategoriesResponse;
	name: string;
}
