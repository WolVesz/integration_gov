"""Databricks startup is read-only and cannot silently fall back to SQLite."""

import asyncio
from types import SimpleNamespace

import pytest

from backend import main
from backend.database import engine
from backend.models import Base


def run_startup():
    async def run():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run())


def test_databricks_refuses_development_identity(monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_PORT", "8000")
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(dev_mode=True))
    with pytest.raises(RuntimeError, match="DEV_MODE"):
        run_startup()


def test_databricks_refuses_sqlite_fallback(monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_PORT", "8000")
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(dev_mode=False))
    with pytest.raises(RuntimeError, match="SQLite fallback is forbidden"):
        run_startup()


def test_databricks_requires_schema_without_creating_it(monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_PORT", "8000")
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(dev_mode=False))
    # The dialect contract is faked here; live PostgreSQL requires deployment validation.
    monkeypatch.setattr(main, "_current_schema", lambda connection: "main")
    monkeypatch.setattr(
        main,
        "engine",
        SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=engine.connect),
    )
    Base.metadata.tables["integration_framework_profiles"].drop(engine)
    monkeypatch.setattr(
        Base.metadata, "create_all", lambda *a, **kw: pytest.fail("Production attempted DDL")
    )
    with pytest.raises(RuntimeError, match="migrate_framework.py"):
        run_startup()


def test_databricks_complete_schema_is_read_only(monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_PORT", "8000")
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(dev_mode=False))
    monkeypatch.setattr(main, "_current_schema", lambda connection: "main")
    monkeypatch.setattr(
        main,
        "engine",
        SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=engine.connect),
    )
    monkeypatch.setattr(
        Base.metadata, "create_all", lambda *a, **kw: pytest.fail("Production attempted DDL")
    )
    run_startup()


@pytest.mark.parametrize("app_name", [None, "Custom Integration Catalog"])
def test_application_title_is_configurable(monkeypatch, app_name):
    import importlib

    from backend.config import Settings, get_settings

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    if app_name is None:
        monkeypatch.delenv("APP_NAME", raising=False)
    else:
        monkeypatch.setenv("APP_NAME", app_name)
    get_settings.cache_clear()
    original_app = main.app
    try:
        reloaded = importlib.reload(main)
        assert reloaded.app.title == (app_name or "Integration Governance")
    finally:
        main.app = original_app
        get_settings.cache_clear()
