import { Injectable, computed, inject, signal } from "@angular/core";
import { Observable, tap } from "rxjs";
import { ApiClientService } from "@shared/api/api-client.service";
import { StatusResponse } from "@shared/api/setup/model";

/** Connection status, resolved once at startup and refreshed after anything that changes it. */
@Injectable({ providedIn: "root" })
export class StatusService {
	private readonly apiClient = inject(ApiClientService);
	private readonly statusState = signal<StatusResponse | null>(null);

	readonly status = this.statusState.asReadonly();
	readonly connected = computed(() => this.statusState()?.connected ?? false);

	refresh(): Observable<StatusResponse> {
		return this.apiClient.setup.standard.getStatus().pipe(tap((status) => this.statusState.set(status)));
	}

	clear(): void {
		this.statusState.set(null);
	}
}
