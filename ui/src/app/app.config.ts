import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZonelessChangeDetection } from "@angular/core";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { provideNativeDateAdapter } from "@angular/material/core";
import { provideRouter } from "@angular/router";

import { routes } from "./app.routes";
import { errorInterceptor } from "@shared/interceptors/error.interceptor";
import { loadingInterceptor } from "@shared/interceptors/loading.interceptor";

export const appConfig: ApplicationConfig = {
	providers: [
		provideBrowserGlobalErrorListeners(),
		provideZonelessChangeDetection(),
		provideRouter(routes),
		provideHttpClient(withInterceptors([errorInterceptor, loadingInterceptor])),
		provideNativeDateAdapter(),
	],
};
