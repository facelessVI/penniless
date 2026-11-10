"""The category list and re-applying the rules file over stored rows."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app import categorize, db
from app.schemas import ApplyCategoriesResponse, CategoriesResponse

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=CategoriesResponse)
def list_categories() -> CategoriesResponse:
    try:
        rules = categorize.load_rules()
    except categorize.CategoryConfigError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return CategoriesResponse(categories=list(rules.categories), uncategorized=categorize.UNCATEGORIZED_CATEGORY)


@router.post("/categories/apply", response_model=ApplyCategoriesResponse)
def apply_categories(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> ApplyCategoriesResponse:
    try:
        rules = categorize.load_rules()
    except categorize.CategoryConfigError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    result = categorize.apply_rules(connection, rules)

    return ApplyCategoriesResponse(updated=result.updated, uncategorized=result.uncategorized)
