import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { AccountCreateContract, AccountResponse, AccountUpdateContract } from "./model";

/** Mirrors the API's cap, so the field can say the limit before a save is refused. */
export const MAXIMUM_ACCOUNT_DESCRIPTION_LENGTH = 500;

@Injectable({ providedIn: "root" })
export class AccountsStandardService {
	private readonly http = inject(HttpClient);

	getAccounts() {
		const url = "/api/accounts";

		return this.http.get<AccountResponse[]>(url);
	}

	createAccount(contract: AccountCreateContract) {
		const url = "/api/accounts";
		const body = contract;

		return this.http.post<AccountResponse>(url, body);
	}

	updateAccount(connectionId: number | string, accountId: number | string, contract: AccountUpdateContract) {
		const url = `/api/accounts/${connectionId}/${accountId}`;
		const body = contract;

		return this.http.patch<AccountResponse>(url, body);
	}

	deleteAccount(connectionId: string, accountId: string) {
		const url = `/api/accounts/${connectionId}/${accountId}`;

		return this.http.delete<AccountResponse[]>(url);
	}
}
