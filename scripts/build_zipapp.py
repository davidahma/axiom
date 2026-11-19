"""Build the portable Python CLI from the same sources used by the checkout."""

import argparse
import os
import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = b"from axiom_demo.__main__ import main\nraise SystemExit(main())\n"
PACKAGE_FILES = (
    "LICENSE",
    "axiom_demo/__init__.py",
    "axiom_demo/__main__.py",
    "axiom_demo/fixture.py",
    "axiom_demo/gate.py",
    "axiom_demo/inputs.py",
    "axiom_demo/receipt.py",
    "axiom_demo/receipt_cli.py",
    "axiom_demo/report.py",
)


def build(path):
    inputs = [ROOT / name for name in PACKAGE_FILES]
    if any(source.resolve() != source or not source.is_file() for source in inputs):
        raise ValueError("Package inputs must be regular files in the checkout.")
    if path.is_symlink() or (
        path.exists()
        and any(path.samefile(source) for source in [*inputs, Path(__file__)])
    ):
        raise ValueError("Choose an output separate from the package sources.")
    path.parent.mkdir(parents=True, exist_ok=True)
    files = {"__main__.py": ENTRY_POINT}
    for name, source in zip(PACKAGE_FILES, inputs):
        files[name] = source.read_bytes().replace(b"\r\n", b"\n")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
                for name, content in files.items():
                    entry = ZipInfo(name)
                    entry.create_system = 3
                    entry.external_attr = 0o100644 << 16
                    archive.writestr(entry, content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "axiom.pyz")
    try:
        build(parser.parse_args().output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Could not build the archive: {error}\n")
