import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { SummaryResponse } from "./model";

@Injectable({ providedIn: "root" })
export class SummaryStandardService {
	private readonly http = inject(HttpClient);

	getSummary(start: string | null = null, end: string | null = null) {
		const url = "/api/summary";
		let params = new HttpParams();

		if (start) {
			params = params.set("start", start);
		}

		if (end) {
			params = params.set("end", end);
		}

		return this.http.get<SummaryResponse>(url, { params });
	}
}
