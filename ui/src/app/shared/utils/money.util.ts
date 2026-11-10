const CENTS_PER_UNIT = 100;
const DEFAULT_CURRENCY = "USD";

export function formatCents(cents: number, currency: string = DEFAULT_CURRENCY): string {
	const amount = cents / CENTS_PER_UNIT;

	try {
		return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
	} catch {
		// Custom currencies are URLs rather than ISO codes, so they cannot be formatted.
		return `${amount.toFixed(2)} ${currency}`;
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
