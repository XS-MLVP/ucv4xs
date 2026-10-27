"""Logical correction scope and falsified consumers, without DUT credit."""
import ast
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.ahead_correction import AheadCorrectionChecks
from bpuverify.bpu.coverage.ahead_correction import AheadCorrectionCoverage
from bpuverify.bpu.model.abtb.alias import mainbtb_route
from bpuverify.bpu.model.ahead_correction import AheadCorrectionProgram, RULES, SELECTIONS
from bpuverify.bpu.model.ahead_working_set import SIZES
from bpuverify.bpu.model.path_history import Checkpoint
from bpuverify.bpu.model.selection import Branch, Choice, Kind, StackAction, fallthrough


@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('selection', SELECTIONS)
def test_forward_skip_and_indirect_working_set_does_not_replace_main_identities(size, selection):
    program = AheadCorrectionProgram(size, selection)
    edges = program.edges(0)
    assert len(edges) == SIZES[size] and len({edge.pc for edge in edges}) == len(edges)
    assert edges[-1].target == edges[0].pc and edges[-1].kind == 3
    assert tuple(edge.target for edge in edges[:-1]) == tuple(edge.pc for edge in edges[1:])
    routes = Counter()
    for edge in edges:
        assert edge.pc <= edge.cfi_pc < edge.pc+8
        r = mainbtb_route(edge.pc, edge.position)
        routes[r['selected_physical_align'], r['internal_bank'], r['entry_set']] += 1
        if edge.kind == 1:
            assert edge.target == fallthrough(edge.pc).branch.target
            assert edge.cfi_pc+1 < edge.target  # Taken skips actual straight-line instructions.
    assert max(routes.values()) == 1
    assert len(program.selected) == len(edges)//(2 if selection == 'all' else 4)
    assert all(edge.kind == 1 for edge in edges if edge.pc in program.selected)


@pytest.mark.parametrize('selection', SELECTIONS)
def test_direction_endpoint_is_owned_by_selected_branches_not_their_physical_coordinates(selection):
    p = AheadCorrectionProgram('turnover', selection)
    for edge in p.edges(0):
        negative = p.desired_branch(edge, negative=True)
        positive = p.desired_branch(edge, negative=False)
        if edge.pc in p.selected:
            assert (negative['taken'], negative['kind'], negative['position']) == (False, 0, 15)
            assert (positive['taken'], positive['kind'], positive['position']) == (True, 1, 7)
            assert p.desired_counter(edge, negative=True) == 0
            assert p.desired_counter(edge, negative=False) == 3
        else:
            assert negative == positive
            assert p.desired_counter(edge, negative=True) == (3 if edge.kind == 1 else 2)


def fixture():
    p = AheadCorrectionProgram('turnover', 'alternate')
    checks = AheadCorrectionChecks(p, AheadCorrectionCoverage(p))
    checks.pipeline = NS(current_event=NS(tick=100))
    checks.begin(0, 'warm-negative')
    edge = p.edges(0)[0]
    branch = fallthrough(edge.pc).branch
    token = NS(pc=edge.pc, history=Checkpoint(1, 123, 1), sequence=1,
               early=Choice(branch, None, 'fallthrough'))
    frame = NS(valid=True, counters=(0, 0, 0, 0), hits=(True, False, False, False),
        read=NS(bank=0, row=0, entries=tuple(NS(position=edge.position, kind=edge.kind) for _ in range(4))))
    sources = NS(snapshot=lambda _:NS(frame=frame))
    cycle = NS(metadata=token, decisions=(None, None, Choice(branch, None, 'fallthrough')))
    return checks, NS(metadata_ready=True), cycle, sources, frame


def test_not_taken_consumer_is_valid_even_without_taken_ahead_choice():
    checks, events, cycle, sources, frame = fixture()
    checks.consumer(events, cycle, sources)
    assert checks._pending[0] == cycle.metadata.pc
    assert checks._pending[1]['counter'] == 0 and not checks._pending[1]['taken']
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('counter', 'early-direction', 'no-owned-frame', 'not-delivered'))
def test_transient_or_unowned_early_read_never_earns_endpoint_credit(fault):
    checks, events, cycle, sources, frame = fixture()
    if fault == 'counter': frame.counters = (1, 0, 0, 0)
    elif fault == 'early-direction':
        token = cycle.metadata
        token.early = Choice(Branch(7, token.early.branch.target, Kind.CONDITIONAL), 0, 'ahead')
    elif fault == 'no-owned-frame': frame.valid = False
    else: events.metadata_ready = False
    checks.consumer(events, cycle, sources)
    assert not checks._pending and checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('target', 'position', 'taken', 'kind'))
def test_wrong_final_direction_or_identity_is_a_comparison_failure_not_a_wait(fault):
    checks, events, cycle, sources, frame = fixture()
    before = cycle.decisions[2]
    branch = before.branch
    changes = {'target':dict(target=branch.target+8), 'position':dict(position=7),
               'taken':dict(taken=True), 'kind':dict(kind=Kind.CONDITIONAL)}
    cycle.decisions = (None, None, replace(before, branch=replace(branch, **changes[fault])))
    with pytest.raises(AssertionError, match='complete final outcome'):
        checks.consumer(events, cycle, sources)
    assert not checks._pending and checks.coverage.groups['checked'].coverage == 0


def test_correction_case_is_a_lifecycle_not_a_clock_script_or_raw_coordinate_scan():
    tree = ast.parse(Path('bpuverify/bpu/case/ahead_correction.py').read_text())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {'RisingEdge', 'FallingEdge', 'ClockCycles', 'gather', 'create_task', 'get_', 'set_'}
    text = Path('bpuverify/bpu/model/ahead_correction.py').read_text()
    assert not any(word in text for word in ('lcov', 'memory_signal', 'native_rows', 'toffee'))
    assert len(RULES) == 10


def test_capture_order_is_anchored_to_prediction_acceptance_not_later_metadata():
    tree = ast.parse(Path('bpuverify/bpu/env/ahead_correction.py').read_text())
    boundaries = [node.value.attr for node in ast.walk(tree) if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'boundary' for target in node.targets)
                  and isinstance(node.value, ast.Attribute)]
    assert boundaries == ['tick', 'prediction_tick']
