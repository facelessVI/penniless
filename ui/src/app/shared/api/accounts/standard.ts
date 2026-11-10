import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { AccountResponse, AccountUpdateContract } from "./model";

@Injectable({ providedIn: "root" })
export class AccountsStandardService {
	private readonly http = inject(HttpClient);

	getAccounts() {
		const url = "/api/accounts";

		return this.http.get<AccountResponse[]>(url);
	}

	updateIncludeInCash(connectionId: number | string, accountId: number | string, contract: AccountUpdateContract) {
		const url = `/api/accounts/${connectionId}/${accountId}`;
		const body = contract;

		return this.http.patch<AccountResponse>(url, body);
	}
}
