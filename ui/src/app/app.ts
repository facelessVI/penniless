import { ChangeDetectionStrategy, Component, ViewEncapsulation, inject, signal } from "@angular/core";
import { Router, RouterOutlet } from "@angular/router";
import { StatusResponse } from "@shared/api/setup/model";
import { StatusService } from "@shared/services/status.service";

@Component({
	selector: "app-root",
	imports: [RouterOutlet],
	templateUrl: "./app.html",
	styleUrl: "./app.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class App {
	private readonly router = inject(Router);
	private readonly statusService = inject(StatusService);

	/* Nothing mounts until the connection status is known, so an unconnected visit never flashes the dashboard. */
	protected readonly resolved = signal(false);

	constructor() {
		this.resolveInitialRoute();
	}

	private resolveInitialRoute(): void {
		this.statusService.refresh().subscribe({
			next: (status) => {
				this.resolved.set(true);
				this.redirectIfNeeded(status);
			},
			error: () => {
				/* The error banner already reports it; show whatever route was asked for. */
				this.resolved.set(true);
			},
		});
	}

	private redirectIfNeeded(status: StatusResponse): void {
		const onSetupRoute = this.router.url.startsWith("/setup");

		if (!status.connected && !onSetupRoute) {
			this.router.navigate(["/setup"], { replaceUrl: true });

			return;
		}

		if (status.connected && onSetupRoute) {
			this.router.navigate(["/dashboard"], { replaceUrl: true });
		}
	}
}
