/** Local calendar date as `YYYY-MM-DD`. Never `toISOString`, which would shift across time zones. */
export function toIsoDate(date: Date): string {
	const year = date.getFullYear();
	const month = `${date.getMonth() + 1}`.padStart(2, "0");
	const day = `${date.getDate()}`.padStart(2, "0");

	return `${year}-${month}-${day}`;
}

export function firstDayOfMonth(date: Date, monthsBack = 0): Date {
	return new Date(date.getFullYear(), date.getMonth() - monthsBack, 1);
}

export function lastDayOfMonth(date: Date): Date {
	return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

/** Parses `YYYY-MM-DD` into a local calendar date, without the UTC shift of `new Date(string)`. */
export function fromIsoDate(value: string | null | undefined): Date | null {
	if (!value) {
		return null;
	}

	const parts = value.split("-").map(Number);

	if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
		return null;
	}

	return new Date(parts[0], parts[1] - 1, parts[2]);
}

const DATE_MASK_MONTH_DIGITS = 2;
const DATE_MASK_DAY_DIGITS = 4;
const DATE_MASK_DIGIT_COUNT = 8;

const ISO_DATE_PATTERN = /^(\d{4})-(\d{1,2})-(\d{1,2})$/;
const SLASH_DATE_PATTERN = /^\d{1,2}\/\d{1,2}\/(\d{2}|\d{4})$/;

/**
 * Rewrites digits typed into a date field as `MM/DD/YYYY`, so the entry stays readable while it is
 * being typed. Separators are only added once the next digit arrives, which keeps backspace able to
 * remove the last digit instead of re-adding a separator.
 */
export function maskTypedDate(rawValue: string, caret: number): { value: string; caret: number } {
	const trimmed = rawValue.trim();
	const isoMatch = ISO_DATE_PATTERN.exec(trimmed);

	// A pasted ISO date keeps its meaning instead of being read as a run of unordered digits.
	if (isoMatch) {
		const value = `${padDatePart(isoMatch[2])}/${padDatePart(isoMatch[3])}/${isoMatch[1]}`;

		return { value, caret: value.length };
	}

	// A date the user separated themselves, or pasted already formatted, is left as it was typed.
	if (SLASH_DATE_PATTERN.test(trimmed)) {
		return { value: rawValue, caret };
	}

	const digits = rawValue.replace(/\D/g, "").slice(0, DATE_MASK_DIGIT_COUNT);
	const digitsBeforeCaret = Math.min(rawValue.slice(0, caret).replace(/\D/g, "").length, digits.length);

	return {
		value: formatDateDigits(digits),
		caret: formatDateDigits(digits.slice(0, digitsBeforeCaret)).length,
	};
}

function padDatePart(part: string): string {
	return part.padStart(2, "0");
}

function formatDateDigits(digits: string): string {
	const parts = [
		digits.slice(0, DATE_MASK_MONTH_DIGITS),
		digits.slice(DATE_MASK_MONTH_DIGITS, DATE_MASK_DAY_DIGITS),
		digits.slice(DATE_MASK_DAY_DIGITS, DATE_MASK_DIGIT_COUNT),
	].filter((part) => part.length > 0);

	return parts.join("/");
}
