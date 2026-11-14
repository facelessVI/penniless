"""What can go wrong while managing categories and rules. `handlers` maps each to a status."""


class CategoryRulesError(ValueError):
    """The category data is wrong. Raised at startup too, so it cannot cost a fetch."""


class UnknownTransactionError(LookupError):
    """The composite key names no stored transaction."""


class CategoryNameError(ValueError):
    """A category name is empty, too long, carries a slash, or is already taken."""


class ProtectedCategoryError(ValueError):
    """The category is named in code, so renaming or deleting it would change behavior."""


class UnknownCategoryError(LookupError):
    """No category has that name."""


class RulePatternError(ValueError):
    """A keyword is blank, has an unknown match type, or does not occur in the description shown."""


class UnknownRuleError(LookupError):
    """Nothing to delete: no rule of that type carries that keyword."""


class CategoryOrderError(ValueError):
    """A reorder is not every stored category exactly once, so it cannot be a display order."""
