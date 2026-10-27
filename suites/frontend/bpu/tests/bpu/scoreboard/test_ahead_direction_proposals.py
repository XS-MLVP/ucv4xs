"""Corrupt proposals and source ownership; these pure tests earn no DUT credit."""
import ast
import json
import pickle
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.ahead_working_set import AheadWorkingSetChecks
from bpuverify.bpu.coverage.ahead_working_set import AheadWorkingSetCoverage
from bpuverify.bpu.coverage.cold_source_isolation import ColdSourceCoverage
from bpuverify.bpu.model.ahead_working_set import BASE, AheadWorkingSetProgram
from bpuverify.bpu.model.cold_source_isolation import ColdSourceProgram, MODES, SOURCES
from bpuverify.mbtb.model.semantic import Accepted, Branch, Feedback, MbtbReference, Source


def main_model(*, hit=False, kind=1, counter=2, taken=True, correction=True):
    main = MbtbReference()
    sources = ((Source(), Source(hit, 7, kind, 0, counter), Source(), Source(), Source()), (Source(),)*5)
    feedback = Feedback((BASE, BASE+16), sources,
                        (Branch(BASE+17, taken, 7, 1, mispredict=correction),))
    main.offered = Accepted(feedback, (0, 0))
    return main


def checks_for(main):
    program = AheadWorkingSetProgram('turnover', 'conditional', 'coexisting')
    checks = AheadWorkingSetChecks(program, AheadWorkingSetCoverage(program))
    checks.pipeline = NS(model=NS(sources=NS(main=main)), current_event=NS(tick=123))
    checks._direction_snapshot = tuple(dict(valid=0) for _ in range(8))
    return checks


def test_no_feedback_has_no_direction_proposal():
    assert MbtbReference().direction_proposals() == {}


@pytest.mark.parametrize('hit,kind,counter,taken,expected', (
    (False, 1, 2, True, None),
    (True, 2, 2, True, None),
    (True, 1, 2, True, 3),
    (True, 1, 3, True, 3),
    (True, 1, 2, False, 1),
    (True, 1, 0, False, 0),
))
def test_only_original_conditional_hit_owns_direction_learning(hit, kind, counter, taken, expected):
    main = main_model(hit=hit, kind=kind, counter=counter, taken=taken, correction=False)
    proposals = main.direction_proposals()
    if expected is None:
        assert proposals == {}
    else:
        assert proposals[0, 0].values == (None, expected, None, None)


def test_miss_payload_cannot_update_an_unrelated_way_and_preview_does_not_mutate():
    main = main_model()
    before = pickle.dumps(main)
    assert main.direction_proposals()[0, 0].values == (2, None, None, None)
    assert main.direction_proposals()[0, 0].values == (2, None, None, None)
    assert pickle.dumps(main) == before
    assert not main.recency and not main.memory and main.cycles == 0


@pytest.mark.parametrize('fault', ('extra-owner', 'wrong-row', 'wrong-value', 'missing-write'))
def test_proposal_guard_preserves_first_failure_and_serializable_original_context(fault):
    checks = checks_for(main_model())
    direction = dict(valid=1, bits=dict(row=0, mask=1, counters=(2, 0)))
    if fault == 'extra-owner': direction['bits'].update(mask=3, counters=(2, 3))
    elif fault == 'wrong-row': direction['bits']['row'] = 1
    elif fault == 'wrong-value': direction['bits']['counters'] = (3, 0)
    else: direction['valid'] = 0
    checks._direction_snapshot = (direction, *checks._direction_snapshot[1:])
    with pytest.raises(AssertionError, match='Main direction proposal'):
        checks.compare_direction_proposals()
    summary = checks.summary()
    json.dumps(summary)
    failure = summary['first_main_direction_failure']
    assert failure['expected'] == dict(valid=1, row=0, mask=1, values={'0': 2})
    assert failure['original_public_feedback']['sources'][0][1]['hit'] is False
    assert summary['checks']['failed'] == 1 and summary['checks']['first_failure']
    assert checks.coverage.groups['checked'].coverage == 0


def test_proposal_guard_ignores_payload_of_unselected_way_only():
    checks = checks_for(main_model())
    checks._direction_snapshot = (dict(valid=1, bits=dict(row=0, mask=1, counters=(2, 3))),
                                  *checks._direction_snapshot[1:])
    checks.compare_direction_proposals()
    assert checks.first_main_direction_failure is None


@pytest.mark.parametrize('fault', ('foreign-origin', 'wrong-pc', 'duplicate-source', 'duplicate-tick'))
def test_feedback_receipt_rejects_foreign_or_reused_ownership(fault):
    checks = checks_for(MbtbReference())
    edge = checks.program.edges(0)[0]
    token = NS(pc=edge.pc)
    source = NS(meta_tick=100, meta=NS(resolve={'pc':edge.pc}, redirect={'history':123}))
    branch = NS(position=edge.position, target=edge.target, kind=edge.kind, taken=True, action=0)
    checks.pipeline.source_token = lambda _: token
    resolution = NS(origin=token, branches=(branch,))
    if fault == 'foreign-origin': resolution.origin = deepcopy(token)
    elif fault == 'wrong-pc': token.pc += 8
    elif fault == 'duplicate-source': checks.feedback_receipts.append(dict(source_tick=100, accepted_tick=102))
    else: checks.feedback_receipts.append(dict(source_tick=99, accepted_tick=101))
    before = len(checks.feedback_receipts)
    with pytest.raises(AssertionError): checks.accepted(source, (101, resolution), edge)
    assert len(checks.feedback_receipts) == before and not checks.originals


@pytest.mark.parametrize('source', SOURCES)
@pytest.mark.parametrize('mode', MODES)
def test_cold_isolation_declares_the_same_single_branch_not_a_physical_scan(source, mode):
    program = ColdSourceProgram(source, mode)
    edge, = program.edges(0)
    assert edge.pc == edge.target == BASE and edge.kind == 1
    assert len(program.rules) == 5
    with pytest.raises(ValueError): program.edges(1)


@pytest.mark.parametrize('source', SOURCES)
def test_cold_isolation_launch_credit_requires_actual_disabled_control_after_initialization(source):
    coverage = ColdSourceCoverage(ColdSourceProgram(source, MODES[0]))
    enabled = [True]*7
    index = 0 if source == 'ubtb' else 3
    coverage.observe_launch(tuple(enabled), True, 1)
    enabled[index] = False
    coverage.observe_launch(tuple(enabled), False, 2)
    assert not coverage.reached
    coverage.observe_launch(tuple(enabled), True, 3)
    assert coverage.reached == {'isolated-source-disabled'}
    assert coverage.groups['checked'].coverage == 0


def test_cold_isolation_case_keeps_scheduler_and_signal_operations_out_of_test_logic():
    tree = ast.parse(Path('bpuverify/bpu/case/cold_source_isolation.py').read_text())
    forbidden = {'RisingEdge','FallingEdge','ClockCycles','gather','create_task','get_','set_'}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & forbidden
