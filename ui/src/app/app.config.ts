import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZonelessChangeDetection } from "@angular/core";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { MAT_NATIVE_DATE_FORMATS, MatDateFormats, provideNativeDateAdapter } from "@angular/material/core";
import { provideRouter } from "@angular/router";

import { routes } from "./app.routes";
import { errorInterceptor } from "@shared/interceptors/error.interceptor";

/** Padded month and day, so a date field reformats to `MM/DD/YYYY` on blur and not `M/D/YYYY`. */
const DATE_FORMATS: MatDateFormats = {
	...MAT_NATIVE_DATE_FORMATS,
	display: {
		...MAT_NATIVE_DATE_FORMATS.display,
		dateInput: { year: "numeric", month: "2-digit", day: "2-digit" },
	},
};

export const appConfig: ApplicationConfig = {
	providers: [
		provideBrowserGlobalErrorListeners(),
		provideZonelessChangeDetection(),
		provideRouter(routes),
		provideHttpClient(withInterceptors([errorInterceptor])),
		provideNativeDateAdapter(DATE_FORMATS),
	],
};
