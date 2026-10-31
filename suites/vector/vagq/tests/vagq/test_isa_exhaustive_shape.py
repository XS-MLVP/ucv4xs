"""Durable exhaustive public-shape execution on the existing native platform."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time

import pytest
from toffee import Bin, CoverGroupDef, CoverPointDef

from suites.vector.vagq.native import open_dut
from suites.vector.vagq.vagq.exhaustive import ShapeSession, build_shape_sequence, run_shape_sequence
from suites.vector.vagq.vagq.scenario_matrix import feature_case_id, legal_public_feature_cases


pytestmark = [pytest.mark.vagq_exhaustive, pytest.mark.vagq_isa_audit]


def _write_json(path, value):
    temporary = path.with_suffix('.json.partial')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _journal(stream, value):
    stream.write(json.dumps(value, separators=(',', ':')) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def test_generated_dut_exhaustive_shape_sequences(native_registration, tmp_path):
    if os.environ.get('RUN_VAGQ_EXHAUSTIVE') != '1':
        pytest.skip('set RUN_VAGQ_EXHAUSTIVE=1 for the explicit exhaustive campaign')
    cases = tuple(legal_public_feature_cases())
    if os.environ.get('EXHAUSTIVE_ORDINALS'):
        ordinals = [int(value) for value in os.environ['EXHAUSTIVE_ORDINALS'].split(',')]
    else:
        start = int(os.environ.get('EXHAUSTIVE_START', 0))
        length = int(os.environ.get('EXHAUSTIVE_LIMIT', len(cases) - start))
        ordinals = list(range(start, start + length))
    if (not ordinals or len(set(ordinals)) != len(ordinals)
            or any(i < 0 or i >= len(cases) for i in ordinals)):
        raise ValueError('invalid/empty/duplicate exhaustive ordinal selection')
    root = Path(os.environ.get('VAGQ_SHAPE_LOG', str(tmp_path / 'shapes')))
    root.mkdir(parents=True, exist_ok=True)
    journal_path = root / 'progress.jsonl'
    if journal_path.exists():
        raise RuntimeError('refusing to overwrite an existing shape journal')
    shape_bins = {feature_case_id(case): Bin.values(feature_case_id(case)) for case in cases}
    coverage = CoverGroupDef('vagq_exhaustive_sequences_v2', (
        CoverPointDef('attempted_shape', shape_bins),
        CoverPointDef('passed_shape', {
            **shape_bins, 'not-passed': Bin.ignore(Bin.values('not-passed')),
        }),
        CoverPointDef('outcome', {name: Bin.values(name) for name in ('PASS', 'FAIL', 'ERROR')}),
    )).instantiate(
        'vagq.public_dut.exhaustive_sequences.v2',
        contract='Full VLMAX/producer-uops; complete byte multisets and multiplicity; separate synthetic consumer placement/v2',
    )
    completed = []
    with journal_path.open('x') as journal:
        with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
            session = ShapeSession(dut)
            for ordinal in ordinals:
                case = cases[ordinal]
                shape_id = feature_case_id(case)
                _journal(journal, dict(event='started', ordinal=ordinal, shape_id=shape_id, time=time.time()))
                started = time.monotonic()
                stimulus = dict(case=asdict(case), shape_id=shape_id)
                try:
                    plan = build_shape_sequence(case, ordinal)
                    stimulus = plan.stimulus()
                    # Persist the actual input sequence BEFORE executing it.
                    _write_json(root / f'{ordinal:05d}-stimulus.json', stimulus)
                    result = run_shape_sequence(session, case, ordinal, plan=plan)
                except Exception as error:
                    # Driver/model failures are not RTL counterexamples or DUT
                    # coverage passes. Keep them distinct and continue the list.
                    result = dict(ordinal=ordinal, shape_id=shape_id, status='ERROR',
                        errors=[f'{type(error).__name__}: {error}'])
                result['elapsed_seconds'] = time.monotonic() - started
                result['stimulus'] = stimulus
                result_path = root / f'{ordinal:05d}-result.json'
                _write_json(result_path, result)
                receipt = {key: value for key, value in result.items() if key not in (
                    'stimulus', 'events', 'missing_bytes', 'extra_bytes', 'duplicate_placements',
                )}
                receipt.update(event='finished', path=str(result_path),
                    sha256=hashlib.sha256(result_path.read_bytes()).hexdigest())
                _journal(journal, receipt)
                coverage.sample(dict(attempted_shape=shape_id,
                    passed_shape=shape_id if result['status'] == 'PASS' else 'not-passed',
                    outcome=result['status']))
                completed.append(receipt)
                if len(completed) % 16 == 0:
                    print(f'shapes {len(completed)}/{len(ordinals)}; '
                          f'PASS {sum(item["status"] == "PASS" for item in completed)}', flush=True)
    _write_json(root / 'summary.json', dict(requested=len(ordinals),
        completed=len(completed), passed=sum(r['status'] == 'PASS' for r in completed),
        failed=sum(r['status'] == 'FAIL' for r in completed),
        errors=sum(r['status'] == 'ERROR' for r in completed)))
    failures = [r for r in completed if r['status'] != 'PASS']
    assert not failures, f'{len(failures)}/{len(completed)} shape checks failed; first: {failures[:3]}'
