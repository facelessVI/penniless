import { Injectable, computed, inject, signal } from "@angular/core";
import { ApiClientService } from "@shared/api/api-client.service";
import { ConnectContract } from "@shared/api/setup/model";
import { extractErrorMessage } from "@shared/services/error.service";
import { DataOperationService } from "@shared/services/data-operation.service";
import { StatusService } from "@shared/services/status.service";

@Injectable({ providedIn: "root" })
export class SetupPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly statusService = inject(StatusService);
	private readonly dataOperation = inject(DataOperationService);

	/** Claiming a token also runs the 12-month backfill, so it is the same long shared state. */
	readonly connecting = computed(() => this.dataOperation.active() === "connect");
	readonly errorMessage = signal<string | null>(null);

	get alreadyConnected(): boolean {
		return this.statusService.connected();
	}

	connect(setupToken: string, onConnected: () => void): void {
		const contract: ConnectContract = {
			setup_token: setupToken,
			replace: this.statusService.connected(),
		};

		this.dataOperation.start("connect");
		this.errorMessage.set(null);

		this.apiClient.setup.standard.claimSetupToken(contract).subscribe({
			next: () => {
				this.dataOperation.stop();
				this.statusService.refresh().subscribe({ next: () => onConnected() });
			},
			error: (error: unknown) => {
				this.dataOperation.stop();
				this.errorMessage.set(extractErrorMessage(error));
			},
		});
	}

	reset(): void {
		this.errorMessage.set(null);
	}
}
