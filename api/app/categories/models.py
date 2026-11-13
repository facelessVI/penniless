"""What the category service returns. Plain frozen data: no I/O and no wire concerns."""

from dataclasses import dataclass

from app.categories.constants import PROTECTED_CATEGORIES
from app.categories.matching import Rule


@dataclass(frozen=True)
class AssignResult:
    description: str
    match_type: str
    pattern: str
    category: str
    matched: int
    updated: int
    rule_deleted: bool


@dataclass(frozen=True)
class KeywordOption:
    match_type: str
    pattern: str
    category: str | None
    source: str
    matched: int


@dataclass(frozen=True)
class KeywordOptions:
    description: str
    effective_rule: Rule | None
    options: tuple[KeywordOption, ...]


@dataclass(frozen=True)
class ApplyResult:
    updated: int
    uncategorized: int


@dataclass(frozen=True)
class CategorySummary:
    name: str
    position: int
    transaction_count: int
    rule_count: int

    @property
    def is_protected(self) -> bool:
        return self.name in PROTECTED_CATEGORIES


@dataclass(frozen=True)
class CategoryDeleteResult:
    moved_transactions: int
    deleted_rules: int
