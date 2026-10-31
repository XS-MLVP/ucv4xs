"""Check serial/parallel native runs without publishing full-regression credit."""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from suites.frontend.bpu.coverage import rtl as rtl_coverage
from tools.refresh_coverage import NAMES
from tools.refresh_coverage import ROOT
from tools.refresh_coverage import digest
from tools.refresh_coverage import execution_inputs
from tools.refresh_coverage import read
from tools.refresh_coverage import write


def canonical_fc(database):
    """Only rename implicit collection UUIDs; preserve all coverage semantics."""
    value = deepcopy(database)
    substitutions = {}

    def snapshot(group):
        payload = {key: item for key, item in group.items() if key != 'snapshot_id'}
        return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    for group in value['groups']:
        if group['snapshot_id'] != snapshot(group) or len(group['origins']) != 1:
            raise ValueError('invalid original functional snapshot')
        origin, record = next(iter(group['origins'].items()))
        if record['explicit_run_id'] is not False or record['run_id'] != origin or group['active_origin'] != origin:
            raise ValueError('not an implicit independent collection origin')
        if origin not in substitutions:
            substitutions[origin] = f'implicit-origin-{len(substitutions)}'

    def rename(item):
        if isinstance(item, dict):
            result = {substitutions.get(key, key): rename(val) for key, val in item.items()}
            if len(result) != len(item):
                raise ValueError('non-bijective origin mapping')
            return result
        if isinstance(item, list):
            return [rename(val) for val in item]
        return substitutions.get(item, item) if isinstance(item, str) else item

    result = rename(value)
    for group in result['groups']:
        group['snapshot_id'] = snapshot(group)
    return result


def qualify(serial, parallel, output, nodes):
    protected = {name: digest(ROOT / 'results' / name) for name in (
        'feature-points.json', 'rtl-coverage-manifest.json', 'rtl-line-coverage.json',
        'verification-report.html', 'summary.json')}
    output.mkdir(parents=True, exist_ok=False)
    verdicts, functional, manifests, native = [], [], [], []
    for run in (serial, parallel):
        evidence = read(run / 'evidence.json')
        cases = {row['nodeid']: row['status'] for row in evidence['tests']}
        if set(cases.values()) != {'PASS'}:
            raise ValueError('qualification requires all cases PASS')
        verdicts.append(cases)
        paths = execution_inputs(run, nodes, cases)
        functional.append({'/'.join(path.relative_to(run / 'workers').parts[1:]): path for path in paths})
        manifest = read(run / 'rtl-coverage-manifest.json')
        manifests.append(manifest)
        native.append(rtl_coverage.build_report(run / 'rtl-coverage-manifest.json', run / 'qualification-native.json'))
    if verdicts[0] != verdicts[1] or functional[0].keys() != functional[1].keys():
        raise ValueError('serial/parallel test or artifact identities differ')
    if any({path.parent.name for path in inputs.values()} != set(NAMES) for inputs in functional):
        raise ValueError('not all ten DUT functional coverage outputs were captured')
    if read(serial / 'feature-points.json')['features'] != read(parallel / 'feature-points.json')['features']:
        raise ValueError('serial/parallel feature verdicts differ')
    for key in functional[0]:
        if canonical_fc(read(functional[0][key])) != canonical_fc(read(functional[1][key])):
            raise ValueError('functional semantics differ: ' + key)
    from toffee.coverage_report import load_functional_coverage
    for inputs in functional:
        load_functional_coverage(list(inputs.values()))
    merged = {}
    if any(set(report['dut']) != set(NAMES) for report in native):
        raise ValueError('not all ten native DUTs were exercised')
    for name in NAMES:
        hashes = []
        for label, manifest in zip(('serial', 'parallel'), manifests):
            paths = [ROOT / path for path in manifest['files'] if Path(path).parent.name == name]
            destination = output / f'{label}-{name}.dat'
            subprocess.run([rtl_coverage._coverage_tool(name), '--write', str(destination), *map(str, paths)],
                           check=True, capture_output=True, text=True)
            hashes.append(digest(destination))
        if hashes[0] != hashes[1]:
            raise ValueError('complete native point tables differ: ' + name)
        left, right = (Path(report['dut'][name]['lcov_file']) for report in native)
        if left.read_bytes() != right.read_bytes():
            raise ValueError('native LCOV differs: ' + name)
        merged[name] = dict(full_native_table_sha256=hashes[0], lcov_sha256=digest(left),
                            source_lines=native[0]['dut'][name]['source_lines'])
    if any(digest(ROOT / 'results' / name) != value for name, value in protected.items()):
        raise ValueError('published reports changed during qualification')
    report = dict(format='bpu-production-parallel-qualification', version=1,
        tests_PASS=len(nodes), equivalent_functional_files=len(functional[0]),
        complete_native_point_tables_equal=True, native_lcov_equal=True, native=merged,
        serial=str(serial), parallel=str(parallel), current_reports_unchanged=True,
        full_suite_qualified=False, new_coverage_claimed=False, goal_complete=False)
    write(output / 'qualification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', type=Path, required=True)
    parser.add_argument('--parallel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', action='append', required=True)
    args = parser.parse_args()
    report = qualify(args.serial.resolve(), args.parallel.resolve(), args.output.resolve(), args.node)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
