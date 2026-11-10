import { HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { catchError, throwError } from "rxjs";
import { ErrorService, SUPPRESS_ERROR_BANNER } from "@shared/services/error.service";

export const errorInterceptor: HttpInterceptorFn = (request, next) => {
	const errorService = inject(ErrorService);
	const suppressErrorBanner = request.context.get(SUPPRESS_ERROR_BANNER);

	return next(request).pipe(
		catchError((error: unknown) => {
			if (!suppressErrorBanner) {
				errorService.setError(error);
			}

			return throwError(() => error);
		}),
	);
};
