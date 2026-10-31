"""Reproduce all original failures; diagnostic interventions are NOT acceptance."""
from collections import Counter
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time

import pytest
from toffee import Bin, CoverGroupDef, CoverPointDef

from tools.run_vagq_exhaustive import atomic_json
from suites.vector.vagq.native import open_dut
from suites.vector.vagq.vagq.exhaustive import build_shape_sequence, observed_bytes, run_shape_sequence
from suites.vector.vagq.vagq.failure_review import ReviewSession
from suites.vector.vagq.vagq.scenario_matrix import legal_public_feature_cases


pytestmark = pytest.mark.vagq_isa_audit
ROOT = Path(__file__).resolve().parents[2]


def _run(session, case, ordinal, policy='baseline', *, extended=False):
    session.policy = policy
    plan = build_shape_sequence(case, ordinal)
    result = run_shape_sequence(session, case, ordinal, plan=plan,
                                max_idle=512 if extended else 64)
    result['actual_driven_lsu_responses'] = list(session.driven_responses)
    result['diagnostic_overrides'] = list(session.overrides)
    result['policy'] = policy
    result['extended_timeout'] = extended
    result['stimulus'] = plan.stimulus()
    result['acceptance_credit'] = False
    if policy != 'baseline':
        result['warning'] = 'Counterfactual ACK; original helper response records are PRE-override. Actual driven responses are separately recorded. NOT a DUT fix or ISA pass.'
    return result


def _same(baseline, original):
    keys = ('status', 'errors', 'actual_sequence_uops', 'admitted_uops',
            'writebacks', 'cycles', 'expected_byte_occurrences',
            'raw_request_byte_occurrences', 'placed_byte_occurrences',
            'missing_bytes', 'extra_bytes', 'duplicate_placements', 'events')
    return [key for key in keys if baseline[key] != original[key]]


def test_all_exhaustive_failures_reproduce_and_have_causal_evidence(native_registration, tmp_path):
    if os.environ.get('RUN_VAGQ_FAILURE_REVIEW') != '1':
        pytest.skip('explicit native review campaign only')
    original_root = ROOT / 'results/vagq-exhaustive-20261020-v1'
    review_root = ROOT / 'results/vagq-exhaustive-review-20261020-v1'
    reviews = json.loads((review_root / 'case-review.json').read_text())
    originals = {row['ordinal']: row for row in json.loads((original_root / 'failed-shapes.json').read_text())}
    if os.environ.get('REVIEW_ORDINALS'):
        selected = set(map(int, os.environ['REVIEW_ORDINALS'].split(',')))
        reviews = [row for row in reviews if row['ordinal'] in selected]
        assert len(reviews) == len(selected)
    else:
        start = int(os.environ.get('REVIEW_START', 0))
        count = int(os.environ.get('REVIEW_LIMIT', len(reviews) - start))
        reviews = reviews[start:start + count]
    assert reviews
    cases = tuple(legal_public_feature_cases())
    output = Path(os.environ.get('REVIEW_LOG', str(tmp_path / 'review')))
    output.mkdir(parents=True, exist_ok=True)
    journal_path = output / 'progress.jsonl'
    if journal_path.exists():
        raise RuntimeError('will not overwrite a prior review journal')
    group = CoverGroupDef('vagq_failure_reproduction_v1', (
        CoverPointDef('reproduced_shape', {row['shape_id']: Bin.values(row['shape_id'])
                                        for row in json.loads((review_root / 'case-review.json').read_text())}),
    )).instantiate('vagq.review.reproduced',
        contract='Original failures faithfully reproduced; NOT functional acceptance coverage')
    receipts = []
    with journal_path.open('x') as journal:
        with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
            session = ReviewSession(dut)
            for item in reviews:
                ordinal = item['ordinal']
                case = cases[ordinal]
                started = time.monotonic()
                journal.write(json.dumps(dict(event='started', ordinal=ordinal)) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                original = json.loads(Path(originals[ordinal]['path']).read_text())
                baseline = _run(session, case, ordinal)
                differences = _same(baseline, original)
                checks = dict(offline_explanation_verified=item['all_checks_satisfied'],
                              baseline_failure_reproduced=not differences)
                diagnostics = {}
                if item['family'] == 'zero_mask':
                    long = _run(session, case, ordinal, extended=True)
                    diagnostics['extended_wait'] = long
                    checks['extended_wait_still_stalls'] = long['events']['timed_out']
                    checks['extended_wait_has_identical_public_transactions'] = all(
                        baseline['events'][key] == long['events'][key]
                        for key in ('requests', 'admissions', 'writebacks', 'empty_requests', 'std_outputs'))
                    ack = _run(session, case, ordinal, 'ack_zero_only')
                    diagnostics['counterfactual_ack_zero'] = ack
                    checks['acking_only_zero_masks_unblocks_completion'] = (
                        not ack['events']['timed_out']
                        and Counter(x['entry'] for x in ack['events']['writebacks'])
                        == Counter(range(ack['actual_sequence_uops']))
                        and bool(ack['diagnostic_overrides'])
                        and all(x['original'] == 0 for x in ack['diagnostic_overrides']))
                elif item['family'] == 'special7':
                    onehot = _run(session, case, ordinal, 'onehot_all')
                    diagnostics['counterfactual_request_start_ack'] = onehot
                    plan = build_shape_sequence(case, ordinal)
                    raw, _, _ = observed_bytes(onehot['events']['requests'])
                    checks['request_start_acks_restore_all_architectural_requests'] = raw == plan.expected_bytes
                    checks['counterfactual_completion'] = not onehot['events']['timed_out']
                elif item['family'] == 'wide_offset':
                    control = _run(session, replace(case, index_eew=2), ordinal)
                    diagnostics['index_e32_control'] = control
                    checks['no_midflow_index_bank_split_control_passes'] = control['status'] == 'PASS'
                result = dict(ordinal=ordinal, shape_id=item['shape_id'], family=item['family'],
                    checks=checks, baseline_differing_fields=differences,
                    baseline=baseline, diagnostics=diagnostics,
                    elapsed_seconds=time.monotonic() - started,
                    review_status='VERIFIED' if all(checks.values()) else 'UNRESOLVED',
                    diagnostic_runs_are_acceptance=False)
                result_path = output / f'{ordinal:05d}-review.json'
                atomic_json(result_path, result)
                receipt = {key: value for key, value in result.items() if key not in ('baseline', 'diagnostics')}
                receipt.update(path=str(result_path), sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(), event='finished')
                journal.write(json.dumps(receipt) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                receipts.append(receipt)
                if not differences:
                    group.sample(dict(reproduced_shape=item['shape_id']))
                if len(receipts) % 16 == 0:
                    print(f'reviewed {len(receipts)}/{len(reviews)}', flush=True)
    atomic_json(output / 'receipts.json', receipts)
    unresolved = [row for row in receipts if row['review_status'] != 'VERIFIED']
    assert not unresolved, f'causal checks unresolved: {unresolved[:3]}'
