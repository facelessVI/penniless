import { ChangeDetectionStrategy, Component, ViewEncapsulation } from "@angular/core";

@Component({
	selector: "penniless-setup",
	templateUrl: "./setup.page.html",
	styleUrl: "./setup.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SetupPage {}
