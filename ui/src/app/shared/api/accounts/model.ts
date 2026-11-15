export interface AccountResponse {
	connectionId: string;
	accountId: string;
	connectionName: string;
	name: string;
	displayName: string | null;
	description: string | null;
	currency: string;
	balanceCents: number;
	availableBalanceCents: number | null;
	balanceDate: string;
	includeInCash: boolean;
	labels: string[];
}

export interface AccountUpdateContract {
	displayName?: string;
	description?: string;
	includeInCash?: boolean;
	/** The account's complete set, not a delta. */
	labels?: string[];
}

export const resolvedAccountName = (account: AccountResponse): string => account.displayName ?? account.name;

export const accountKeyOf = (connectionId: string, accountId: string): string => `${connectionId}/${accountId}`;

export const accountKey = (account: AccountResponse): string => accountKeyOf(account.connectionId, account.accountId);
