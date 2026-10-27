"""Reassess existing 8352 native event records; this does NOT run the DUT."""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.vagq.exhaustive import assess_shape_boundaries, build_shape_sequence, compare_shape
from vagqverify.vagq.scenario_matrix import legal_public_feature_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    original = ROOT / 'results/vagq-exhaustive-20261020-v1'
    run = original / 'full'
    receipts = json.loads((run / 'completed-shapes.json').read_text())
    cases = tuple(legal_public_feature_cases())
    families = {row['ordinal']: row['family'] for row in json.loads(
        (ROOT / 'results/vagq-exhaustive-review-20261020-v1/reviewed-failures.json').read_text())}
    assert len(receipts) == len(cases) == 8352
    assert [row['ordinal'] for row in receipts] == list(range(8352))
    counts = defaultdict(Counter)
    by_family = defaultdict(lambda: defaultdict(Counter))
    rows, flat = [], []
    aggregate = hashlib.sha256()
    for ordinal, (receipt, case) in enumerate(zip(receipts, cases)):
        path = Path(receipt['path'])
        assert digest(path) == receipt['sha256']
        record = json.loads(path.read_text())
        plan = build_shape_sequence(case, ordinal)
        assert record['stimulus'] == plan.stimulus()
        stimulus_path = path.with_name(f'{ordinal:05d}-stimulus.json')
        assert json.loads(stimulus_path.read_text()) == plan.stimulus()
        legacy = compare_shape(plan, record['events'])
        assert all(record[key] == value for key, value in legacy.items()), ordinal
        assessment = assess_shape_boundaries(plan, record['events'])
        assert assessment['legacy_v2']['status'] == receipt['status']
        assert assessment['overall_isa_acceptance'] == 'NOT_VERIFIED'
        family = families.get(ordinal, 'legacy_v2_pass')
        statuses = dict(legacy_v2=receipt['status'],
            raw_architectural_counter=assessment['architectural_requests']['status'],
            public_lifecycle=assessment['public_lifecycle']['status'],
            scoped_request_boundary=assessment['request_boundary_status'],
            single_flow_projection='MATCH' if assessment['response_placement']['projection_matches_architecture'] else 'DIFF')
        for key, value in statuses.items():
            counts[key][value] += 1
            by_family[family][key][value] += 1
        row = dict(ordinal=ordinal, shape_id=receipt['shape_id'], family=family,
            original_path=str(path), original_sha256=receipt['sha256'],
            original_stimulus_sha256=digest(stimulus_path),
            assessment=assessment, new_native_execution=False,
            new_full_functional_acceptance_credit=False)
        rows.append(row)
        flat.append(dict(ordinal=ordinal, shape_id=receipt['shape_id'], family=family,
            **statuses, overall_isa_acceptance='NOT_VERIFIED', new_native_execution=False,
            original_path=str(path), original_sha256=receipt['sha256']))
        aggregate.update(bytes.fromhex(receipt['sha256']))
    assert counts['legacy_v2'] == Counter(PASS=6074, FAIL=2278)
    old_report = json.loads((original / 'report.json').read_text())
    assert counts['raw_architectural_counter']['PASS'] == old_report['diagnostics']['raw_byte_counter_match']
    assert counts['single_flow_projection']['MATCH'] == old_report['diagnostics']['placement_byte_counter_match']
    atomic_json(out / 'reassessed-shapes.json', rows)
    with (out / 'reassessed-shapes.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    summary = dict(reassessed_records=8352, new_native_shape_executions=0,
        original_shape_input_sequences_unchanged=8352,
        original_checker_statuses_preserved=8352, overall_isa_acceptance='NOT_VERIFIED',
        counts={key: dict(value) for key, value in counts.items()},
        by_original_family={key: {name: dict(value) for name, value in group.items()}
                            for key, group in by_family.items()},
        legacy_pass_but_raw_counter_diff=sum(row['legacy_v2'] == 'PASS' and row['raw_architectural_counter'] == 'FAIL' for row in flat),
        raw_counter_note='A raw-mask Counter mismatch is NOT automatically an effective-memory-address bug; wide fragments may repeat bytes removed by the single-flow projection.',
        original_receipt_aggregate_sha256=aggregate.hexdigest(),
        original_ledger_sha256=digest(run / 'completed-shapes.json'),
        reassessed_table_sha256=digest(out / 'reassessed-shapes.json'),
        scope='Existing actual events, separately scoped comparisons; no new DUT/ISA pass credit')
    atomic_json(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
