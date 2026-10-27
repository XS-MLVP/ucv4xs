"""Check or synchronize canonical LCOV files from the published native report.

The report's explicit lcov_file entries are authoritative. Never infer the
current run from a directory glob, filename, mtime, or an old canonical copy.
This only publishes existing measurements; it cannot claim new coverage.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = frozenset(('abtb', 'bpu', 'ittage', 'mbtb', 'ras', 'sc', 'tage', 'ubtb', 'uras', 'utage'))


def source_counts(data: bytes) -> dict[tuple[str, int], int]:
    """Validate the unambiguous native SF/DA subset used by this repository."""
    source = None
    counts = {}
    for record in data.decode('utf-8').splitlines():
        if record.startswith('SF:'):
            if source is not None or not record[3:]:
                raise ValueError('invalid LCOV source boundary')
            source = record[3:]
        elif record.startswith('DA:'):
            if source is None:
                raise ValueError('LCOV DA precedes SF')
            number, count = map(int, record[3:].split(','))
            key = (source, number)
            if number <= 0 or count < 0 or key in counts:
                raise ValueError('invalid or duplicate LCOV source line')
            counts[key] = count
        elif record == 'end_of_record':
            if source is None:
                raise ValueError('LCOV end precedes SF')
            source = None
        elif record and not record.startswith('TN:'):
            raise ValueError('unexpected LCOV record: ' + record[:40])
    if source is not None or not counts:
        raise ValueError('incomplete or empty native LCOV')
    return counts


def sync(report_path: Path, *, root: Path = ROOT, publish: bool = False) -> dict:
    root = root.resolve()
    results = root / 'results'
    report_path = report_path.resolve()
    if not report_path.is_relative_to(results):
        raise ValueError('published report must be under repository results/')
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if (report.get('format') != 'bpu-rtl-line-coverage' or report.get('version') != 3
            or report.get('pytest_exitstatus') != 0 or set(report.get('dut', ())) != NAMES):
        raise ValueError('expected a successful complete ten-DUT native report')
    canonical = results / 'rtl-lines'
    if canonical.is_symlink():
        raise ValueError('canonical LCOV directory must not be a symlink')
    planned = []
    # Validate every source and destination before replacing any output.
    for name, row in sorted(report['dut'].items()):
        source = Path(row['lcov_file'])
        if not source.is_absolute() or source.resolve() != source or not source.is_relative_to(results):
            raise ValueError('invalid native LCOV source: ' + str(source))
        payload = source.read_bytes()
        counts = source_counts(payload)
        measured = dict(total=len(counts), hit=sum(count > 0 for count in counts.values()))
        if measured != row['source_lines']:
            raise ValueError('native LCOV disagrees with published source-line totals: ' + name)
        target = canonical / (name + '.info')
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('invalid canonical LCOV target: ' + str(target))
        planned.append((name, source, target, payload))
    if report_path.read_bytes() != report_bytes:
        raise ValueError('published report changed during preflight')
    if any(source.read_bytes() != payload for _, source, _, payload in planned):
        raise ValueError('native LCOV source changed during preflight')
    stale = [name for name, _, target, payload in planned
             if not target.exists() or target.read_bytes() != payload]
    if publish:
        canonical.mkdir(parents=True, exist_ok=True)
        for _, _, target, payload in planned:
            if target.exists() and target.read_bytes() == payload:
                continue
            fd, temporary_name = tempfile.mkstemp(prefix='.' + target.name + '-', dir=canonical)
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        if report_path.read_bytes() != report_bytes:
            raise ValueError('published report changed; rerun synchronization')
        if any(source.read_bytes() != payload for _, source, _, payload in planned):
            raise ValueError('native LCOV source changed; rerun synchronization')
        if any(target.read_bytes() != payload for _, _, target, payload in planned):
            raise ValueError('canonical LCOV changed during publication')
        directory_fd = os.open(canonical, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return dict(format='bpu-published-lcov-synchronization', published=publish,
                report=str(report_path), report_sha256=sha256(report_bytes).hexdigest(),
                stale_before=stale, synchronized=publish or not stale,
                files={name: dict(source=str(source), canonical=str(target),
                                  sha256=sha256(payload).hexdigest())
                       for name, source, target, payload in planned},
                new_coverage_claimed=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'results/rtl-line-coverage.json')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    result = sync(args.report, publish=args.publish)
    print(json.dumps(result, indent=2))
    return 0 if result['synchronized'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
