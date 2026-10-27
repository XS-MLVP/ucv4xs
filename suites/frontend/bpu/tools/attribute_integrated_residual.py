"""Per-file attribution of the integrated-BPU residual uncovered lines.

Reads one native line-coverage report and groups uncovered source lines by
(file, normalized emission-site template).  The output is an audit artefact: it
says *which* emission site each missing line belongs to and how many physical
copies that site has, so a "per-cell/per-set copy" claim is countable instead of
asserted.

It does not change any denominator and it does not grant functional credit.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path


def normalize(verilog: str) -> str:
    text = re.sub(r'\s+', ' ', verilog or '').strip()
    text = re.sub(r'_\d+', '_N', text)
    text = re.sub(r'\b\d+\b', 'N', text)
    text = re.sub(r'\[N:N\]', '[N:N]', text)
    return text[:90]


def select_dut(duts: dict, wanted: str | None = None) -> tuple[str, dict]:
    """Pick the DUT to attribute.

    A whole-suite run merges every DUT into one report, so ``next(iter(...))``
    silently reads whichever name sorts first (``abtb``) and reports zero
    residual while the much larger DUT is untouched. Default to the DUT with the
    most uncovered lines; an explicit ``wanted`` name must exist.
    """
    if not duts:
        raise ValueError('report has no DUT payloads')
    if wanted is not None:
        if wanted not in duts:
            raise ValueError(f'unknown dut {wanted!r}; report has {sorted(duts)}')
        return wanted, duts[wanted]
    name = max(duts, key=lambda key: len(duts[key].get('uncovered_rtl_source_lines') or []))
    return name, duts[name]


def attribute(report: dict, *, dut: str | None = None) -> dict:
    name, payload = select_dut(report.get('dut') or {}, dut)
    if False:  # pragma: no cover - documentation of the removed single-DUT path
        name, payload = next(iter(report.get('dut') or {}))
    lines = payload.get('uncovered_rtl_source_lines') or []
    branches = payload.get('uncovered_rtl_branches') or []
    by_file = collections.defaultdict(list)
    for row in lines:
        by_file[row['file']].append(row)
    files = []
    for path, rows in sorted(by_file.items(), key=lambda item: -len(item[1])):
        sites = collections.Counter(normalize(row.get('verilog')) for row in rows)
        files.append(dict(
            file=path,
            uncovered_lines=len(rows),
            emission_sites=len(sites),
            largest_sites=[dict(count=count, template=template)
                           for template, count in sites.most_common(5)],
            copies_per_site=dict(collections.Counter(sites.values())),
        ))
    branch_by_file = collections.Counter(row['file'] for row in branches)
    return dict(
        format='integrated-residual-attribution', version=1,
        dut=name,
        source_lines=payload.get('by_source', {}).get('rtl_verilog', {}).get('source_lines'),
        uncovered_lines=len(lines),
        uncovered_branches=len(branches),
        files=files,
        branch_files=[dict(file=path, count=count)
                      for path, count in branch_by_file.most_common(12)],
        note='Normalized templates collapse physical copy indices; counts are '
             'report-derived and grant no coverage credit.',
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dut', help='DUT name; default is the one with the most uncovered lines')
    args = parser.parse_args(argv)
    result = attribute(json.loads(args.report.read_text()), dut=args.dut)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps(dict(files=len(result['files']),
                          uncovered_lines=result['uncovered_lines'],
                          uncovered_branches=result['uncovered_branches']), indent=1))


if __name__ == '__main__':
    main()
