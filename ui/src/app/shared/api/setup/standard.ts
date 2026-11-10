import { HttpClient, HttpContext } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { SUPPRESS_ERROR_BANNER } from "@shared/services/error.service";
import { BackfillContract, BackfillResponse, ConnectContract, ConnectResponse, RefreshResponse, StatusResponse } from "./model";

@Injectable({ providedIn: "root" })
export class SetupStandardService {
	private readonly http = inject(HttpClient);

	claimSetupToken(contract: ConnectContract) {
		const url = "/api/connect";
		const body = contract;
		// The setup screen shows this failure inline, so the global banner would only duplicate it.
		const options = { context: new HttpContext().set(SUPPRESS_ERROR_BANNER, true) };

		return this.http.post<ConnectResponse>(url, body, options);
	}

	getStatus() {
		const url = "/api/status";

		return this.http.get<StatusResponse>(url);
	}

	refresh() {
		const url = "/api/refresh";

		return this.http.post<RefreshResponse>(url, null);
	}

	backfill(contract: BackfillContract) {
		const url = "/api/backfill";
		const body = contract;

		return this.http.post<BackfillResponse>(url, body);
	}
}
