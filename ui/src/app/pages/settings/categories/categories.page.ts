import { ChangeDetectionStrategy, Component, ViewEncapsulation } from "@angular/core";

/** Placeholder for the category list: the management surface is a later unit, so this page holds no state. */
@Component({
	selector: "penniless-settings-categories",
	templateUrl: "./categories.page.html",
	styleUrl: "./categories.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SettingsCategoriesPage {}
