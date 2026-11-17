import { Injectable, signal } from "@angular/core";

const SIDEBAR_COLLAPSED_KEY = "penniless.sidebar-collapsed";

function readStoredCollapsed(): boolean {
	try {
		return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
	} catch {
		return false;
	}
}

function writeStoredCollapsed(collapsed: boolean): void {
	try {
		localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "true" : "false");
	} catch {
		/* A browser that refuses storage keeps the choice for this session only. */
	}
}

@Injectable({ providedIn: "root" })
export class LayoutService {
	readonly sidebarCollapsed = signal(readStoredCollapsed());

	toggleSidebar(): void {
		this.sidebarCollapsed.update((collapsed) => !collapsed);
		writeStoredCollapsed(this.sidebarCollapsed());
	}
}
