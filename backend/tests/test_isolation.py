"""Test setup cannot inherit a developer's Lakebase or embedding target."""

import inspect
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from . import conftest


@pytest.mark.parametrize("inherited", [False, True])
def test_setup_overrides_external_targets_and_dotenv(tmp_path, inherited):
    root = Path(__file__).resolve().parents[2]
    settings = {
        "LAKEBASE_INSTANCE_NAME": "must-not-connect",
        "PGHOST": "must-not-connect.invalid",
        "EMBEDDING_ENDPOINT": "must-not-query",
        "DATABASE_URL": "postgresql://must-not-connect.invalid/catalog",
        "APP_NAME": "Developer Catalog",
    }
    (tmp_path / ".env").write_text(
        "\n".join(f"{key}={value}" for key, value in settings.items()), encoding="utf-8"
    )
    env = dict(os.environ, PYTHONPATH=str(root))
    for key, value in settings.items():
        if inherited:
            env[key] = value
        else:
            env.pop(key, None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import inspect
from pathlib import Path
from unittest.mock import patch

with patch("databricks.sdk.WorkspaceClient", side_effect=AssertionError("Unexpected SDK client")):
    with patch("socket.socket.connect", side_effect=AssertionError("Unexpected network access")):
        from backend.tests import conftest
        from backend.config import get_settings

        settings = get_settings()
        assert settings.lakebase_instance_name == ""
        assert settings.embedding_endpoint == ""
        assert conftest.engine.dialect.name == "sqlite"
        assert conftest.engine.url.database == conftest._db_path
        fixture = inspect.unwrap(conftest.fresh_db)()
        next(fixture)
        fixture.close()
        conftest.engine.dispose()
        Path(conftest._db_path).unlink()
""",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "dialect,database",
    [("postgresql", None), ("sqlite", "not-the-allocated-test-database")],
)
def test_fixture_rejects_other_databases_before_ddl(monkeypatch, dialect, database):
    drop = Mock()
    monkeypatch.setattr(conftest.Base.metadata, "drop_all", drop)
    monkeypatch.setattr(
        conftest,
        "engine",
        SimpleNamespace(
            dialect=SimpleNamespace(name=dialect), url=SimpleNamespace(database=database)
        ),
    )
    fixture = inspect.unwrap(conftest.fresh_db)()
    with pytest.raises(AssertionError, match="Tests must use"):
        next(fixture)
    drop.assert_not_called()
