"""Independent reset transitions, checked-credit gates and damaged consumers."""
from copy import deepcopy
from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.mbtb.model.semantic import (
    Branch as Outcome, Events, Feedback, MbtbReference, Source, tag)
from bpuverify.mbtb.transaction.types import MbtbEntry, MbtbPrediction
from bpuverify.mbtb.model.reset_lifetime import Program, PROFILES, RULES
from bpuverify.mbtb.coverage.reset_lifetime import Coverage
from bpuverify.mbtb.checker.reset_lifetime import Checks



def feedback(model, branch, *, taken=True, allocate=True):
    frame = model.lookup_snapshot(branch.pc)
    sources = tuple(tuple(Source(entry.valid and entry.tag == tag(read.pc),
        16*read.ordinal+entry.position, entry.kind, entry.action, counter)
        for entry, counter in zip(read.entries, read.counters, strict=True))+(Source(),) for read in frame.banks)
    return Feedback((branch.pc, (branch.pc//16+1)*16), sources,
                    (Outcome(branch.target, taken, branch.position, branch.kind, 0, allocate),))


def settled(model, request):
    model.advance(Events(feedback=request))
    # Pure model transition bound: accepted -> learned -> retained -> served.
    # These are not DUT delays or testcase settling assumptions.
    for _ in range(8):
        model.advance()


@pytest.mark.parametrize('phase', ('accepted', 'direction-pending', 'entry-pending', 'committed'))
def test_reset_ends_each_old_semantic_obligation_and_cannot_replay_it(phase):
    program, model = Program('registered-feedback'), MbtbReference()
    request = feedback(model, program.old[0])
    if phase == 'committed':
        settled(model, request)
        assert any(entry.valid for entry in model.memory.values())
    else:
        busy = dict(pc=program.old[0].pc, select=True, advance=True)
        model.advance(Events(feedback=request, **busy))
        if phase != 'accepted':
            model.advance(Events(**busy))
            assert any(queue.pending for queue in model.directions.values())
        if phase == 'entry-pending':
            model.advance(Events(**busy))
            assert any(cache.outstanding for cache in model.entries.values())
    original = model.lookup_snapshot(program.old[0].pc)
    frozen = deepcopy(original)
    model.advance(Events(reset=True))
    assert not model.memory and not model.counters and not model.recency
    assert model.offered is model.frame is model.read is None
    assert not model.cleanup and not any(model.entry_offers.values())
    assert not any(cache.records or cache.outstanding for cache in model.entries.values())
    assert not any(queue.pending for queue in model.directions.values())
    # Release every modeled service opportunity; no unowned old write returns.
    for _ in range(8):
        model.advance()
    assert not model.memory and not model.counters
    settled(model, feedback(model, program.new[0]))
    values = model.lookup_snapshot(program.new[0].pc).values()
    active = next(slot for slot in range(10) if values[f'{slot}.valid'])
    assert values[f'{active}.counter'] == 2
    assert values[f'{active}.target'] == program.new[0].target
    assert original == frozen


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('missing', RULES)
def test_partial_reset_lifetime_cannot_obtain_checked_credit(profile, missing):
    coverage = Coverage(Program(profile))
    for rule in RULES:
        if rule != missing:
            coverage.reach(rule)
    with pytest.raises(AssertionError, match='incomplete'):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
def test_checked_credit_requires_every_obligation_and_is_granted_once(profile):
    coverage = Coverage(Program(profile))
    for rule in RULES:
        coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == 25
    with pytest.raises(AssertionError):
        coverage.finish()
    with pytest.raises(ValueError):
        coverage.reach(RULES[0])


def prediction(branch=None, *, counter=2):
    entries = [MbtbEntry(0, 0, 0, 0, 0, 0) for _ in range(10)]
    meta = [[dict(rawHit=0, position=0, counter_value=0) for _ in range(5)] for _ in range(2)]
    if branch is not None:
        entries[0] = MbtbEntry(1, int(counter >= 2), branch.target, branch.position, branch.kind, 0)
        meta[0][0] = dict(rawHit=1, position=branch.position, counter_value=counter)
    return MbtbPrediction(tuple(entries), meta)


@pytest.mark.parametrize('fault', ('visible-old', 'filtered-old'))
def test_cold_check_rejects_visible_and_filtered_resurrection(fault):
    program = Program('committed')
    result = prediction(program.old[0])
    if fault == 'filtered-old':
        result = replace(result, entries=tuple(replace(entry, valid=0) for entry in result.entries))
    with pytest.raises(ScoreboardMismatch):
        Checks(program).cold(result)


@pytest.mark.parametrize('fault', ('target', 'kind', 'action', 'position', 'counter', 'taken', 'missing', 'duplicate'))
def test_new_consumer_rejects_old_lifetime_and_corrupted_branch_fields(fault):
    program = Program('committed')
    branch = program.new[0]
    result = prediction(branch)
    entries = list(result.entries)
    if fault == 'counter':
        result.meta_entries[0][0]['counter_value'] = 0
    elif fault == 'missing':
        entries[0] = replace(entries[0], valid=0)
    elif fault == 'duplicate':
        entries[1] = entries[0]
    else:
        attribute = dict(kind='branch_type', action='ras_action').get(fault, fault)
        value = program.old[0].target if fault == 'target' else getattr(entries[0], attribute) ^ 1
        entries[0] = replace(entries[0], **{attribute: value})
    result = replace(result, entries=tuple(entries))
    with pytest.raises(ScoreboardMismatch) as error:
        Checks(program).resident(result, branch, counter=2)
    assert error.value.context.request['program'] == program.state()


@pytest.mark.parametrize('profile', ('', 'cold-only', 'random-bank', None, 0, True))
def test_unqualified_profile_cannot_silently_shrink_the_lifetime(profile):
    with pytest.raises(ValueError):
        Program(profile)
