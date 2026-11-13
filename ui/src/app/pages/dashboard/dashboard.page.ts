import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, ViewEncapsulation, computed, inject } from "@angular/core";
import { DatePipe } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatSortModule, Sort } from "@angular/material/sort";
import { MatTableModule } from "@angular/material/table";
import { RouterLink } from "@angular/router";
import { AccountResponse } from "@shared/api/accounts/model";
import { DashboardPageService, DashboardSortColumn, DashboardSortDirection } from "./dashboard.service";

@Component({
	selector: "penniless-dashboard",
	imports: [DatePipe, RouterLink, MatButtonModule, MatSlideToggleModule, MatSortModule, MatTableModule],
	templateUrl: "./dashboard.page.html",
	styleUrl: "./dashboard.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class DashboardPage implements OnInit, OnDestroy {
	protected readonly service = inject(DashboardPageService);
	protected readonly accountColumns = ["name", "connection", "balance", "cash"];

	protected readonly refreshBlockedReason = computed(() => {
		const status = this.service.status();

		if (status === null || status.refreshAllowed || status.nextRefreshAllowedAt === null) {
			return null;
		}

		return `Refresh is paused until ${new Date(status.nextRefreshAllowedAt).toLocaleString()}, the minimum gap of ${status.refreshMinIntervalHours} hours.`;
	});

	protected readonly canRefresh = computed(() => this.service.status()?.refreshAllowed ?? false);

	ngOnInit(): void {
		this.service.load();
	}

	ngOnDestroy(): void {
		this.service.reset();
	}

	protected onCashToggle(account: AccountResponse, includeInCash: boolean): void {
		this.service.setIncludeInCash(account, includeInCash);
	}

	protected onSortChange(event: Sort): void {
		const column = event.direction === "" ? null : (event.active as DashboardSortColumn);
		const direction = event.direction === "" ? null : (event.direction as DashboardSortDirection);

		this.service.setSort(column, direction);
	}
}
