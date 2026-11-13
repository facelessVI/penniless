"""The category list, creating, renaming and deleting categories, and re-applying the rules."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app import categorize, converters, db
from app.schemas import (
    ApplyCategoriesResponse,
    CategoriesResponse,
    CategoryDeleteResponse,
    CategoryNameRequest,
)

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=CategoriesResponse)
def list_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    categorize.load_rules(connection)

    return converters.to_categories(categorize.list_categories(connection))


@router.post("/categories", response_model=CategoriesResponse, status_code=201)
def create_category(
    request: CategoryNameRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    categorize.create_category(connection, request.name)

    return converters.to_categories(categorize.list_categories(connection))


@router.patch("/categories/{name}", response_model=CategoriesResponse)
def rename_category(
    name: str,
    request: CategoryNameRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    categorize.rename_category(connection, name, request.name)

    return converters.to_categories(categorize.list_categories(connection))


@router.delete("/categories/{name}", response_model=CategoryDeleteResponse)
def delete_category(
    name: str,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoryDeleteResponse:
    result = categorize.delete_category(connection, name)
    categories = converters.to_categories(categorize.list_categories(connection))

    return converters.to_category_delete(categories, result)


@router.post("/categories/apply", response_model=ApplyCategoriesResponse)
def apply_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> ApplyCategoriesResponse:
    rules = categorize.load_rules(connection)
    result = categorize.apply_rules(connection, rules)

    return converters.to_apply_result(result)
