"""Run the security scanners that plugins.qgis.org applies on upload, so
you can catch and fix findings BEFORE committing / packaging / uploading.

Two scanners are run over the plugin code:

  * ``bandit``          -- Python static security analysis.
  * ``detect-secrets``  -- hardcoded secret / API-key / password scanning.
                           This is the "Secrets Detection" gate that rejects
                           uploads on plugins.qgis.org.

Both tools honour inline suppression comments, which this script respects
because it just shells out to the real tools:

  * bandit          ->  ``# nosec``  /  ``# nosec B105``
  * detect-secrets  ->  ``# pragma: allowlist secret``

By default the script scans your working source tree. The server actually
scans the *packaged* plugin, so before an upload run it with ``--package``
to scan the built ``zip_build/`` tree -- an exact match for what gets sent.

Exit codes (safe to use as a pre-commit / pre-upload gate)::

    0   both scanners clean (no secrets, no medium/high bandit findings)
    1   findings that would block or warrant attention
    2   an internal / scanner error
    3   a required tool (bandit / detect-secrets) is not installed

Usage::

    python scripts/check_security.py             # scan the working source
    python scripts/check_security.py --package   # scan the built zip_build/ tree
    python scripts/check_security.py --strict     # also fail on low-severity bandit findings
    python scripts/check_security.py --verbose    # list every low-severity bandit finding
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Directories that are not shipped plugin code (tests, translations, build
# artefacts, docs, caches). Scanning them only produces noise the server
# would never see. Matched by *name* anywhere in the path.
EXCLUDE_DIRS = {
    'tests', 'i18n', 'i18n_backup_cdse2', '.pytest_cache', 'docs',
    'homepage', 'example_iso_files', '.git', '__pycache__', '.vscode',
    'zip_build',
}


def _tool_available(module: str) -> bool:
    """Return True if ``python -m <module>`` can be imported."""
    proc = subprocess.run(  # nosec B603 - fixed args, our own interpreter
        [sys.executable, '-c', f'import {module}'],
        capture_output=True,
    )
    return proc.returncode == 0


def _iter_py_files(root: Path):
    """Yield every ``*.py`` file under ``root`` outside EXCLUDE_DIRS."""
    for path in root.rglob('*.py'):
        if any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _chunked(items: list, size: int):
    """Yield ``items`` in lists of at most ``size`` (keeps command lines
    comfortably under the Windows length limit)."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run_bandit(scan_root: Path) -> "tuple[list[dict], str | None]":
    """Run bandit and return (results, error). ``results`` is bandit's list
    of issue dicts; ``error`` is a message when bandit could not be run."""
    exclude_csv = ','.join(f'./{name}' for name in sorted(EXCLUDE_DIRS))
    # Write the report to a file with -o: bandit mixes INFO/WARNING logs into
    # stdout, so parsing stdout directly is unreliable. The file is pure JSON.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'bandit.json'
        proc = subprocess.run(  # nosec B603
            [sys.executable, '-m', 'bandit', '-q', '-r', '.', '-f', 'json',
             '-o', str(out), '-x', exclude_csv],
            cwd=str(scan_root), capture_output=True, text=True,
        )
        # bandit exits 1 when it finds issues; that is expected, not an error.
        if not out.exists():
            return [], (proc.stderr.strip() or 'bandit produced no report')
        try:
            payload = json.loads(out.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as exc:
            return [], f'could not read bandit report: {exc}'
    return payload.get('results', []), None


def run_detect_secrets(scan_root: Path) -> "tuple[dict, str | None]":
    """Run detect-secrets over the python files under ``scan_root`` and
    return (results, error), where ``results`` maps file -> list of finds."""
    files = [str(p.relative_to(scan_root).as_posix())
             for p in _iter_py_files(scan_root)]
    if not files:
        return {}, None
    merged: dict = {}
    for batch in _chunked(files, 150):
        proc = subprocess.run(  # nosec B603 - fixed args, our own interpreter
            [sys.executable, '-m', 'detect_secrets', 'scan', *batch],
            cwd=str(scan_root), capture_output=True, text=True,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {}, (proc.stderr.strip()
                        or 'detect-secrets produced no JSON output')
        merged.update(payload.get('results', {}))
    return merged, None


def _resolve_scan_root(repo_root: Path, package: bool) -> "Path | None":
    """Pick the directory to scan. ``--package`` targets the built plugin."""
    if not package:
        return repo_root
    for candidate in (repo_root / 'zip_build' / 'geodatafarm',
                      repo_root / 'zip_build'):
        if candidate.is_dir():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--package', action='store_true',
        help='Scan the built zip_build/ tree (what actually gets uploaded) '
             'instead of the working source.')
    parser.add_argument(
        '--allow-low', action='store_true',
        help='Do not fail on low-severity bandit findings (report only). '
             'By default any finding fails, mirroring the plugins.qgis.org '
             'upload gate, which now blocks on all severities.')
    parser.add_argument(
        '--verbose', action='store_true',
        help='List every low-severity bandit finding individually.')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    scan_root = _resolve_scan_root(repo_root, args.package)
    if scan_root is None:
        print('No zip_build/ tree found -- run `make package` (or `make zip`) '
              'first, then re-run with --package.', file=sys.stderr)
        return 2

    missing = [m for m in ('bandit', 'detect_secrets')
               if not _tool_available(m)]
    if missing:
        pretty = ' '.join('detect-secrets' if m == 'detect_secrets' else m
                          for m in missing)
        print(f'Required tool(s) not installed: {pretty}\n'
              f'Install with:  {Path(sys.executable).name} -m pip install '
              f'{pretty}', file=sys.stderr)
        return 3

    print(f'Scanning: {scan_root}\n')
    failed = False

    # --- detect-secrets (the upload-blocking gate) -----------------------
    secrets, err = run_detect_secrets(scan_root)
    print('== detect-secrets (Secrets Detection) ==')
    if err:
        print(f'  ERROR: {err}', file=sys.stderr)
        return 2
    if secrets:
        failed = True
        total = sum(len(v) for v in secrets.values())
        print(f'  {total} potential secret(s) found:')
        for filename in sorted(secrets):
            for item in secrets[filename]:
                line = item.get('line_number', '?')
                kind = item.get('type', 'secret')
                print(f'    {filename}:{line}  {kind}')
        print('  -> if a finding is a false positive, append '
              '`# pragma: allowlist secret` to that line.')
    else:
        print('  clean -- no secrets detected.')
    print()

    # --- bandit ----------------------------------------------------------
    results, err = run_bandit(scan_root)
    print('== bandit (static security analysis) ==')
    if err:
        print(f'  ERROR: {err}', file=sys.stderr)
        return 2
    by_sev = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
    for issue in results:
        by_sev.get(issue.get('issue_severity', 'LOW'), by_sev['LOW']).append(
            issue)

    for sev in ('HIGH', 'MEDIUM'):
        for issue in by_sev[sev]:
            failed = True
            rel = issue.get('filename', '?')
            print(f'  [{sev}] {rel}:{issue.get("line_number", "?")}  '
                  f'{issue.get("test_id", "")}  {issue.get("issue_text", "")}')

    low = by_sev['LOW']
    if low:
        if not args.allow_low:
            failed = True
        if args.verbose:
            for issue in low:
                marker = 'warn' if args.allow_low else 'FAIL'
                print(f'  [{marker}:LOW] {issue.get("filename", "?")}:'
                      f'{issue.get("line_number", "?")}  '
                      f'{issue.get("test_id", "")}  '
                      f'{issue.get("issue_text", "")}')
        else:
            summary = ', '.join(f'{tid}x{n}' for tid, n in
                                Counter(i.get('test_id') for i in low).items())
            note = '(not failing: --allow-low)' if args.allow_low else '(failing)'
            print(f'  {len(low)} low-severity finding(s) {note}: {summary}')
            print('  -> re-run with --verbose to list them, or silence a '
                  'line with `# nosec` / `# nosec B###`.')

    if not by_sev['HIGH'] and not by_sev['MEDIUM'] and not low:
        print('  clean -- no findings.')
    print()

    if failed:
        print('RESULT: FAIL -- fix the findings above before uploading.')
        return 1
    print('RESULT: PASS -- safe to commit / package / upload.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
