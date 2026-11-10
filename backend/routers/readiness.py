"""Unauthenticated readiness signal; never expose database or identity details."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from ..config import get_settings
from ..database import engine
from ..models import Base

router = APIRouter()
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@router.get("/readyz", include_in_schema=False)
def readyz():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            schema = (
                connection.execute(text("SELECT current_schema()")).scalar_one()
                if connection.dialect.name == "postgresql"
                else "main"
            )
            if not schema:
                return JSONResponse({"status": "not_ready"}, status_code=503)
            inspector = inspect(connection)
            for name, table in Base.metadata.tables.items():
                if not inspector.has_table(name, schema=schema):
                    return JSONResponse({"status": "not_ready"}, status_code=503)
                if set(table.columns.keys()) - {
                    c["name"] for c in inspector.get_columns(name, schema=schema)
                }:
                    return JSONResponse({"status": "not_ready"}, status_code=503)
        if not get_settings().dev_mode and not (_DIST / "index.html").is_file():
            return JSONResponse({"status": "not_ready"}, status_code=503)
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ok"}
