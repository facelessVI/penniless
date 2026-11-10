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
