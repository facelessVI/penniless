"""Request state that has to be loaded before a handler runs.

`get_connection` stays in `db` because a connection is the app's basic unit of work. What
lives here is loaded, validated state: anything a handler needs before it can answer, and
anything a broken database row should fail early rather than let through.
"""

import sqlite3
from typing import Annotated

from fastapi import Depends

from app.categories import service
from app.categories.matching import CategoryRules
from app.common import db


def category_rules(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> CategoryRules:
    """The stored rules and categories, validated. A broken row fails the request, not a fetch."""
    return service.get_category_rules(connection)
