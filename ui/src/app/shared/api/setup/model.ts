export interface ConnectContract {
	setupToken: string;
	replace: boolean;
}

export interface ConnectResponse {
	connected: boolean;
	accountCount: number;
	backfillWindows: number;
	transactionsStored: number;
}

export type DataSource = "live" | "fixture";

export type FetchStatus = "ok" | "error";

export interface StatusResponse {
	connected: boolean;
	source: DataSource;
	credentialClaimedAt: string | null;
	accountCount: number;
	transactionCount: number;
	lastFetchStatus: FetchStatus | null;
	lastFetchedAt: string | null;
	lastFetchErrorCode: string | null;
	refreshAllowed: boolean;
	nextRefreshAllowedAt: string | null;
	refreshMinIntervalHours: number;
}

export interface RefreshResponse {
	fetched: boolean;
	accountCount: number;
	transactionsStored: number;
	fetchedAt: string;
	refreshAllowed: boolean;
	nextRefreshAllowedAt: string | null;
}

export interface BackfillContract {
	months: number;
}

export interface BackfillResponse {
	windows: number;
	transactionsStored: number;
}
