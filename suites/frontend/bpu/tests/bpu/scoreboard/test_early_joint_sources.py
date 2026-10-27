"""Six independent components advance once and retain explicitly owned domains."""
from copy import deepcopy
from dataclasses import replace, asdict
import pytest
from bpuverify.bpu.model.early_joint_sources import EarlyJointSources
from bpuverify.bpu.model.pipeline import Resolution
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.early_opposition import provider, resident
from bpuverify.utage.model.semantic import Entry, tag
from bpuverify.tage.model.semantic import TABLES
from tests.bpu.scoreboard._indirect_path_program import Program
from tests.bpu.scoreboard import test_joint_sources as old

def prepared(early):
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(old, 'JointLateSources', EarlyJointSources)
        enabled = list(old.ENABLED)
        enabled[1] = early
        patch.setattr(old, 'ENABLED', tuple(enabled))
        return old.joint_learned()


def shared_original(early):
    model, event, anchor, source = prepared(early)
    bank = model.sources
    tagged = bank.tage_snapshot(source, resolved=True)
    target = bank.target_snapshot(source, resolved=True)
    assert tagged.owner is target.owner is source.history
    assert tagged.read.pc == source.pc and target.read.pc == source.pc * 2
    assert target.prediction.provider is not None and target.prediction.target == old.INDIRECT_TARGET * 2
    assert target.prediction.confidence == 3
    values = source.lookup.values()
    slot = next(slot for slot in range(4) if values.get(f'{slot}.valid') and values[f'{slot}.position'] == old.CONDITION)
    assert values[f'{slot}.taken'] == 1 and dict(tagged.wanted)[f'{slot}.taken'] == 0
    assert tagged.late == target.late
    assert (target.late.branch.position, target.late.branch.target, target.late.source) == (
        old.INDIRECT, old.INDIRECT_TARGET, 'indirect-history')
    return dict(owner=source.sequence, same_logical_original=True)


def conditional_blocks_target(early):
    model, event, anchor, source = prepared(early)
    bank = model.sources
    memories = deepcopy(bank.indirect.memories)
    confidence = bank.target_snapshot(source, resolved=True).prediction.confidence
    initial = dict(bank.tage_snapshot(source, resolved=True).wanted)
    slot = next(slot for slot in range(4) if initial.get(f'{slot}.has_provider'))
    assert initial[f'{slot}.counter'] == 2
    if early:
        assert initial[f'{slot}.table'] == TABLES - 1
    else:
        assert initial[f'{slot}.table'] < TABLES - 1
    for number in range(2):
        request = old.resolve(model, event, source,
            old.outcome(old.CONDITION, old.CONDITION_TARGET, Kind.CONDITIONAL, wrong=True))
        assert bank.targets.feedback_for(request) is None
        source = old.query(model, event, anchor)
        if number == 0:
            # Highest-table NT2 becomes weak NT3 and follows taken Main;
            # a lower provider instead allocates a new weak T4 which follows
            # its old NT alternate.  Extra early work changes PRNG timing,
            # so those semantic preconditions must not be silently equated.
            expected = old.CONDITION if early else old.INDIRECT
            assert bank.tage_snapshot(source, resolved=True).late.branch.position == expected
    late = bank.tage_snapshot(source, resolved=True).late
    assert (late.branch.position, late.branch.target, late.source) == (old.CONDITION, old.CONDITION_TARGET, 'main')
    assert bank.target_snapshot(source, resolved=True).prediction.confidence == confidence
    assert bank.indirect.memories == memories
    return dict(unexecuted_target_feedback=0, indirect_memories_unchanged=True)


def original_immutability(early):
    model, event, anchor, source = prepared(early)
    bank = model.sources
    getters = (bank.tage_snapshot, bank.target_snapshot)
    frozen = tuple((getter(source), getter(source, resolved=True)) for getter in getters)
    metadata = deepcopy((bank.defined_tage_metadata(source), bank.defined_ittage_metadata(source)))
    old.resolve(model, event, source,
        old.outcome(old.CONDITION, old.CONDITION_TARGET, Kind.CONDITIONAL, wrong=True))
    old.query(model, event, anchor)
    assert tuple((getter(source), getter(source, resolved=True)) for getter in getters) == frozen
    assert (bank.defined_tage_metadata(source), bank.defined_ittage_metadata(source)) == metadata
    assert all(getter(source).read is saved[0].read for getter, saved in zip(getters, frozen, strict=True))
    return dict(domains=['tage-read', 'tage-result', 'target-read', 'target-result'], immutable=True)


def bad_execution_prefix(early):
    model, event, anchor, source = prepared(early)
    idle = old.quiet(model, event)
    bank = model.sources
    names = ('main', 'tage', 'indirect', 'ahead', 'short')
    states = tuple(deepcopy(getattr(bank, name).state()) for name in names)
    request = Resolution(source.history, source.pc, (
        old.outcome(old.CONDITION, old.CONDITION_TARGET, Kind.CONDITIONAL, wrong=True),
        old.outcome(old.INDIRECT, old.INDIRECT_TARGET, Kind.INDIRECT)), origin=source)
    with pytest.raises(ValueError, match='unexecuted younger'):
        model.advance(replace(idle, feedback=request))
    assert tuple(getattr(bank, name).state() for name in names) == states
    return dict(rejected_before_learning=True)


def source_lifetime(domain, fault):
    p = Program(0x40000001, flowing=False)
    detail = p.prepare()
    bank = p.model.sources
    token = p.model.published[detail['owner']]
    getters = dict(ahead=bank.snapshot, short=bank.short_snapshot, tage=bank.tage_snapshot,
        tage_resolved=lambda t: bank.tage_snapshot(t, resolved=True),
        target=bank.target_snapshot, target_resolved=lambda t: bank.target_snapshot(t, resolved=True))
    getter = getters[domain]
    assert getter(token).owner is token.history
    if fault == 'foreign':
        token = replace(token, history=replace(token.history))
    elif fault == 'retired':
        p.model.retire_source(token.sequence)
    elif fault == 'reset':
        p.model.advance(replace(p.event, reset=True))
    else:
        raise AssertionError('unknown mutation')
    with pytest.raises(ValueError, match='absent|retired|checkpoint'):
        getter(token)
    return dict(domain=domain, fault=fault, rejected=True)


def complete_teaching(pc, flowing):
    p = Program(pc, flowing=flowing)
    detail = p.prepare()
    bank = p.model.sources
    token = p.model.published[detail['owner']]
    short = bank.short_snapshot(token)
    assert provider(bank, token) is None
    index = short.prediction.frame.read.indices[0]
    identity = tag(token.pc, short.prediction.frame.context, 0)
    expected = Entry(True, identity, 2, 3)
    assert resident(bank, (0, index)) == expected
    snapshots = (bank.snapshot(token), short, bank.tage_snapshot(token), bank.tage_snapshot(token, resolved=True),
        bank.target_snapshot(token), bank.target_snapshot(token, resolved=True))
    cancelled = next(cycle.tokens[0] for _, cycle in p.repairs
        if cycle.tokens[2] is not None and cycle.tokens[2].sequence == token.sequence)
    for getter in (bank.snapshot, bank.short_snapshot, bank.tage_snapshot, bank.target_snapshot):
        with pytest.raises(ValueError, match='absent|retired|checkpoint'):
            getter(cancelled)
    restored = p.model.stages[0]
    assert restored.pc == p.a and restored.history.history == detail['restored_history']
    def original_short(t):
        value = provider(bank, t)
        return value is not None and (value.table, value.index, value.tag) == (0, index, identity) and value.counter < 4
    # Observe both published originals without inserting a ready pause between
    # them.  A pause after A changes the experiment and can repeatedly replay
    # the pre-learning source; a FIFO receipt collector must be passive here.
    new_a = new_b = None
    for _ in range(256):
        candidate = p.step().metadata
        if candidate is None:
            continue
        if candidate.sequence == restored.sequence:
            new_a = candidate
        if candidate.pc == p.pc and original_short(candidate):
            new_b = candidate
            break
    assert new_a is not None and new_a.sequence == restored.sequence
    assert new_b is not None, 'continuous flow must consume the exact learned short identity'
    p.quiet()
    value = provider(bank, new_b)
    assert new_b.early.branch.position == 4 and new_b.early.branch.kind == Kind.INDIRECT
    assert bank.target_snapshot(new_b, resolved=True).late.branch.target == p.a
    assert (bank.snapshot(token), bank.short_snapshot(token), bank.tage_snapshot(token),
        bank.tage_snapshot(token, resolved=True), bank.target_snapshot(token),
        bank.target_snapshot(token, resolved=True)) == snapshots
    assert new_b.sequence > new_a.sequence > token.sequence
    detail.update(short_learning=dict(index=index, tag=identity, entry=asdict(expected)),
        exact_restored_owner=new_a.sequence, fresh_consumer=dict(owner=new_b.sequence, provider=asdict(value)),
        all6snapshot_domains_immutable=True, cancelled_all_domains_released=True)
    return detail



def six_once():
    p = Program(0x40000001, flowing=False)
    p.source(pc=p.a)
    names = ('micro', 'main', 'ahead', 'short', 'tage', 'indirect')
    counts = dict.fromkeys(names, 0)
    with pytest.MonkeyPatch.context() as patch:
        for name in names:
            component = getattr(p.model.sources, name)
            original = component.advance
            def counted(*args, _name=name, _original=original, **kwargs):
                counts[_name] += 1
                return _original(*args, **kwargs)
            patch.setattr(component, 'advance', counted)
        for _ in range(8):
            p.step()
    assert counts == dict.fromkeys(names, 8)
    return counts




def test_all_six_components_advance_exactly_once():
    six_once()

@pytest.mark.parametrize('early', (False, True))
@pytest.mark.parametrize('function', (shared_original, conditional_blocks_target, original_immutability, bad_execution_prefix))
def test_explicit_original_domains_preserve_selection_and_execution_prefix(early, function):
    function(early)

@pytest.mark.parametrize('domain', ('ahead', 'short', 'tage', 'tage_resolved', 'target', 'target_resolved'))
@pytest.mark.parametrize('fault', ('foreign', 'retired', 'reset'))
def test_each_domain_rejects_foreign_retired_and_reset_origins(domain, fault):
    source_lifetime(domain, fault)

@pytest.mark.parametrize('pc', (0x40000001, 0x40000002))
@pytest.mark.parametrize('flowing', (False, True))
def test_complete_original_lifetime_and_fresh_consumers_remain_semantically_owned(pc, flowing):
    complete_teaching(pc, flowing)

