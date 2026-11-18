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
	/** Where the account came from: mirrored from the API's own numbering. */
	source: AccountSource;
	labels: string[];
}

/** The API stores an account's origin as a number, so the meaning of a row never rides on a string. */
export const AccountSource = {
	SimpleFin: 1,
	Manual: 2,
} as const;

export type AccountSource = (typeof AccountSource)[keyof typeof AccountSource];

export interface AccountCreateContract {
	name: string;
	balanceCents: number;
	description?: string;
	labels?: string[];
}

export interface AccountUpdateContract {
	displayName?: string;
	description?: string;
	includeInCash?: boolean;
	/** Refused by the API for an account a fetch owns, because the next fetch would overwrite it. */
	balanceCents?: number;
	/** The account's complete set, not a delta. */
	labels?: string[];
}

export const resolvedAccountName = (account: AccountResponse): string => account.displayName ?? account.name;

export const isManualAccount = (account: AccountResponse): boolean => account.source === AccountSource.Manual;

export const accountKeyOf = (connectionId: string, accountId: string): string => `${connectionId}/${accountId}`;

export const accountKey = (account: AccountResponse): string => accountKeyOf(account.connectionId, account.accountId);
