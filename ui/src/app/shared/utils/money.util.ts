const CENTS_PER_UNIT = 100;
const DEFAULT_CURRENCY = "USD";

/** An amount typed by hand: an optional sign, thousands separators, and at most two decimals. */
const TYPED_MONEY_PATTERN = /^(-?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?$/;

/** Cents back to the plain `250.00` shape a money field edits, with no symbol or grouping. */
export function centsToInput(cents: number): string {
	return (cents / CENTS_PER_UNIT).toFixed(2);
}

/** Read a typed amount as whole cents, or `null` when it is not one. The parts are read as integers
 * so a typed `0.29` cannot pick up float drift on the way to cents. */
export function parseCents(value: string): number | null {
	const match = TYPED_MONEY_PATTERN.exec(value.trim().replace(/^\$\s*/, ""));

	if (match === null) {
		return null;
	}

	const [, sign, whole, fraction = ""] = match;
	const cents = Number(whole.replaceAll(",", "")) * CENTS_PER_UNIT + Number(fraction.padEnd(2, "0"));

	return sign === "-" ? -cents : cents;
}

export function formatCents(cents: number, currency: string = DEFAULT_CURRENCY): string {
	const amount = cents / CENTS_PER_UNIT;
	// Some institutions send no currency at all. A blank code is a missing value, not a custom
	// currency, so it falls back to the default instead of the unformatted path below.
	const currencyCode = currency.trim() || DEFAULT_CURRENCY;

	try {
		return new Intl.NumberFormat("en-US", { style: "currency", currency: currencyCode }).format(amount);
	} catch {
		// Custom currencies are URLs rather than ISO codes, so they cannot be formatted.
		return `${amount.toFixed(2)} ${currencyCode}`;
	}
}

export function formatSignedCents(cents: number, currency: string = DEFAULT_CURRENCY): string {
	const formatted = formatCents(Math.abs(cents), currency);

	if (cents < 0) {
		return `-${formatted}`;
	}

	if (cents > 0) {
		return `+${formatted}`;
	}

	return formatted;
}
