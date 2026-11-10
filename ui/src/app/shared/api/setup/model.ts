export interface ConnectContract {
	setup_token: string;
	replace: boolean;
}

export interface ConnectResponse {
	connected: boolean;
	account_count: number;
	backfill_windows: number;
	transactions_stored: number;
}

export type DataSource = "live" | "fixture";

export type FetchStatus = "ok" | "error";

export interface StatusResponse {
	connected: boolean;
	source: DataSource;
	credential_claimed_at: string | null;
	account_count: number;
	transaction_count: number;
	last_fetch_status: FetchStatus | null;
	last_fetched_at: string | null;
	last_fetch_error_code: string | null;
	refresh_allowed: boolean;
	next_refresh_allowed_at: string | null;
	refresh_min_interval_hours: number;
}

export interface RefreshResponse {
	fetched: boolean;
	account_count: number;
	transactions_stored: number;
	fetched_at: string;
	refresh_allowed: boolean;
	next_refresh_allowed_at: string | null;
}

export interface BackfillContract {
	months: number;
}

export interface BackfillResponse {
	windows: number;
	transactions_stored: number;
}
