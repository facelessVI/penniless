import { Injectable, inject, signal } from "@angular/core";
import { ApiClientService } from "@shared/api/api-client.service";
import { ConnectContract } from "@shared/api/setup/model";
import { extractErrorMessage } from "@shared/services/error.service";
import { StatusService } from "@shared/services/status.service";

@Injectable({ providedIn: "root" })
export class SetupPageService {
	private readonly apiClient = inject(ApiClientService);
	private readonly statusService = inject(StatusService);

	readonly connecting = signal(false);
	readonly errorMessage = signal<string | null>(null);

	get alreadyConnected(): boolean {
		return this.statusService.connected();
	}

	connect(setupToken: string, onConnected: () => void): void {
		const contract: ConnectContract = {
			setup_token: setupToken,
			replace: this.statusService.connected(),
		};

		this.connecting.set(true);
		this.errorMessage.set(null);

		this.apiClient.setup.standard.claimSetupToken(contract).subscribe({
			next: () => {
				this.connecting.set(false);
				this.statusService.refresh().subscribe({ next: () => onConnected() });
			},
			error: (error: unknown) => {
				this.connecting.set(false);
				this.errorMessage.set(extractErrorMessage(error));
			},
		});
	}

	reset(): void {
		this.connecting.set(false);
		this.errorMessage.set(null);
	}
}
