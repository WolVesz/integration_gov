"""Build a clean deterministic source bundle, explicitly including frontend/dist.

Does not build, deploy, copy credentials, or rely on gitignore/sync behavior.
"""

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_files(root):
    if not (root / "frontend/dist/index.html").is_file():
        raise RuntimeError("Build frontend first: cd frontend && npm ci && npm run build")
    files = [root / "app.yaml", root / "requirements.txt", root / "README.md", root / "LICENSE"]
    for directory, extensions in (("backend", {".py"}), ("scripts", {".py"}), ("docs", {".md"})):
        files += [
            p
            for p in (root / directory).rglob("*")
            if p.is_file()
            and p.suffix in extensions
            and "__pycache__" not in p.parts
            and "tests" not in p.parts
        ]
    files += [p for p in (root / "frontend/dist").rglob("*") if p.is_file()]
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError(f"Refusing symlink or external file: {path}")
        if path.name.startswith(".env") or path.suffix in {".pem", ".key", ".db"}:
            raise RuntimeError(f"Refusing possible secret/local database: {path}")
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="New .tar file outside source tree"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise RuntimeError("Write release archives outside the source tree")
    files = release_files(ROOT)
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    # Uncompressed tar avoids gzip timestamp variability. Exclusive create
    # prevents overwriting an existing release. Files have stable metadata.
    with output.open("xb") as archive_file, tarfile.open(fileobj=archive_file, mode="w") as archive:
        for path in files:
            data = path.read_bytes()
            info = tarfile.TarInfo(str(path.relative_to(ROOT)))
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, sort_keys=True, indent=2).encode()
        info = tarfile.TarInfo("RELEASE_MANIFEST.json")
        info.size, info.mode, info.mtime = len(data), 0o644, 0
        archive.addfile(info, io.BytesIO(data))
    print(
        json.dumps(
            {
                "archive": str(output),
                "files": len(files),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
