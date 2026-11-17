import { ChangeDetectionStrategy, Component, ViewEncapsulation, input } from "@angular/core";

export type NavIcon = "dashboard" | "transactions" | "accounts" | "categories" | "data";

@Component({
	selector: "app-main-layout-nav-icon",
	template: `
		<svg
			class="sidebar-item-icon"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="1.5"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			@switch (icon()) {
				@case ("dashboard") {
					<rect x="3" y="3" width="7" height="7" rx="1.5" />
					<rect x="14" y="3" width="7" height="7" rx="1.5" />
					<rect x="3" y="14" width="7" height="7" rx="1.5" />
					<rect x="14" y="14" width="7" height="7" rx="1.5" />
				}
				@case ("transactions") {
					<path d="M4 7h16" />
					<path d="M8 3 4 7l4 4" />
					<path d="M20 17H4" />
					<path d="M16 21l4-4-4-4" />
				}
				@case ("accounts") {
					<rect x="2.5" y="5" width="19" height="14" rx="2.5" />
					<path d="M2.5 10h19" />
				}
				@case ("categories") {
					<path
						d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0l-7.2-7.2a2 2 0 0 1-.6-1.4V4.5A1.5 1.5 0 0 1 4.3 3H11.9a2 2 0 0 1 1.4.6l7.3 7.3a2 2 0 0 1 0 2.5z"
					/>
					<circle cx="7.5" cy="7.5" r="1.25" />
				}
				@case ("data") {
					<ellipse cx="12" cy="6" rx="8" ry="3" />
					<path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" />
					<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
				}
			}
		</svg>
	`,
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class MainLayoutNavIconComponent {
	readonly icon = input.required<NavIcon>();
}
