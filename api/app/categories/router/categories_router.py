"""The category list, creating, renaming and deleting categories, and re-applying the rules."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.categories.api.categories_api import (
    ApplyCategoriesResponse,
    CategoriesResponse,
    CategoryDeleteResponse,
    CategoryNameRequest,
)
from app.categories.converter import categories_converter as converter
from app.categories.dependencies.categories_dependencies import category_rules
from app.categories.model.categories_model import CategoryRules
from app.categories.service import categories_service as service
from app.common import db

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=CategoriesResponse)
def list_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    _rules: Annotated[CategoryRules, Depends(category_rules)],
) -> CategoriesResponse:
    return converter.to_categories(service.list_categories(connection))


@router.post("/categories", response_model=CategoriesResponse, status_code=201)
def create_category(
    request: CategoryNameRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    return converter.to_categories(service.create_category(connection, request.name))


@router.patch("/categories/{name}", response_model=CategoriesResponse)
def rename_category(
    name: str,
    request: CategoryNameRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoriesResponse:
    return converter.to_categories(service.rename_category(connection, name, request.name))


@router.delete("/categories/{name}", response_model=CategoryDeleteResponse)
def delete_category(
    name: str,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoryDeleteResponse:
    return converter.to_category_delete(service.delete_category(connection, name))


@router.post("/categories/apply", response_model=ApplyCategoriesResponse)
def apply_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    rules: Annotated[CategoryRules, Depends(category_rules)],
) -> ApplyCategoriesResponse:
    return converter.to_apply_result(service.apply_rules(connection, rules))
