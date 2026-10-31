"""Qualify failure explanations without granting acceptance coverage."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from ucv.runtime import historical_path

import pytest

from tools.run_vagq_exhaustive import atomic_json, digest
from suites.vector.vagq.maskgen.probe import bind_maskgen
from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate_protocol
from suites.vector.vagq.native import open_dut
from suites.vector.vagq.vagq.exhaustive import build_shape_sequence
from suites.vector.vagq.vagq.failure_review import analyze_failure
from suites.vector.vagq.vagq.scenario_matrix import legal_public_feature_cases


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = historical_path('vagq', 'results/vagq-exhaustive-20261020-v1')
REVIEW = historical_path('vagq', 'results/vagq-exhaustive-review-20261020-v1')


@pytest.mark.parametrize('ordinal,mutation', (
    (12, 'request_address'),
    (12, 'duplicate_admission'),
    (12, 'wrong_response'),
    (22, 'nonzero_mask'),
    (22, 'claimed_writeback'),
    (998, 'wrong_special_width'),
    (1196, 'wrong_wide_element'),
))
def test_explanation_rejects_counterevidence(tmp_path, ordinal, mutation):
    """Perturb COPIES only. No historical artifact or oracle is changed."""
    row = next(row for row in json.loads((ORIGINAL / 'failed-shapes.json').read_text())
               if row['ordinal'] == ordinal)
    case = tuple(legal_public_feature_cases())[ordinal]
    assert analyze_failure(row, case)['all_checks_satisfied']
    record = json.loads(Path(row['path']).read_text())
    events = record['events']
    if mutation == 'request_address':
        events['requests'][0]['address'] += 1
    elif mutation == 'duplicate_admission':
        events['admissions'].append(deepcopy(events['admissions'][0]))
    elif mutation == 'wrong_response':
        events['responses'][0]['issue_mask'] ^= 1
    elif mutation == 'nonzero_mask':
        next(req for req in events['requests'] if req['data_mask'] == 0)['data_mask'] = 1
    elif mutation == 'claimed_writeback':
        completed = {wb['entry'] for wb in events['writebacks']}
        entry = next(i for i in range(record['actual_sequence_uops']) if i not in completed)
        events['writebacks'].append(dict(entry=entry))
    elif mutation == 'wrong_special_width':
        events['requests'][0]['data_mask'] = 0xF
    else:
        events['requests'][0]['element'] += 2
    copy = tmp_path / 'perturbed-result.json'
    atomic_json(copy, record)
    changed = dict(row, path=str(copy), sha256=digest(copy))
    assert not analyze_failure(changed, case)['all_checks_satisfied']


@pytest.mark.vagq_isa_audit
def test_all_failure_producer_metadata_matches_native_maskgen(native_registration, tmp_path):
    if os.environ.get('RUN_VAGQ_FAILURE_PRODUCER_CHECK') != '1':
        pytest.skip('explicit failure-producer qualification only')
    output = Path(os.environ.get('PRODUCER_CHECK_LOG', str(tmp_path / 'producer-check')))
    output.mkdir(parents=True, exist_ok=True)
    journal_path = output / 'metadata.jsonl'
    if journal_path.exists():
        raise RuntimeError('will not overwrite a previous producer qualification')
    source_names = (
        'tests/vagq/test_failure_review_qualification.py',
        'maskgen/probe.py', 'maskgen/reference.py',
        'vagq/exhaustive.py', 'vagq/isa_reference.py',
        'vagq/scenario_matrix.py', 'native.py',
    )
    atomic_json(output / 'source-hashes.json', {name: digest(ROOT / name) for name in source_names})
    cases = tuple(legal_public_feature_cases())
    rows = json.loads((ORIGINAL / 'failed-shapes.json').read_text())
    receipts, total = [], 0
    with journal_path.open('x') as journal:
        with open_dut('MaskGen', tmp_path, clocked=False, register=native_registration) as dut:
            observe = bind_maskgen(dut)
            for row in rows:
                ordinal = row['ordinal']
                plan = build_shape_sequence(cases[ordinal], ordinal)
                samples = []
                for addr, _data in plan.packets:
                    request = MaskRequest(addr.v0_byte_mask, addr.deew, addr.ieew, addr.emul,
                        addr.vl, addr.vstart, addr.vma, addr.vta, addr.uop_idx, addr.nf)
                    expected, actual = evaluate_protocol(request), observe(request)
                    samples.append(dict(request=asdict(request), expected=expected, actual=actual,
                        matches=expected == actual))
                entry = dict(ordinal=ordinal, shape_id=row['shape_id'], samples=samples,
                    all_match=all(sample['matches'] for sample in samples),
                    acceptance_credit=False)
                journal.write(json.dumps(entry) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                receipts.append(dict(ordinal=ordinal, shape_id=row['shape_id'],
                    uops=len(samples), all_match=entry['all_match']))
                total += len(samples)
    atomic_json(output / 'summary.json', dict(shapes=len(receipts), uops=total,
        matching_shapes=sum(row['all_match'] for row in receipts),
        mismatches=[row for row in receipts if not row['all_match']],
        journal_sha256=hashlib.sha256(journal_path.read_bytes()).hexdigest(),
        scope='Native MaskGen producer/static-mask qualification, NOT ISA acceptance'))
    assert len(receipts) == 2278 and all(row['all_match'] for row in receipts)
