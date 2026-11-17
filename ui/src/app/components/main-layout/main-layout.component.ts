import { ChangeDetectionStrategy, Component, ViewEncapsulation, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatTooltipModule } from "@angular/material/tooltip";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { MainLayoutNavIconComponent, NavIcon } from "@app/components/main-layout/nav-icon/main-layout-nav-icon.component";
import { ErrorService } from "@shared/services/error.service";
import { LayoutService } from "@shared/services/layout.service";

export interface NavLink {
	label: string;
	route: string;
	icon: NavIcon;
}

@Component({
	selector: "app-main-layout",
	imports: [RouterOutlet, RouterLink, RouterLinkActive, MatButtonModule, MatTooltipModule, MainLayoutNavIconComponent],
	templateUrl: "./main-layout.component.html",
	styleUrl: "./main-layout.component.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class MainLayoutComponent {
	protected readonly errorService = inject(ErrorService);
	protected readonly layoutService = inject(LayoutService);

	protected readonly links: NavLink[] = [
		{ label: "Dashboard", route: "/dashboard", icon: "dashboard" },
		{ label: "Transactions", route: "/transactions", icon: "transactions" },
	];

	protected readonly settingsLinks: NavLink[] = [
		{ label: "Accounts", route: "/settings/accounts", icon: "accounts" },
		{ label: "Categories", route: "/settings/categories", icon: "categories" },
		{ label: "Data", route: "/settings/data", icon: "data" },
	];
}
