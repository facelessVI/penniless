import { Routes } from "@angular/router";
import { MainLayoutComponent } from "@app/components/main-layout/main-layout.component";
import { DashboardPage } from "@app/pages/dashboard/dashboard.page";
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
		],
	},
	{ path: "**", redirectTo: "" },
];
