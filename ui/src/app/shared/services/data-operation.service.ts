import { Injectable, computed, signal } from "@angular/core";

/**
 * The actions that take seconds and rewrite stored rows, so two of them must never overlap: a refresh,
 * a backfill and a connect all spend one of the 24 daily SimpleFIN `/accounts` calls, and re-applying
 * rules must not run while a fetch is rewriting the same transactions.
 */
export type DataOperation = "refresh" | "backfill" | "connect" | "apply-rules";

/**
 * The one piece of loading state the app shares, because it is the one piece that is genuinely global.
 * Everything else belongs to the thing that started it: a page's first paint, a dialog's save and a
 * keyword fetch are local to a control, and one app-wide boolean cannot answer "is the thing I am
 * showing still loading?".
 */
@Injectable({ providedIn: "root" })
export class DataOperationService {
	private readonly operation = signal<DataOperation | null>(null);

	readonly active = this.operation.asReadonly();
	readonly busy = computed(() => this.operation() !== null);

	start(operation: DataOperation): void {
		this.operation.set(operation);
	}

	stop(): void {
		this.operation.set(null);
	}
}
