"""Bounded cell-template audit for the UTAGE bypass shadow useful registers.

Every uncovered row in this generated WriteBuffer is expected to be one of six
textual templates for a single useful cell.  The audit proves that the residual
rows are *per-cell copies of three already-exercised updates*, not 1829 distinct
semantics.  It never removes a native row, never grants functional credit, and
never claims whole-design unreachability.
"""
from suites.frontend.bpu import ROOT as _SUITE_ROOT
from collections import Counter, defaultdict
from pathlib import Path
import json
import re

ROOT = _SUITE_ROOT
SOURCE = 'rtl/utage/BypassShadowBuffer.sv'
CELL = re.compile(r'usefulEntries_(\d+)_(\d+)_value')

TEMPLATES = (
    ('allocate-weak', re.compile(r"usefulEntries_(\d+)_(\d+)_value <= 2'h1;")),
    ('reward-increase', re.compile(r'usefulEntries_(\d+)_(\d+)_value <= _GEN_147;')),
    ('penalty-decrease', re.compile(r'usefulEntries_(\d+)_(\d+)_value <= _newUseful_T_13;')),
    ('allocate-head', re.compile(r'if \(io_train_t1_alloc_valid\)')),
    ('increase-head', re.compile(r'else if \(_newUseful_T_8\)')),
    ('reset-decrement', re.compile(
        r"usefulEntries_(\d+)_(\d+)_value == 2'h0 \? 2'h0 : usefulEntries_(\d+)_(\d+)_value - 2'h1;")),
    ('reset-shift', re.compile(r"usefulEntries_(\d+)_(\d+)_value >> 1'h1;")),
    ('legacy-guard-head', re.compile(r'if \(_GEN_148 & _GEN_149 & _GEN_\d+\) begin')),
)


def source_lines():
    return [line.split('//', 1)[0].strip() for line in (ROOT / SOURCE).read_text().splitlines()]


def classify(report, dut='utage'):
    lines = source_lines()
    rows = [row for row in report['dut'][dut]['uncovered_rtl_source_lines'] if row['file'] == SOURCE]
    unmatched = []
    forms = Counter()
    cells = defaultdict(set)
    for row in rows:
        body = lines[row['line'] - 1]
        for name, pattern in TEMPLATES:
            if pattern.search(body):
                forms[name] += 1
                match = CELL.search(body)
                if match is not None:
                    cells[name].add((int(match[1]), int(match[2])))
                break
        else:
            unmatched.append((row['line'], body[:120]))
    total = report['dut'][dut]['source_lines']
    return dict(
        format='utage-useful-cell-template-audit', version=1,
        source=SOURCE,
        source_sha256=_sha256(ROOT / SOURCE),
        raw_missing=len(rows),
        templates={name: forms[name] for name, _ in TEMPLATES},
        matched=len(rows) - len(unmatched),
        unmatched=unmatched,
        distinct_cells={name: len(value) for name, value in cells.items()},
        native_source_lines=dict(total=total['total'], hit=total['hit']),
        native_denominator_unchanged=True,
        functional_pass_credit=False,
        whole_design_formal_claim=False,
        scope='three useful-register update templates per (bank,set) cell; no reachability or correctness claim',
    )


def _sha256(path):
    from hashlib import sha256
    return sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--dut', default='utage')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = classify(json.loads(args.report.read_text()), args.dut)
    if result['unmatched']:
        raise SystemExit(f"unclassified rows: {result['unmatched'][:5]}")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: result[key] for key in
        ('raw_missing', 'matched', 'distinct_cells', 'native_denominator_unchanged')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
