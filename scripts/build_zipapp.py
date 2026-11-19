"""Build the portable Python CLI from the same sources used by the checkout."""

import argparse
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = b"from axiom_demo.__main__ import main\nraise SystemExit(main())\n"


def build(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        files = {"__main__.py": ENTRY_POINT, "LICENSE": (ROOT / "LICENSE").read_bytes()}
        for source in sorted((ROOT / "axiom_demo").glob("*.py")):
            files[source.relative_to(ROOT).as_posix()] = source.read_bytes()
        for name, content in files.items():
            # Fixed timestamps and mode make the archive reproducible across checkouts.
            entry = ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "axiom.pyz")
    build(parser.parse_args().output)
