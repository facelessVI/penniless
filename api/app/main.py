"""FastAPI entry point. Local-only: uvicorn binds 127.0.0.1, no CORS, no auth."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.categories import service as category_service
from app.common import db, handlers, migrations
from app.common.config import settings
from app.routers import accounts, categories, setup, transactions

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    # Rules are the only thing a fixture reset keeps, so read them before the file is deleted.
    preserved_rules = db.read_rules_snapshot(settings.database_path) if settings.source == "fixture" else []

    if settings.source == "fixture":
        migrations.reset_database(settings.database_path)
        logger.info("rebuilt fixture database at %s", settings.database_path)

    connection = db.connect()

    try:
        applied_filenames = migrations.run_migrations(connection)
        restored_rules = db.restore_rules(connection, preserved_rules)

        # Category data is validated after migrations and before the first fetch: broken rules must
        # fail startup rather than a fetch, because SimpleFIN calls cost quota.
        rules = category_service.get_category_rules(connection)
    finally:
        connection.close()

    logger.info("categories ready: %d categories, %d rules", len(rules.categories), len(rules.rules))

    if restored_rules:
        logger.info("kept %d learned rule(s) across the fixture reset", restored_rules)

    logger.info(
        "database ready at %s, applied migrations: %s",
        settings.database_path,
        ", ".join(applied_filenames) or "none",
    )

    yield


app = FastAPI(title="Penniless API", lifespan=lifespan)

handlers.register_exception_handlers(app)

app.include_router(setup.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
