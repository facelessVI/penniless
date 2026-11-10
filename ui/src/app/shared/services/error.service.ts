import { HttpContextToken, HttpErrorResponse } from "@angular/common/http";
import { Injectable, signal } from "@angular/core";

export const SUPPRESS_ERROR_BANNER = new HttpContextToken<boolean>(() => false);

export interface FormattedError {
	status: number;
	message: string;
}

const DEFAULT_ERROR_DURATION_MS = 5000;
const UNKNOWN_ERROR_MESSAGE = "An unknown error has occurred.";

function getFallbackMessage(status: number): string {
	if (status === 0) {
		return "Unable to reach the server. Check your connection and try again.";
	}

	return `An unknown error has occurred (${status}).`;
}

/* FastAPI reports problems as `detail`; this app's own envelopes would use `error`. */
function getMessageFromBody(error: HttpErrorResponse): string | null {
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

/** The message a person should read for any thrown value, whether or not it reached the banner. */
export function extractErrorMessage(error: unknown): string {
	if (error instanceof HttpErrorResponse) {
		return getMessageFromBody(error) ?? getFallbackMessage(error.status);
	}

	if (error instanceof Error) {
		return error.message;
	}

	return UNKNOWN_ERROR_MESSAGE;
}

@Injectable({ providedIn: "root" })
export class ErrorService {
	private readonly activeErrorState = signal<FormattedError | null>(null);

	readonly activeError = this.activeErrorState.asReadonly();

	private dismissTimer: ReturnType<typeof setTimeout> | null = null;

	setError(error: unknown, durationMs: number = DEFAULT_ERROR_DURATION_MS): FormattedError {
		const status = error instanceof HttpErrorResponse ? error.status : 0;
		const formattedError: FormattedError = { status, message: extractErrorMessage(error) };

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

	private clearDismissTimer(): void {
		if (this.dismissTimer !== null) {
			clearTimeout(this.dismissTimer);
			this.dismissTimer = null;
		}
	}
}
