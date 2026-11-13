"""The values the category rules and the category list are built on."""

UNCATEGORIZED_CATEGORY = "Uncategorized"
TRANSFERS_CATEGORY = "Transfers"
PROTECTED_CATEGORIES = (TRANSFERS_CATEGORY, UNCATEGORIZED_CATEGORY)
PROTECTED_CATEGORY_REASONS = {
    TRANSFERS_CATEGORY: f"{TRANSFERS_CATEGORY!r} decides which rows are transfers",
    UNCATEGORIZED_CATEGORY: f"{UNCATEGORIZED_CATEGORY!r} is where unmatched transactions land",
}
MAXIMUM_CATEGORY_NAME_LENGTH = 40

MATCH_TYPE_EXACT = "exact"
MATCH_TYPE_CONTAINS = "contains"
MATCH_TYPES = (MATCH_TYPE_EXACT, MATCH_TYPE_CONTAINS)

KEYWORD_SOURCE_DESCRIPTION = "description"
KEYWORD_SOURCE_RULE = "rule"
KEYWORD_SOURCE_TOKEN = "token"
KEYWORD_SOURCE_PHRASE = "phrase"
MINIMUM_KEYWORD_TOKEN_LENGTH = 3

# Words that say how a charge arrived rather than who it was to. Kept short on purpose: dropping a
# merchant word hides the keyword the user actually wants.
KEYWORD_NOISE_TOKENS = frozenset(
    {
        "ach",
        "amex",
        "autopay",
        "card",
        "debit",
        "discover",
        "mastercard",
        "payment",
        "pending",
        "pmts",
        "pos",
        "purchase",
        "ref",
        "recurring",
        "visa",
    }
)
