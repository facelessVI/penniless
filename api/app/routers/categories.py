"""The category list, creating, renaming and deleting categories, and re-applying the rules."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app import categorize, db
from app.schemas import (
    ApplyCategoriesResponse,
    CategoriesResponse,
    CategoryDeleteResponse,
    CategoryItem,
    CategoryNameRequest,
)

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=CategoriesResponse)
def list_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    categorize.load_rules(connection)

    return to_categories_response(connection)


@router.post("/categories", response_model=CategoriesResponse, status_code=201)
def create_category(
    request: CategoryNameRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    categorize.create_category(connection, request.name)

    return to_categories_response(connection)


@router.patch("/categories/{name}", response_model=CategoriesResponse)
def rename_category(
    name: str,
    request: CategoryNameRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    categorize.rename_category(connection, name, request.name)

    return to_categories_response(connection)


@router.delete("/categories/{name}", response_model=CategoryDeleteResponse)
def delete_category(
    name: str,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoryDeleteResponse:
    result = categorize.delete_category(connection, name)
    response = to_categories_response(connection)

    return CategoryDeleteResponse(
        categories=response.categories,
        uncategorized=response.uncategorized,
        moved_transactions=result.moved_transactions,
        deleted_rules=result.deleted_rules,
    )


@router.post("/categories/apply", response_model=ApplyCategoriesResponse)
def apply_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> ApplyCategoriesResponse:
    rules = categorize.load_rules(connection)
    result = categorize.apply_rules(connection, rules)

    return ApplyCategoriesResponse(updated=result.updated, uncategorized=result.uncategorized)


def to_categories_response(connection: sqlite3.Connection) -> CategoriesResponse:
    return CategoriesResponse(
        categories=[to_category_item(summary) for summary in categorize.list_categories(connection)],
        uncategorized=categorize.UNCATEGORIZED_CATEGORY,
    )


def to_category_item(summary: categorize.CategorySummary) -> CategoryItem:
    return CategoryItem(
        name=summary.name,
        position=summary.position,
        transaction_count=summary.transaction_count,
        rule_count=summary.rule_count,
        protected=summary.is_protected,
    )
