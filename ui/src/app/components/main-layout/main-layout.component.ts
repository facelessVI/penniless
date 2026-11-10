import { ChangeDetectionStrategy, Component, ViewEncapsulation, inject } from "@angular/core";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { ErrorService } from "@shared/services/error.service";
import { LoadingService } from "@shared/services/loading.service";

export interface NavLink {
	label: string;
	route: string;
}

@Component({
	selector: "app-main-layout",
	imports: [RouterOutlet, RouterLink, RouterLinkActive],
	templateUrl: "./main-layout.component.html",
	styleUrl: "./main-layout.component.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class MainLayoutComponent {
	protected readonly errorService = inject(ErrorService);
	protected readonly loadingService = inject(LoadingService);

	protected readonly links: NavLink[] = [
		{ label: "Dashboard", route: "/dashboard" },
		{ label: "Transactions", route: "/transactions" },
	];
}
