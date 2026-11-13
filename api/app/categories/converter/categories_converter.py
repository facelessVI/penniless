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
from app.categories.model.categories_model import ApplyResult, Category, CategoryDeleteResult


def to_category_item(category: Category) -> CategoryItem:
    return CategoryItem(
        name=category.name,
        position=category.position,
        transaction_count=category.transaction_count,
        rule_count=category.rule_count,
        protected=category.is_protected,
    )


def to_categories(categories: Sequence[Category]) -> CategoriesResponse:
    return CategoriesResponse(
        categories=[to_category_item(category) for category in categories],
        uncategorized=UNCATEGORIZED_CATEGORY,
    )


def to_category_delete(result: CategoryDeleteResult) -> CategoryDeleteResponse:
    categories = to_categories(result.categories)

    return CategoryDeleteResponse(
        categories=categories.categories,
        uncategorized=categories.uncategorized,
        moved_transactions=result.moved_transactions,
        deleted_rules=result.deleted_rules,
    )


def to_apply_result(result: ApplyResult) -> ApplyCategoriesResponse:
    return ApplyCategoriesResponse(updated=result.updated, uncategorized=result.uncategorized)
