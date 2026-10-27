"""Preview the cost of a selection and diagnose a voided run.

Two failure modes this tool exists to prevent:

1. A "small" selection whose wall time is dominated by one huge matrix test.
   ``estimated_runtime`` is only a scheduling hint, and the harness has no
   timeout, so a single slow test can hold an entire run for tens of minutes.
2. A run discarded at the end with ``execution source epoch changed``. Without
   naming the changed files, the same mistake (editing the tree mid-run) repeats.

Nothing here runs the DUT, edits the plan or changes a verdict.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HINT = re.compile(r'estimated_runtime\(\s*(\d+(?:\.\d+)?)\s*\)')


def selection_files(paths):
    """Expand the same ``--select`` arguments the runner accepts."""
    files = []
    for raw in paths:
        path = ROOT / raw
        if path.is_dir():
            files.extend(sorted(path.rglob('test_*.py')))
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f'unknown selection path: {raw}')
    return files


def costs(files):
    rows = []
    for path in files:
        text = path.read_text()
        hints = [float(value) for value in HINT.findall(text)]
        functions = len(re.findall(r'^(?:async def test_|def test_)', text, re.M))
        rows.append(dict(file=str(path.relative_to(ROOT)), hints=len(hints),
                         hinted_seconds=round(sum(hints)), max_hint=round(max(hints)) if hints else 0,
                         test_functions=functions))
    rows.sort(key=lambda row: (-row['hinted_seconds'], -row['max_hint'], row['file']))
    return rows


def chunks(rows, budget):
    """Greedy packing that never splits a file and keeps the heaviest first."""
    groups, current, load = [], [], 0.0
    for row in rows:
        cost = max(row['hinted_seconds'], row['max_hint'])
        if current and load + cost > budget:
            groups.append((load, current))
            current, load = [], 0.0
        current.append(row['file'])
        load += cost
    if current:
        groups.append((load, current))
    return groups


def measured(path):
    """Per-file totals measured by a completed JUnit report.

    A marker is one number per test function, so a file with 200 cheap cases is
    invisible to ``costs``. The measured report is the only honest source for
    "how long does this selection really take"; it never changes a verdict.
    """
    root = ElementTree.parse(path).getroot()
    totals, peaks, counts = {}, {}, {}
    for case in root.iter('testcase'):
        cls = case.get('classname') or ''
        seconds = float(case.get('time') or 0)
        module = cls.replace('.', '/') + '.py'
        module = module.removeprefix('tests/')
        module = 'tests/' + module
        totals[module] = totals.get(module, 0.0) + seconds
        peaks[module] = max(peaks.get(module, 0.0), seconds)
        counts[module] = counts.get(module, 0) + 1
    return dict(totals=totals, peaks=peaks, counts=counts)


def epoch_delta(run):
    """Compare the frozen keys (absolute paths) with the same files today.

    Only the frozen key set is scanned: walking the whole repository would
    include site-packages and turn a two-file edit into 36000 false positives.
    """
    frozen = json.loads((Path(run) / 'source-epoch.json').read_text())
    frozen = {str(Path(name).resolve()): digest for name, digest in frozen.items()}
    current = {}
    for name in frozen:
        path = Path(name)
        try:
            current[name] = sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    removed = sorted(Path(name).name for name in frozen if name not in current)
    changed = sorted(Path(name).name for name, digest in frozen.items()
                     if name in current and current[name] != digest)
    added = sorted(Path(name).name for name in current if name not in frozen)
    return dict(changed=changed, added=added, removed=removed,
                frozen_files=len(frozen), current_files=len(current))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--select', nargs='*', default=[], help='same paths passed to the runner')
    parser.add_argument('--budget', type=float, default=900.0,
                        help='target wall seconds per chunk for the split suggestion')
    parser.add_argument('--epoch-delta', metavar='RUN_DIR',
                        help='name the files that invalidated a frozen run')
    parser.add_argument('--measured', metavar='PYTEST_XML',
                        help='augment the preview with per-file totals measured by a completed JUnit report')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    if args.epoch_delta:
        delta = epoch_delta(args.epoch_delta)
        if args.json:
            print(json.dumps(delta, indent=2))
        else:
            print(f"frozen={delta['frozen_files']} current={delta['current_files']}")
            print(f"changed={len(delta['changed'])} added={len(delta['added'])} "
                  f"removed={len(delta['removed'])}")
            for name in delta['changed'][:40]:
                print('  changed', name)
            for name in delta['added'][:40]:
                print('  added  ', name)
            for name in delta['removed'][:40]:
                print('  removed', name)
        return 0

    if not args.select:
        parser.error('either --select or --epoch-delta is required')
    rows = costs(selection_files(args.select))
    total = sum(row['hinted_seconds'] for row in rows)
    summary = dict(files=len(rows), test_functions=sum(r['test_functions'] for r in rows),
                   hinted_seconds=total, hints=sum(r['hints'] for r in rows),
                   unhinted_files=sum(1 for r in rows if not r['hints']),
                   top=rows[:8],
                   chunks=[dict(seconds=round(load), files=files)
                           for load, files in chunks(rows, args.budget)])
    if args.measured:
        data = measured(args.measured)
        selected = {row['file'] for row in rows}
        summary['measured_total_seconds'] = round(sum(
            seconds for name, seconds in data['totals'].items() if name in selected))
        summary['measured'] = sorted(
            (dict(file=name, total=round(data['totals'][name], 1),
                  peak=round(data['peaks'][name], 1), cases=data['counts'][name],
                  hint=next((row['hinted_seconds'] for row in rows if row['file'] == name), 0))
             for name in selected if name in data['totals']),
            key=lambda row: -row['total'])
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"files={summary['files']} tests={summary['test_functions']} "
              f"hinted={summary['hinted_seconds']:.0f}s hints={summary['hints']} "
              f"unhinted_files={summary['unhinted_files']}")
        print('heaviest:')
        for row in rows[:8]:
            if not row['hinted_seconds']:
                break
            print(f"  {row['hinted_seconds']:6.0f}s max={row['max_hint']:5.0f} "
                  f"tests={row['test_functions']:3d} {row['file']}")
        if args.measured:
            print(f"measured={summary['measured_total_seconds']}s "
                  f"({summary['measured_total_seconds']/3600:.1f}h) "
                  f"hinted={summary['hinted_seconds']:.0f}s")
            print('measured top:')
            for row in summary['measured'][:10]:
                ratio = (row['total'] / row['hint']) if row['hint'] else float('inf')
                print(f"  {row['total']:8.1f}s peak={row['peak']:7.1f}s n={row['cases']:4d} "
                      f"hint={row['hint']:6.0f} measured/hint={ratio:5.1f}x {row['file']}")
        print(f'suggested chunks (budget {args.budget:.0f}s):')
        for index, chunk in enumerate(summary['chunks']):
            print(f"  chunk{index}: {chunk['seconds']}s files={len(chunk['files'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
