export interface AccountResponse {
	connectionId: string;
	accountId: string;
	connectionName: string;
	name: string;
	currency: string;
	balanceCents: number;
	availableBalanceCents: number | null;
	balanceDate: string;
	includeInCash: boolean;
}

export interface AccountUpdateContract {
	includeInCash: boolean;
}
