import { Injectable } from "@angular/core";

/**
 * Single facade over every HTTP service. Callers reach an endpoint as `<component>.<tier>`, mirroring
 * the API. Tiers arrive with the features that need them: `setup`, `accounts`, `transactions`,
 * `summary`, `categories`.
 */
@Injectable({ providedIn: "root" })
export class ApiClientService {}
