"""Category domain results into wire models.

No I/O and no formatting decisions: every field is spelled out, so a renamed column or a
dropped field fails here rather than reaching the client.
"""

from collections.abc import Sequence

from app.categories.api.categories_api import (
    ApplyCategoriesResponse,
    CategoriesResponse,
    CategoryDeleteResponse,
    CategoryItem,
)
from app.categories.constants.categories_constants import UNCATEGORIZED_CATEGORY
from app.categories.model.categories_model import ApplyResult, CategoryDeleteResult, CategoryRow


def to_category_item(row: CategoryRow) -> CategoryItem:
    return CategoryItem(
        name=row.name,
        position=row.position,
        transaction_count=row.transaction_count,
        rule_count=row.rule_count,
        protected=row.is_protected,
    )


def to_categories(rows: Sequence[CategoryRow]) -> CategoriesResponse:
    return CategoriesResponse(
        categories=[to_category_item(row) for row in rows],
        uncategorized=UNCATEGORIZED_CATEGORY,
    )


def to_category_delete(categories: CategoriesResponse, result: CategoryDeleteResult) -> CategoryDeleteResponse:
    return CategoryDeleteResponse(
        categories=categories.categories,
        uncategorized=categories.uncategorized,
        moved_transactions=result.moved_transactions,
        deleted_rules=result.deleted_rules,
    )


def to_apply_result(result: ApplyResult) -> ApplyCategoriesResponse:
    return ApplyCategoriesResponse(updated=result.updated, uncategorized=result.uncategorized)
