"""Recursively delete every ``__pycache__`` folder and ``*.pyc`` file
under the OMRAT repo root.

Useful when QGIS has cached a stale plugin module after a refactor or
when ``pytest`` is picking up a removed test through its bytecode
sibling.  Safe to run from anywhere -- the script anchors itself to the
repo by going one directory up from the ``tools/`` folder rather than
relying on the caller's cwd.

Usage::

    python tools/clear_pycache.py            # actually delete
    python tools/clear_pycache.py --dry-run  # list what would be removed
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _iter_targets(root: Path):
    """Yield every ``__pycache__`` dir and ``.pyc`` file under ``root``.

    ``__pycache__`` directories are yielded as a unit so the caller
    can ``rmtree`` them in one shot; loose ``.pyc`` files (uncommon
    but possible from ancient Python 2 leftovers) are yielded
    individually.  Symlinked directories are not followed -- avoids
    deleting things outside the repo if the user has a venv linked
    in.
    """
    for path in root.rglob('__pycache__'):
        if path.is_dir() and not path.is_symlink():
            yield path
    for path in root.rglob('*.pyc'):
        # Skip files inside __pycache__ dirs we already yielded -- the
        # rmtree will take them.  Cheap to check via parents.
        if any(p.name == '__pycache__' for p in path.parents):
            continue
        if path.is_file():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--dry-run', action='store_true',
        help="List paths that would be deleted, but don't touch them.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    if not repo_root.exists():
        print(f"Repo root not found: {repo_root}", file=sys.stderr)
        return 1

    removed_dirs = 0
    removed_files = 0
    bytes_freed = 0
    errors: list[str] = []

    for target in _iter_targets(repo_root):
        rel = target.relative_to(repo_root)
        if args.dry_run:
            kind = 'DIR' if target.is_dir() else 'FILE'
            print(f"would remove {kind}: {rel}")
            continue
        try:
            if target.is_dir():
                size = sum(
                    f.stat().st_size for f in target.rglob('*') if f.is_file()
                )
                shutil.rmtree(target)
                removed_dirs += 1
                bytes_freed += size
            else:
                bytes_freed += target.stat().st_size
                target.unlink()
                removed_files += 1
        except OSError as exc:
            errors.append(f"{rel}: {exc}")

    if args.dry_run:
        print("\n(dry run -- nothing was deleted)")
        return 0

    mb = bytes_freed / (1024 * 1024)
    print(
        f"Removed {removed_dirs} __pycache__ folder(s) "
        f"and {removed_files} stray .pyc file(s)  ({mb:.2f} MB freed)."
    )
    if errors:
        print("\nErrors:", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
