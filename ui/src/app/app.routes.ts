import { Routes } from "@angular/router";
import { MainLayoutComponent } from "@app/components/main-layout/main-layout.component";
import { DashboardPage } from "@app/pages/dashboard/dashboard.page";
import { SettingsAccountsPage } from "@app/pages/settings/accounts/accounts.page";
import { SettingsCategoriesPage } from "@app/pages/settings/categories/categories.page";
import { SettingsDataPage } from "@app/pages/settings/data/data.page";
import { SetupPage } from "@app/pages/setup/setup.page";
import { TransactionsPage } from "@app/pages/transactions/transactions.page";

export const routes: Routes = [
	{ path: "setup", component: SetupPage },
	{
		path: "",
		component: MainLayoutComponent,
		children: [
			{ path: "", redirectTo: "dashboard", pathMatch: "full" },
			{ path: "dashboard", component: DashboardPage },
			{ path: "transactions", component: TransactionsPage },
			{ path: "settings/accounts/:connectionId/:accountId", component: SettingsAccountsPage },
			{ path: "settings/accounts", component: SettingsAccountsPage },
			{ path: "settings/categories", component: SettingsCategoriesPage },
			{ path: "settings/data", component: SettingsDataPage },
		],
	},
	{ path: "**", redirectTo: "" },
];
