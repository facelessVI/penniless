"""Request state the categories endpoints need before a handler runs.

Only the category router uses this, which is why it lives in this folder rather than in
`common`.
"""

import sqlite3
from typing import Annotated

from fastapi import Depends

from app.categories.model.categories_model import CategoryRules
from app.categories.service import categories_service as service
from app.common import db


def category_rules(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoryRules:
    """The stored rules and categories, validated. A broken row fails the request, not a fetch."""
    return service.get_category_rules(connection)
