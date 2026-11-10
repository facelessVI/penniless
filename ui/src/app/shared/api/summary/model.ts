export interface SummaryResponse {
	start: string;
	end: string;
	total_in_cents: number;
	total_out_cents: number;
	net_cents: number;
	cash_total_cents: number;
	uncategorized_count: number;
	transaction_count: number;
}
