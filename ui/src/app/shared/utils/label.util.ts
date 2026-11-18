/** One autocomplete row: a label already in the vocabulary, or the name the user is about to create. */
export interface LabelOption {
	value: string;
	create: boolean;
}

/**
 * The labels an account can attach from: every label in use, minus the ones it already carries. An
 * unknown typed name becomes a create row, so one selection does both steps; a name that matches an
 * existing spelling reuses it, so the vocabulary never grows two casings of one grouping.
 */
export function labelOptions(vocabulary: readonly string[], attached: readonly string[], typed: string): LabelOption[] {
	const trimmed = typed.trim();

	if (trimmed === "") {
		return [];
	}

	const spellings = new Map<string, string>();

	for (const label of vocabulary) {
		const key = label.toLowerCase();

		if (!spellings.has(key)) {
			spellings.set(key, label);
		}
	}

	const matching = [...spellings.entries()]
		.filter(([key]) => key.includes(trimmed.toLowerCase()))
		.sort(([first], [second]) => first.localeCompare(second));

	if (matching.length === 0) {
		return [{ value: trimmed, create: true }];
	}

	const attachedKeys = new Set(attached.map((label) => label.toLowerCase()));

	return matching.filter(([key]) => !attachedKeys.has(key)).map(([, label]) => ({ value: label, create: false }));
}
