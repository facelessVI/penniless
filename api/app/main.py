"""FastAPI entry point. Local-only: uvicorn binds 127.0.0.1, no CORS, no auth."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.config import settings
from app.routers import accounts, setup

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    if settings.source == "fixture":
        db.reset_database()
        logger.info("rebuilt fixture database at %s", settings.database_path)

    connection = db.connect()

    try:
        applied_filenames = db.run_migrations(connection)
    finally:
        connection.close()

    logger.info(
        "database ready at %s, applied migrations: %s",
        settings.database_path,
        ", ".join(applied_filenames) or "none",
    )

    yield


app = FastAPI(title="Penniless API", lifespan=lifespan)

app.include_router(setup.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
