#!/usr/bin/env python3
"""Compare real01/02 witnesses without promoting01's invalid source claim."""
import json
from pathlib import Path

from audit_coverage_points_v1 import sha256_file
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import native, point_sets, digest_keys
from audit_replay_cause_lifetimes_v1 import FULL, PAIRS, witness, calibration

ROOT = Path(__file__).resolve().parents[1]
OLD = 'replay-cause-lifetimes-contributor-regression-01'


def load(path):
    return json.loads(path.read_text())


def normalized(item):
    item = json.loads(json.dumps(item))
    for row in item['rows']:
        row.pop('PA', None)
        row.pop('initial_S3_last_beat', None)
        for grant in row['grants']:
            grant.pop('feedback_last_beat', None)
    return item


def audit():
    before, after = cases(OLD), cases(FULL)
    assert len(before) == len(after) == 1765 and before == after
    assert failure_digest(before) == failure_digest(after)
    second_run = 'replay-cause-lifetimes-contributor-regression-02'
    assert cases(second_run) == after
    rows = []
    for dut, _, directed in PAIRS:
        prefix = {'load_queue_replay': 'lrq', 'load_queue': 'lq', 'lsq_wrapper': 'lsq'}[dut]
        new = witness(FULL, dut)['witness']
        old_paths = [p for p in (ROOT / 'results' / OLD / 'cases').rglob('replay-cause-lifetime-witness.json') if load(p)['dut'] == dut]
        assert len(old_paths) == 1
        old = load(old_paths[0])
        assert normalized(new) == old
        second_paths = [p for p in (ROOT / 'results' / second_run / 'cases').rglob('replay-cause-lifetime-witness.json') if load(p)['dut'] == dut]
        assert len(second_paths) == 1
        second = load(second_paths[0])
        assert normalized(new) == normalized(second)
        assert sum(row['initial_S3_last_beat'] != bool(row['PA'] & 32) for row in second['rows']) == 60
        new_directed = witness(directed, dut)['witness']
        directed_paths = [p for p in (ROOT / 'results' / f'{prefix}-cause-lifetimes-after-01/cases').rglob('replay-cause-lifetime-witness.json')]
        assert len(directed_paths) == 1 and normalized(new_directed) == load(directed_paths[0])
        a, da = native(OLD, dut)
        b, db = native(FULL, dut)
        assert a['artifact']['build'] == b['artifact']['build']
        x, y = point_sets(da), point_sets(db)
        metrics = {}
        for kind in x:
            assert x[kind]['all'] == y[kind]['all'] and x[kind]['hit'] <= y[kind]['hit']
            metrics[kind] = dict(all_equal=True, old_hits_retained=True,
                newly_hit=len(y[kind]['hit'] - x[kind]['hit']), newly_hit_SHA256=digest_keys(y[kind]['hit'] - x[kind]['hit']))
        rows.append(dict(dut=dut, original_interface_witness=str(old_paths[0].relative_to(ROOT)),
            original_interface_witness_SHA256=sha256_file(old_paths[0]), normalized_complete_witness_equal=True,
            second_interface_witness=str(second_paths[0].relative_to(ROOT)), second_interface_witness_SHA256=sha256_file(second_paths[0]),
            normalized_second_run_UID_behavior_equal=True, second_run_PA5_mismatch_UIDs=60,
            normalized_directed_witness_equal=True, new_explicit_PA_and_10S3_lastBeat_fields_verified=True,
            native_metrics=metrics, raw_counter_bytes_equal=sha256_file(da) == sha256_file(db)))
    result = dict(format='lsq-Replay-cause-01-02-correction-equivalence-v1', old_interface_run=OLD, corrected_run=FULL,
        rows=rows, actual_results_all1765nodes_equal=True, all196failure_details_equal=True,
        calibration=calibration(), native_DUT_reruns=0,
        limits='Only03checks fixed256bitbus/32Bbeat source lastBeat=PA5. Removing explicit PA/lastBeat witness fields proves unchanged recorded UID/grant/wakeup/hold/release behavior, not01/02source legality. Native counter bytes and input pin stream hashes may differ because01/02/03drive different last_beat values; no hidden state or counters are overwritten, ORed or cached.')
    write_report(ROOT / 'results' / FULL / 'PA-lastBeat-correction-equivalence-v1.json', result)
    return result


if __name__ == '__main__':
    r = audit(); print(json.dumps(r, indent=2))
