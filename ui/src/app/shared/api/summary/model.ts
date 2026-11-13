export interface SummaryResponse {
	start: string;
	end: string;
	totalInCents: number;
	totalOutCents: number;
	netCents: number;
	cashTotalCents: number;
	netWorthCents: number;
	transactionCount: number;
}
