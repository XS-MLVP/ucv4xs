"""Attribute qualified incremental native LCOV hits to a checked feature.

This is not a full-regression publisher. An isolated scenario's non-hits are
not regressions, and a historical/current union is not current full coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def lcov_rows(path):
    rows, source = {}, None
    for line in Path(path).read_text().splitlines():
        if line.startswith('SF:'):
            source = line[3:]
        elif line.startswith('DA:'):
            number, count, *_ = line[3:].split(',')
            key = source, int(number)
            if source is None or int(count) < 0 or key in rows:
                raise ValueError(f'invalid or duplicate native LCOV row: {line}')
            rows[key] = int(count)
    if not rows:
        raise ValueError('native LCOV contains no DA rows')
    return rows


def new_hits(baseline, scenario):
    if baseline.keys() != scenario.keys():
        raise ValueError('native LCOV source/line denominator changed')
    return sorted(key for key, count in scenario.items() if count > 0 and baseline[key] == 0)


def attribute(baseline_dir, scenario_dir, *, dut, feature):
    baseline_dir, scenario_dir = Path(baseline_dir), Path(scenario_dir)
    def read(directory, name):
        return json.loads((directory / name).read_text())
    # refresh_coverage keeps native reports beside a pytest-artifacts child;
    # earlier isolated runs used a flat directory. Read either without copying
    # or rewriting receipts, and reject an ambiguous double source.
    evidence_paths = [path for path in (scenario_dir / 'evidence.json',
                      scenario_dir / 'pytest-artifacts' / 'evidence.json') if path.is_file()]
    if len(evidence_paths) != 1:
        raise ValueError('scenario requires one unambiguous pytest evidence file')
    evidence = json.loads(evidence_paths[0].read_text())
    if (evidence.get('pytest_exitstatus') != 0 or evidence.get('evidence_complete') is not True
            or evidence.get('integrity_errors') != []):
        raise ValueError('scenario lacks complete successful pytest evidence')
    features = read(scenario_dir, 'feature-points.json')['features']
    selected = [row for row in features if row['id'] == feature]
    if len(selected) != 1 or selected[0]['status'] != 'PASS':
        raise ValueError('attributed feature must have qualified PASS evidence')
    # Restrict attribution to a single checked scenario: mixing unrelated
    # passing tests cannot establish that the named feature caused the delta.
    tests = evidence['tests']
    if len(tests) != 1 or tests[0]['status'] != 'PASS':
        raise ValueError('feature attribution requires one isolated passing scenario')
    if selected[0]['tests'] != [dict(nodeid=tests[0]['nodeid'], status='PASS')]:
        raise ValueError('feature/test association does not match isolated evidence')
    old_report = read(baseline_dir, 'rtl-line-coverage.json')
    new_report = read(scenario_dir, 'rtl-line-coverage.json')
    if old_report['line_coverage'] != new_report['line_coverage']:
        raise ValueError('native coverage metric changed')
    old, new = old_report['dut'][dut], new_report['dut'][dut]
    for field in ('primary_rtl_sha256', 'signals_sha256'):
        if old['build_provenance'][field] != new['build_provenance'][field]:
            raise ValueError(f'build identity changed: {field}')
    old_path, new_path = Path(old['lcov_file']), Path(new['lcov_file'])
    before, after = lcov_rows(old_path), lcov_rows(new_path)
    for rows, report in ((before, old), (after, new)):
        if report['source_lines'] != dict(total=len(rows), hit=sum(v > 0 for v in rows.values())):
            raise ValueError('native LCOV disagrees with report totals')
    added = new_hits(before, after)
    previous = {(str((Path.cwd() / row['file']).resolve()), row['line']): row
                for row in old['uncovered_rtl_source_lines']}
    sources, points = {}, []
    for source, line in added:
        if source not in sources:
            path = Path(source)
            sources[source] = dict(sha256=sha256(path.read_bytes()).hexdigest(),
                                   lines=path.read_text().splitlines())
        text = sources[source]['lines'][line - 1].strip()
        prior = previous.get((source, line))
        if prior is None or prior['verilog'].strip() != text:
            raise ValueError(f'baseline uncovered RTL text changed: {source}:{line}')
        points.append(dict(file=source, line=line, verilog=text,
                           scala_refs=prior.get('scala_refs', []), feature=feature,
                           scenario_count=after[source, line]))
    return dict(format='bpu-qualified-functional-line-delta', version=1,
        scope='isolated functional increment; NOT a new full-regression coverage result',
        baseline=str(baseline_dir), scenario=str(scenario_dir), dut=dut,
        feature=feature, nodeid=tests[0]['nodeid'], metric=new_report['line_coverage'],
        denominator=len(before), baseline_hits=sum(v > 0 for v in before.values()),
        isolated_scenario_hits=sum(v > 0 for v in after.values()), new_native_rows=len(added),
        by_source=dict(Counter(Path(source).name for source, _ in added)),
        lcov_sha256={str(p): sha256(p.read_bytes()).hexdigest() for p in (old_path, new_path)},
        source_sha256={key: value['sha256'] for key, value in sources.items()}, rows=points)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--dut', required=True)
    parser.add_argument('--feature', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = attribute(args.baseline, args.scenario, dut=args.dut, feature=args.feature)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('feature', 'new_native_rows', 'by_source')}))


if __name__ == '__main__':
    main()
