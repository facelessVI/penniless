import { ChangeDetectionStrategy, Component, ViewEncapsulation } from "@angular/core";

@Component({
	selector: "penniless-dashboard",
	templateUrl: "./dashboard.page.html",
	styleUrl: "./dashboard.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class DashboardPage {}
