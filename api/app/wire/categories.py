"""The category list and the name a create or rename carries."""

from app.wire.base import ApiModel


class CategoryItem(ApiModel):
    name: str
    position: int
    transaction_count: int
    rule_count: int
    protected: bool


class CategoriesResponse(ApiModel):
    categories: list[CategoryItem]
    uncategorized: str


class CategoryNameRequest(ApiModel):
    name: str


class CategoryDeleteResponse(CategoriesResponse):
    moved_transactions: int
    deleted_rules: int


class ApplyCategoriesResponse(ApiModel):
    updated: int
    uncategorized: int
