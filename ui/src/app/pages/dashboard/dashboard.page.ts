import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, ViewEncapsulation, computed, inject } from "@angular/core";
import { DatePipe } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatTableModule } from "@angular/material/table";
import { RouterLink } from "@angular/router";
import { AccountResponse } from "@shared/api/accounts/model";
import { DashboardPageService } from "./dashboard.service";

@Component({
	selector: "penniless-dashboard",
	imports: [DatePipe, RouterLink, MatButtonModule, MatSlideToggleModule, MatTableModule],
	templateUrl: "./dashboard.page.html",
	styleUrl: "./dashboard.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class DashboardPage implements OnInit, OnDestroy {
	protected readonly service = inject(DashboardPageService);
	protected readonly accountColumns = ["name", "connection", "balance", "available", "cash"];

	protected readonly refreshBlockedReason = computed(() => {
		const status = this.service.status();

		if (status === null || status.refresh_allowed || status.next_refresh_allowed_at === null) {
			return null;
		}

		return `Refresh is paused until ${new Date(status.next_refresh_allowed_at).toLocaleString()}, the minimum gap of ${status.refresh_min_interval_hours} hours.`;
	});

	protected readonly canRefresh = computed(() => this.service.status()?.refresh_allowed ?? false);

	ngOnInit(): void {
		this.service.load();
	}

	ngOnDestroy(): void {
		this.service.reset();
	}

	protected onCashToggle(account: AccountResponse, includeInCash: boolean): void {
		this.service.setIncludeInCash(account, includeInCash);
	}
}
