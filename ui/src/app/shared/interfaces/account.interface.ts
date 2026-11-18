import { AccountResponse } from "../api/accounts/model";

export interface AccountDialogData {
	/** Every label in use, so a new account can attach one rather than retype it. */
	labelVocabulary: string[];
}

export interface AccountDialogResult {
	account: AccountResponse;
}
