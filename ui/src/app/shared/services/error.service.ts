import { HttpContextToken, HttpErrorResponse } from "@angular/common/http";
import { Injectable, signal } from "@angular/core";

export const SUPPRESS_ERROR_BANNER = new HttpContextToken<boolean>(() => false);

export interface FormattedError {
	status: number;
	message: string;
}

const DEFAULT_ERROR_DURATION_MS = 5000;

@Injectable({ providedIn: "root" })
export class ErrorService {
	private readonly activeErrorState = signal<FormattedError | null>(null);

	readonly activeError = this.activeErrorState.asReadonly();

	private dismissTimer: ReturnType<typeof setTimeout> | null = null;

	setError(error: unknown, durationMs: number = DEFAULT_ERROR_DURATION_MS): FormattedError {
		const formattedError = this.formatError(error);

		this.clearDismissTimer();
		this.activeErrorState.set(formattedError);

		if (durationMs > 0) {
			this.dismissTimer = setTimeout(() => this.clearError(), durationMs);
		}

		return formattedError;
	}

	clearError(): void {
		this.clearDismissTimer();
		this.activeErrorState.set(null);
	}

	private formatError(error: unknown): FormattedError {
		if (error instanceof HttpErrorResponse) {
			const status = error.status;
			const message = this.getMessageFromBody(error) ?? this.getFallbackMessage(status);

			return { status, message };
		}

		if (error instanceof Error) {
			return { status: 0, message: error.message };
		}

		return { status: 0, message: "An unknown error has occurred." };
	}

	private getFallbackMessage(status: number): string {
		if (status === 0) {
			return "Unable to reach the server. Check your connection and try again.";
		}

		return `An unknown error has occurred (${status}).`;
	}

	/* FastAPI reports problems as `detail`; the older services here report them as `error`. */
	private getMessageFromBody(error: HttpErrorResponse): string | null {
		const body: unknown = error.error;

		if (body === null || typeof body !== "object") {
			return null;
		}

		const detail = (body as { detail?: unknown }).detail;

		if (typeof detail === "string" && detail.length > 0) {
			return detail;
		}

		const message = (body as { error?: unknown }).error;

		if (typeof message === "string" && message.length > 0) {
			return message;
		}

		return null;
	}

	private clearDismissTimer(): void {
		if (this.dismissTimer !== null) {
			clearTimeout(this.dismissTimer);
			this.dismissTimer = null;
		}
	}
}
