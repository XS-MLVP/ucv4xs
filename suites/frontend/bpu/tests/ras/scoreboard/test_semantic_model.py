"""Semantic stack programs, source ownership and independent fault rejection."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from itertools import product

import pytest

from bpuverify.ras.checker.semantic import RasSemanticChecker
from bpuverify.ras.model.semantic import Events, RasReference, Recovery, Retirement, instruction_return
from bpuverify.ras.coverage.semantic import RasActionCoverage


def act(model, action, address=None):
    model.advance(Events(action, address))
    model.advance()
    return dict(model.projection)


def retire(model, before, action):
    model.advance(Events(retirement=Retirement(before['group'], before['calls'], action)))
    model.advance()
    model.advance()


def test_reference_only_imports_plain_data_not_native_state_or_driver():
    tree = ast.parse(Path('bpuverify/ras/model/semantic.py').read_text())
    assert [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] == ['dataclasses', 'copy']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize('position', (0, 1, 7, 15))
@pytest.mark.parametrize('offset', (0, 2, 14))
def test_return_address_uses_instruction_end_not_raw_start_pc(position, offset):
    assert instruction_return(0x40001000 + offset, position) == 0x40001002 + 2 * position


@pytest.mark.parametrize('depth', (1, 2, 7, 8, 12))
def test_lifo_program_across_retained_group_capacity(depth):
    model = RasReference()
    addresses = [0x40001000 + 0x100 * index for index in range(depth)]
    for index, address in enumerate(addresses, 1):
        actual = act(model, 2, address)
        assert actual == dict(top=address // 2, group=index % 8, repeat=0, calls=index)
    for index in range(depth - 1, -1, -1):
        actual = act(model, 1)
        assert actual['top'] == (addresses[index - 1] // 2 if index else 0)
        assert actual['group'] == index % 8


@pytest.mark.parametrize('repeats', (1, 2, 7, 8, 9, 12))
def test_repeated_calls_form_groups_of_eight_then_unwind(repeats):
    model = RasReference()
    act(model, 2, 0x40001000)
    for index in range(repeats):
        actual = act(model, 2, 0x40002000)
        assert actual['group'] == 2 + index // 8
        assert actual['repeat'] == index % 8
    for index in range(repeats - 1, -1, -1):
        actual = act(model, 1)
        assert actual['top'] == (0x40002000 // 2 if index else 0x40001000 // 2)
        assert actual['repeat'] == ((index - 1) % 8 if index else 0)


@pytest.mark.parametrize('action', range(4))
def test_actions_are_stack_algebra_not_exclusive_signal_comparisons(action):
    model = RasReference()
    act(model, 2, 0x40001000)
    before = act(model, 2, 0x40002000)
    actual = act(model, action, 0x40003000 if action & 2 else None)
    assert actual['top'] == (0x40001000 if action == 1 else 0x40003000 if action & 2 else 0x40002000) // 2
    assert actual['group'] == (2, 1, 3, 2)[action]
    assert actual['calls'] == before['calls'] + int(bool(action & 2))


@pytest.mark.parametrize('action', (0, 1, 2, 3))
def test_recovery_restores_owned_prefix_before_redo(action):
    model = RasReference()
    act(model, 2, 0x40001000)
    saved = act(model, 2, 0x40002000)
    act(model, 2, 0x40009000)
    act(model, 2, 0x4000a000)
    model.advance(Events(recovery=Recovery(saved['group'], saved['calls'], saved['repeat'],
                                         action, 0x40003000 if action & 2 else None)))
    assert model.projection['top'] == 0x4000a000 // 2
    model.advance()
    assert model.projection['top'] == (0x40001000 if action == 1 else 0x40003000 if action & 2 else 0x40002000) // 2
    assert model.projection['group'] == (2, 1, 3, 2)[action]


def test_unknown_checkpoint_cannot_initialize_reference_state():
    model = RasReference()
    model.advance(Events(recovery=Recovery(3, 4, 5)))
    with pytest.raises(AssertionError, match='owned checkpoint'):
        model.advance()


def test_retirement_requires_real_owned_source_address():
    model = RasReference()
    with pytest.raises(AssertionError, match='owned speculative source'):
        model.advance(Events(retirement=Retirement(2, 4, 2)))


def test_committed_calls_survive_speculative_queue_reuse():
    model = RasReference()
    for address in (0x40001000, 0x40002000):
        before = dict(model.projection)
        act(model, 2, address)
        retire(model, before, 2)
    for _ in range(20):
        before = dict(model.projection)
        act(model, 2, 0x40003000)
        retire(model, before, 2)
        before = dict(model.projection)
        act(model, 1)
        retire(model, before, 1)
    assert model.projection['top'] == 0x40002000 // 2
    assert act(model, 1)['top'] == 0x40001000 // 2


def test_commit_action_correction_composes_pop_then_push_without_actual_memory():
    model = RasReference()
    for address in (0x40001000, 0x40002000):
        before = dict(model.projection)
        act(model, 2, address)
        retire(model, before, 2)
    before = dict(model.projection)
    act(model, 2, 0x40003000)
    retire(model, before, 3)
    assert model.committed_head == 2
    assert model.committed[2].address == 0x40003000
    assert act(model, 1)['top'] == 0x40003000 // 2
    assert act(model, 1)['top'] == 0x40001000 // 2


def test_disabled_operations_preserve_owned_program():
    model = RasReference()
    act(model, 2, 0x40001000)
    before = model.program
    model.advance(Events(2, 0x40002000, enabled=False))
    assert model.program == before
    assert model.projection['top'] == 0x40001000 // 2


def test_near_overflow_blocks_both_actions_and_recovery_releases_credit():
    model = RasReference()
    saved = act(model, 2, 0x40001000)
    for index in range(1, 15):
        act(model, 2, 0x40001000 + 0x100 * index)
    before = model.program
    act(model, 2, 0x40009000)
    act(model, 1)
    assert model.program == before
    model.advance(Events(recovery=Recovery(saved['group'], saved['calls'], saved['repeat'])))
    model.advance()
    model.advance()
    assert act(model, 2, 0x4000a000)['top'] == 0x4000a000 // 2


def test_reset_cancels_pending_recovery_retirement_and_source_ownership():
    model = RasReference()
    before = dict(model.projection)
    act(model, 2, 0x40001000)
    model.advance(Events(recovery=Recovery(0, 0, 0), retirement=Retirement(before['group'], before['calls'], 2)))
    model.advance(Events(reset=True))
    model.advance()
    assert model.projection == dict(top=0, group=0, repeat=0, calls=0)
    assert model.retirements == 0
    assert not model.operations


@pytest.mark.parametrize('field', ('top', 'group', 'repeat', 'calls', 'commit_group', 'commit_calls'))
def test_wrong_projection_raises_with_state_without_resynchronization(field):
    checker = RasSemanticChecker()
    checker.initialized = True
    checker.capture_input(SimpleNamespace(tick=1), Events(2, 0x40001000))
    projection = checker.model.projection
    actual = dict(top=projection['top'], redirect_meta=dict(ssp=projection['group'], sctr=projection['repeat'],
        tosw=dict(flag=0, value=projection['calls'])), commit_meta=dict(ssp=projection['group'],
        tosw=dict(flag=0, value=projection['calls'])))
    if field == 'top':
        actual['top'] ^= 1
    elif field == 'group':
        actual['redirect_meta']['ssp'] ^= 1
    elif field == 'repeat':
        actual['redirect_meta']['sctr'] ^= 1
    elif field == 'calls':
        actual['redirect_meta']['tosw']['value'] ^= 1
    elif field == 'commit_group':
        actual['commit_meta']['ssp'] ^= 1
    else:
        actual['commit_meta']['tosw']['value'] ^= 1
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=2), actual)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == before


@pytest.mark.parametrize('actions', tuple(product(range(4), repeat=3)))
def test_stack_program_cross_checks_uncompressed_list_semantics(actions):
    model = RasReference()
    stack = [0x40001000, 0x40002000, 0x40003000]
    for address in stack:
        act(model, 2, address)
    for step, action in enumerate(actions):
        address = 0x40004000 + 0x100 * step
        # Independent plain-list algebra, no model operation/helper used to
        # calculate expected stack effects or the order of combined actions.
        if action & 1:
            stack.pop()
        if action & 2:
            stack.append(address)
        actual = act(model, action, address if action & 2 else None)
        assert actual['top'] == (stack[-1] // 2 if stack else 0)
        assert actual['group'] == len(stack)


def test_failed_combined_action_does_not_grant_checked_coverage():
    coverage = RasActionCoverage()
    checker = RasSemanticChecker(coverage=coverage)
    checker.initialized = True
    checker.capture_input(SimpleNamespace(tick=1), Events(3, 0x40001000))
    actual = dict(top=0, redirect_meta=dict(ssp=0,sctr=0,tosw=dict(flag=0,value=0)),
                  commit_meta=dict(ssp=0,tosw=dict(flag=0,value=0)))
    checker.capture_output(SimpleNamespace(tick=2), actual)
    assert coverage.groups['reached'].coverage > 0
    assert coverage.groups['checked'].coverage == 0


def test_retirement_coverage_cannot_be_closed_by_a_live_speculative_same_target():
    model, coverage = RasReference(), RasActionCoverage()
    before = dict(model.projection)
    act(model, 2, 0x40001000)
    event = Events(retirement=Retirement(before['group'], before['calls'], 3))
    model.advance(event)
    coverage.accept(event, model, 1)
    model.advance()
    coverage.consume(model, 4)
    assert coverage.groups['reached'].coverage > 0
    assert coverage.groups['checked'].coverage == 0
    coverage.accept(Events(reset=True), model, 5)
    assert not coverage.pending


def test_last_accepted_adjacent_call_is_reached_even_when_it_sets_overflow_guard():
    model, coverage = RasReference(), RasActionCoverage()
    for index in range(15):
        model.advance(Events(2, 0x40001000 + 0x100 * index))
    event = Events(3, 0x40003000)
    model.advance(event)
    assert model.guarded is True
    assert model.last_applied == ('speculation', 3, event.address)
    coverage.accept(event, model, 31)
    assert coverage.groups['reached'].coverage > 0


def test_blocked_combined_action_does_not_receive_reached_credit():
    model, coverage = RasReference(), RasActionCoverage()
    for index in range(16):
        model.advance(Events(2, 0x40001000 + 0x100 * index))
    event = Events(3, 0x40003000)
    model.advance(event)
    coverage.accept(event, model, 33)
    assert model.last_applied is None
    assert coverage.groups['reached'].coverage == 0


@pytest.mark.parametrize('field', ('head', 'address', 'counter'))
def test_wrong_retained_actual_state_cannot_seed_or_correct_the_model(field):
    checker = RasSemanticChecker()
    checker.initialized = True
    checker.capture_input(SimpleNamespace(tick=1), Events())
    public = dict(top=0, redirect_meta=dict(ssp=0,sctr=0,tosw=dict(flag=0,value=0)),
                  commit_meta=dict(ssp=0,tosw=dict(flag=0,value=0)))
    retained = dict(head=0, cells=[dict(address=0,counter=0) for _ in range(8)])
    if field == 'head':
        retained['head'] = 1
    else:
        retained['cells'][3][field] = 1
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=2), public, retained=retained)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == before
