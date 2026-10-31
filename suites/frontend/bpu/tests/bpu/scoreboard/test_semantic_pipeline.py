"""Owned token ordering and reference-only predictor candidates."""
from dataclasses import replace
from itertools import product

import pytest

from suites.frontend.bpu.bpu.model.micro_sources import MicroOnlySources
from suites.frontend.bpu.bpu.model.pipeline import ENABLES, Events, Outcome, PipelineReference, Redirect, Resolution
from suites.frontend.bpu.bpu.model.selection import Branch, Choice, Kind, StackAction, fallthrough


PC = 0x40000800
OFF = (False,) * len(ENABLES)


class ScriptedSources:
    """Pure test source bank; fixture decisions never come from DUT outputs."""
    def __init__(self, scripted=None):
        self.scripted = {} if scripted is None else scripted
        self.steps = []

    def reset(self):
        self.steps.clear()

    def capture(self, pc, history):
        return dict(self.scripted.get(pc, {}))

    def choose(self, token, stage, enabled):
        return token.lookup.get(stage, fallthrough(token.pc))

    def advance(self, events, cycle, issued):
        self.steps.append((events, cycle, issued))

    def validate(self, events, cycle):
        pass


def boot(sources=None,*,pc=PC):
    model = PipelineReference(ScriptedSources() if sources is None else sources)
    event = Events(pc, enabled=OFF, initialization_complete=True)
    model.advance(replace(event, reset=True))
    assert not model.evaluate(event).fires[0]
    model.advance(event)
    return model, event


def published(model, event):
    for _ in range(4):
        model.advance(event)
    token = next(iter(model.published.values()))
    return token


def test_fallthrough_tokens_own_pc_and_metadata_not_current_s1_payload():
    model, event = boot()
    source = published(model, event)
    assert source.pc == PC and model.stages[0].pc == PC + 96
    assert source.history.history == 0
    assert model.checkpoint_for(source.history.metadata(), source_pc=PC) is source.history


def test_stalled_s1_does_not_stall_older_metadata_even_when_metadata_ready_is_false():
    model, event = boot()
    published(model, event)
    held = model.stages[0]
    stalled = replace(event, prediction_ready=False, metadata_ready=False)
    first = model.advance(stalled)
    assert first.fires == (False, False, True, True)
    assert first.metadata is not None
    model.advance(stalled)
    settled = model.advance(stalled)
    assert model.stages == (held, None, None)
    assert settled.fires == (False, False, False, False)
    assert settled.presented[0] is held


def test_external_recovery_replaces_held_token_without_a_ready_handshake():
    model, event = boot()
    source = published(model, event)
    stalled = replace(event, prediction_ready=False)
    model.advance(stalled)
    old = model.stages[0]
    target = PC + 0x7F9
    cycle = model.advance(replace(stalled, redirect=Redirect(source.history, PC + 4, target, True)))
    assert cycle.fires[0] and not cycle.fires[1]
    assert cycle.presented[0] is old
    assert cycle.flushes == (True, True, True)
    assert model.stages[0].sequence != old.sequence and model.stages[0].pc == target
    assert model.stages[0].history.history == ((PC + 4) % 512) * 16 ^ ((target // 2) % 32768)
    assert model.stages[1:] == (None, None)


@pytest.mark.parametrize('ready', (False, True))
def test_middle_repair_squashes_younger_token_even_when_it_would_fire(ready):
    corrected = Choice(Branch(4, PC + 0x100, Kind.DIRECT), 0, 'main')
    model, event = boot(ScriptedSources({PC: {2: corrected, 3: corrected}}))
    model.advance(event)
    model.advance(event)
    younger = model.stages[0]
    cycle = model.advance(replace(event, prediction_ready=ready))
    assert cycle.middle_repair and not cycle.final_repair
    assert cycle.fires[1] == ready and cycle.flushes[0]
    assert model.stages[1] is None
    assert model.stages[0].pc == corrected.branch.target
    assert cycle.presented[0].pc == PC and cycle.presented[0].sequence != younger.sequence
    assert model.stages[2].pc == PC


def test_late_target_repair_dominates_middle_direction_repair_and_rolls_back_history():
    first = Choice(Branch(4, PC + 0x100, Kind.DIRECT), None, 'micro')
    middle = Choice(replace(first.branch), 0, 'main')
    last = Choice(replace(first.branch, target=PC + 0x200), 0, 'main')
    younger = Choice(Branch(6, PC + 0x300, Kind.DIRECT), 0, 'main')
    model, event = boot(ScriptedSources({PC: {1:first,2:middle,3:last}, PC+0x100:{2:younger,3:younger}}))
    for _ in range(3):
        model.advance(event)
    cycle = model.advance(event)
    assert cycle.middle_repair and cycle.final_repair
    assert cycle.presented[0].pc == PC and cycle.presented[1] == last
    assert model.stages[0].pc == last.branch.target
    assert model.stages[1:] == (None, None)
    assert model.history.taken_edges == 1


def test_retirement_releases_checkpoints_without_leaking_a_continuous_stream():
    model, event = boot()
    for _ in range(1000):
        cycle = model.advance(event)
        if cycle.metadata is not None:
            model.retire_source(cycle.metadata.sequence)
        assert len(model.history.owned) <= 3
    assert not model.published


@pytest.mark.parametrize('fault', ('foreign', 'retired', 'unpublished', 'wrong-pc'))
def test_only_published_owned_sources_can_drive_external_feedback(fault):
    model, event = boot()
    source = published(model, event)
    if fault == 'foreign':
        other, other_event = boot()
        source = published(other, other_event)
    elif fault == 'retired':
        model.retire_source(source.sequence)
    elif fault == 'unpublished':
        source = model.stages[0]
    pc = source.pc + (16 if fault == 'wrong-pc' else 0)
    with pytest.raises(ValueError, match='published'):
        model.advance(replace(event, feedback=Resolution(source.history, pc, ())))


def test_micro_source_bank_learns_only_from_semantic_resolution_and_detects_later_repair():
    model, event = boot(MicroOnlySources())
    active = replace(event, enabled=(True, *OFF[1:]))
    source = published(model, active)
    feedback = Resolution(source.history, PC, (Outcome(4, PC + 0x200, Kind.DIRECT, True, mispredict=True),))
    model.advance(replace(active, feedback=feedback))
    model.advance(active)
    model.advance(replace(active, redirect=Redirect(source.history, PC + 4, PC, True)))
    current = model.evaluate(active)
    assert current.decisions[0].branch.taken and current.decisions[0].branch.target == PC + 0x200
    model.advance(active)
    repair = model.evaluate(active)
    assert repair.middle_repair and not repair.decisions[1].branch.taken


def test_missing_other_predictor_adapters_raise_instead_of_silently_ignoring_training():
    model, event = boot(MicroOnlySources())
    all_enabled = replace(event, enabled=(True,) * len(ENABLES))
    source = published(model, all_enabled)
    with pytest.raises(NotImplementedError, match='full source-bank'):
        model.advance(replace(all_enabled, feedback=Resolution(source.history, PC, ())))


def test_control_has_two_unconditional_cycles_of_delay_even_across_reset():
    model, event = boot()
    on = replace(event, enabled=(True,) * len(ENABLES))
    assert model.evaluate(on).enabled == OFF
    model.advance(on)
    assert model.evaluate(on).enabled == OFF
    model.advance(replace(event, reset=True))
    assert model.evaluate(event).enabled == on.enabled
    assert not model.evaluate(event).fires[0]  # Reset also cleared initialized service.
    model.advance(event)
    assert model.evaluate(event).enabled == OFF
    assert model.evaluate(event).fires[0]


def test_initialization_is_sticky_and_issue_waits_for_its_following_cycle():
    model = PipelineReference(ScriptedSources())
    waiting = Events(PC, enabled=OFF)
    model.advance(replace(waiting, reset=True))
    for _ in range(3):
        assert not model.advance(waiting).fires[0]
    assert not model.advance(replace(waiting, initialization_complete=True)).fires[0]
    assert model.advance(waiting).fires[0]
    assert model.initialized


@pytest.mark.parametrize('action', (StackAction.RETURN, StackAction.CALL, StackAction.RETURN_AND_CALL))
def test_missing_return_stack_adapter_rejects_learning_before_mutating_owned_state(action):
    model, event = boot(MicroOnlySources())
    source = published(model, event)
    feedback = Resolution(source.history, PC, (Outcome(4, PC + 0x200, Kind.DIRECT, True, action),))
    before = model.state(), model.sources.micro.state(), dict(model.history.owned)
    with pytest.raises(NotImplementedError, match='return-stack adapter'):
        model.advance(replace(event, feedback=feedback))
    assert (model.state(), model.sources.micro.state(), dict(model.history.owned)) == before


def test_equal_low_metadata_cannot_associate_different_full_owned_histories():
    model, event = boot()
    first = published(model, event)
    # Pure association fault fixture: distinct owned history has identical
    # public low bits and circular pointer, but a different high path word.
    model.history.history = 1 << 40
    other = model.history.checkpoint()
    token = replace(first, sequence=first.sequence + 100, history=other)
    model.published[token.sequence] = token
    assert first.history.metadata() == other.metadata()
    with pytest.raises(ValueError, match='aliases different history owners'):
        model.checkpoint_for(first.history.metadata())


@pytest.mark.parametrize('occupied,ready,recovery,repair2,repair3', tuple(product(
    product((False,True), repeat=3), (False,True), (False,True), (False,True), (False,True))))
def test_control_priority_over_all_stage_occupancies(occupied, ready, recovery, repair2, repair3):
    """Finite semantic control truth table, not hardware bank/set enumeration."""
    micro = Choice(Branch(4, PC + 0x100, Kind.DIRECT), None, 'micro')
    main = Choice(replace(micro.branch), 0, 'main')
    correction = Choice(replace(main.branch, target=PC + 0x200), 0, 'main')
    model, event = boot(ScriptedSources({PC: {1:micro,2:main,3:correction}}))
    source = published(model, event)
    tokens = []
    for stage, live in enumerate(occupied, 1):
        if not live:
            tokens.append(None)
            continue
        history = model.history.checkpoint()
        lookup = {1:micro, 2:fallthrough(PC) if repair2 else main,
                  3:correction if repair3 else main}
        tokens.append(replace(source, sequence=100+stage, history=history,
            lookup=lookup, early=micro, middle=main, middle_corrected=False))
    model.stages = tuple(tokens)
    event = replace(event, prediction_ready=ready, metadata_ready=False,
        redirect=Redirect(source.history, PC+4, PC+0x400, False) if recovery else None)
    cycle = model.evaluate(event)
    mid, late = occupied[1] and repair2, occupied[2] and repair3
    assert cycle.fires == (not occupied[0] or ready or recovery or mid or late,
                          occupied[0] and ready, occupied[1], occupied[2])
    assert cycle.flushes == (recovery or mid or late, recovery or late, recovery)
    assert (cycle.middle_repair,cycle.final_repair) == (mid,late)
    wanted_stage = 2 if late else 1 if mid else 0 if occupied[0] else None
    assert cycle.presented == (None if wanted_stage is None else (tokens[wanted_stage],cycle.decisions[wanted_stage]))
    expected_pc = (PC+0x400 if recovery else PC+0x200 if late else fallthrough(PC).branch.target if mid
                   else micro.branch.target if occupied[0] else model.pc)
    assert cycle.next_pc == expected_pc
