"""FastAPI entry point. Local-only: uvicorn binds 127.0.0.1, no CORS, no auth."""

from fastapi import FastAPI

from app.routers import setup

app = FastAPI(title="Penniless API")

app.include_router(setup.router, prefix="/api")
