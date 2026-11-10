"""Check generated Databricks requirements against the uv lock, or explicitly update them."""

import argparse
import shutil

# Only fixed uv commands are run, without a shell or untrusted arguments.
import subprocess  # nosec B404
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = {"requirements.txt": ["--no-dev"], "requirements-dev.txt": ["--all-groups"]}


def check_exports(root: Path = ROOT, *, write: bool = False) -> bool:
    """Return whether generated exports match, optionally writing updated exports."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv before checking dependency exports")
    matched = True
    for filename, groups in EXPORTS.items():
        # The executable and arguments are fixed; no shell is used.
        result = subprocess.run(  # nosec B603
            [uv, "export", "--locked", "--no-header", "--no-emit-project", *groups],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        path = root / filename
        if write:
            path.write_text(result.stdout, encoding="utf-8")
        elif not path.is_file() or path.read_text(encoding="utf-8") != result.stdout:
            print(f"{filename} is stale; run uv run --locked poe export-deps")
            matched = False
    return matched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate requirements exports")
    args = parser.parse_args()
    raise SystemExit(0 if check_exports(write=args.write) else 1)


if __name__ == "__main__":
    main()
