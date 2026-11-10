from types import SimpleNamespace

import pytest

from scripts.check_dependencies import EXPORTS, check_exports


@pytest.fixture
def uv_export(monkeypatch):
    monkeypatch.setattr("scripts.check_dependencies.shutil.which", lambda name: "/bin/uv")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="example-package==1.0\n")

    monkeypatch.setattr("scripts.check_dependencies.subprocess.run", run)
    return calls


def test_exports_match_without_writing(tmp_path, uv_export):
    for filename in EXPORTS:
        (tmp_path / filename).write_text("example-package==1.0\n")
    assert check_exports(tmp_path)
    assert len(uv_export) == 2
    assert all("--locked" in command for command, _ in uv_export)
    assert all(kwargs["check"] and kwargs["cwd"] == tmp_path for _, kwargs in uv_export)


def test_stale_exports_fail_without_changes(tmp_path, uv_export):
    path = tmp_path / "requirements.txt"
    path.write_text("stale\n")
    assert not check_exports(tmp_path)
    assert path.read_text() == "stale\n"
    assert not (tmp_path / "requirements-dev.txt").exists()


def test_explicit_write_regenerates_exports(tmp_path, uv_export):
    assert check_exports(tmp_path, write=True)
    assert all(
        (tmp_path / filename).read_text() == "example-package==1.0\n" for filename in EXPORTS
    )


def test_missing_uv_reports_requirement(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.check_dependencies.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="Install uv"):
        check_exports(tmp_path)
