export interface AccountResponse {
	connection_id: string;
	account_id: string;
	connection_name: string;
	name: string;
	currency: string;
	balance_cents: number;
	available_balance_cents: number | null;
	balance_date: string;
	include_in_cash: boolean;
}

export interface AccountUpdateContract {
	include_in_cash: boolean;
}
