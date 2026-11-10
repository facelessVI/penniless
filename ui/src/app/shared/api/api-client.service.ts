import { Injectable, inject } from "@angular/core";
import { AccountsStandardService } from "./accounts/standard";
import { CategoriesStandardService } from "./categories/standard";
import { SetupStandardService } from "./setup/standard";
import { SummaryStandardService } from "./summary/standard";
import { TransactionsStandardService } from "./transactions/standard";

/** Single facade over every HTTP service: callers read `<component>.<tier>`. */
@Injectable({ providedIn: "root" })
export class ApiClientService {
	readonly setup = {
		standard: inject(SetupStandardService),
	};

	readonly accounts = {
		standard: inject(AccountsStandardService),
	};

	readonly transactions = {
		standard: inject(TransactionsStandardService),
	};

	readonly summary = {
		standard: inject(SummaryStandardService),
	};

	readonly categories = {
		standard: inject(CategoriesStandardService),
	};
}
