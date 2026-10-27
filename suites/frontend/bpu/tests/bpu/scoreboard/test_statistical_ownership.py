"""Pure SC ownership prerequisites; no integrated-DUT functional credit."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.model.pipeline import Resolution
from bpuverify.bpu.model.sc.ownership import OwnedStatisticalReference
from bpuverify.bpu.model.selection import Kind
from bpuverify.sc.model.semantic import Events
from bpuverify.sc.transaction.types import ScHistory
from tests.bpu.scoreboard import test_joint_sources as joint


def prepared(taken=False):
    model, event, anchor, token = joint.joint_learned()
    if taken:
        for _ in range(2):
            joint.resolve(model, event, token,
                joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL, wrong=True))
            token = joint.query(model, event, anchor)
    tagged = dict(model.sources.snapshot(token, resolved=True).wanted)
    slot = next(slot for slot in range(4) if tagged.get(f'{slot}.has_provider'))
    assert bool(tagged[f'{slot}.taken']) is taken
    return model, event, anchor, token, slot


def history(token, *, valid=True, nonzero=False):
    return ScHistory(path=token.history.history % (1 << 31),
        global_history=0xA5 if nonzero else 0, backward=9 if nonzero else 0,
        loop=13 if nonzero else 0, common_valid=valid)


def select(sc, model, token, *, enabled=True, context=None):
    context = history(token) if context is None else context
    sc.capture(token, history=context)
    result = sc.resolve(token, direction=model.sources.snapshot(token, resolved=True),
        target=model.sources.target_snapshot(token, resolved=True), enabled=enabled)
    sc.publish(token, history=context)
    return result


def teach(sc, token, *, taken):
    request = Resolution(token.history, token.pc, (
        joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL, taken=taken),
        *(tuple() if taken else (joint.outcome(joint.INDIRECT, joint.INDIRECT_TARGET, Kind.INDIRECT),))), origin=token)
    transaction = sc.feedback_for(request)
    sc.advance(Events(feedback=transaction, feedback_context=sc.snapshot(token).read.context))
    while sc.model.learning is not None or sc.model.pending or any(
            row is not None and row.dirty for banks in sc.model.writes for cache in banks for row in cache.rows):
        sc.advance(Events())
    return transaction


@pytest.mark.parametrize('taken', (False, True))
@pytest.mark.parametrize('nonzero', (False, True))
def test_learned_sc_changes_execution_prefix_without_mutating_other_predictors(taken, nonzero):
    model, event, anchor, token, slot = prepared(not taken)
    sc = OwnedStatisticalReference()
    # Repeated logical queries, not repeated submission of one old metadata.
    # This is a component qualification, not proof of integrated SC/FTQ timing.
    number = 5 if not taken else 4
    originals = []
    for _ in range(number):
        value = select(sc, model, token, context=history(token, nonzero=nonzero))
        originals.append((token, value))
        teach(sc, token, taken=taken)
        token = joint.query(model, event, anchor)
    result = select(sc, model, token, context=history(token, nonzero=nonzero))
    assert result.prediction.used[slot] == 1
    assert result.prediction.directions[slot] == int(taken)
    assert result.late.branch.position == (joint.CONDITION if taken else joint.INDIRECT)
    assert result.late.branch.target == (joint.CONDITION_TARGET if taken else joint.INDIRECT_TARGET)
    assert result.late.source == ('main' if taken else 'indirect-history')
    assert all(sc.snapshot(original, resolved=True) is frozen for original, frozen in originals)
    # Resolve/capture of the SC domain cannot change any other model at all.
    before = tuple(deepcopy(getattr(model.sources, name).state()) for name in ('main', 'tage', 'indirect'))
    metadata = result.prediction.metadata()
    metadata['scPred'] = (1 - int(taken),) * 4
    assert result.prediction.directions[slot] == int(taken)
    assert before == tuple(getattr(model.sources, name).state() for name in ('main', 'tage', 'indirect'))


@pytest.mark.parametrize('disabled', (False, True))
@pytest.mark.parametrize('tage_taken', (False, True))
def test_unused_or_disabled_sc_cannot_claim_direction_authority(disabled, tage_taken):
    model, _, _, token, slot = prepared(tage_taken)
    sc = OwnedStatisticalReference()
    result = select(sc, model, token, enabled=not disabled)
    assert result.prediction.sums[slot] == 5
    assert result.prediction.used[slot] == 0
    assert result.late == model.sources.target_snapshot(token, resolved=True).late


@pytest.mark.parametrize('domain', ('statistical', 'tage', 'target'))
@pytest.mark.parametrize('fault', ('equal-checkpoint', 'other-original'))
def test_equal_pc_and_history_encoding_cannot_rebind_any_original_domain(domain, fault):
    model, event, anchor, token, _ = prepared()
    sc = OwnedStatisticalReference()
    sc.capture(token, history=history(token))
    foreign = (replace(token, history=replace(token.history)) if fault == 'equal-checkpoint'
               else joint.query(model, event, anchor))
    if domain == 'statistical':
        with pytest.raises(ValueError, match='absent|checkpoint'):
            sc.snapshot(foreign)
    else:
        wanted = model.sources.snapshot(token, resolved=True)
        target = model.sources.target_snapshot(token, resolved=True)
        if domain == 'tage':
            wanted = replace(wanted, owner=foreign.history)
        else:
            target = replace(target, owner=foreign.history)
        with pytest.raises(ValueError, match='exact original checkpoint'):
            sc.resolve(token, direction=wanted, target=target)
    assert not sc.resolved and sc.model.commits == 0


@pytest.mark.parametrize('ending', ('retire', 'reset'))
def test_retired_and_reset_sources_lose_both_read_and_final_evidence(ending):
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    select(sc, model, token)
    if ending == 'retire':
        sc.retire(token)
    else:
        sc.advance(Events(reset=True))
    for resolved in (False, True):
        with pytest.raises(ValueError, match='absent|retired'):
            sc.snapshot(token, resolved=resolved)


def test_original_selection_is_frozen_and_cannot_be_recomputed_with_new_weights():
    model, event, anchor, token, slot = prepared()
    sc = OwnedStatisticalReference()
    old = select(sc, model, token)
    for _ in range(4):
        teach(sc, token, taken=True)
        token = joint.query(model, event, anchor)
        fresh = select(sc, model, token)
    assert fresh.prediction.used[slot] == 1 and fresh.prediction.directions[slot] == 1
    assert old.prediction.used[slot] == 0 and old.prediction.sums[slot] == 5
    original = next(row for row in model.published.values() if row.history is old.original.owner)
    with pytest.raises(ValueError, match='already frozen'):
        sc.resolve(original, direction=model.sources.snapshot(original, resolved=True),
            target=model.sources.target_snapshot(original, resolved=True))


def test_original_read_survives_younger_weight_commit_before_selection():
    model, event, anchor, old, slot = prepared()
    sc = OwnedStatisticalReference()
    sc.capture(old, history=history(old))
    token = joint.query(model, event, anchor)
    select(sc, model, token)
    teach(sc, token, taken=True)
    result = sc.resolve(old, direction=model.sources.snapshot(old, resolved=True),
        target=model.sources.target_snapshot(old, resolved=True))
    assert result.prediction.sums[slot] == 5
    token = joint.query(model, event, anchor)
    assert select(sc, model, token).prediction.sums[slot] == 15


def test_unexecuted_feedback_is_rejected_but_real_mispredicted_prefix_is_accepted():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    source = select(sc, model, token)
    assert source.late.branch.position == joint.INDIRECT
    invalid = Resolution(token.history, token.pc, (
        joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL),
        joint.outcome(joint.INDIRECT, joint.INDIRECT_TARGET, Kind.INDIRECT)), origin=token)
    before = deepcopy(sc.model.state())
    with pytest.raises(ValueError, match='unexecuted younger'):
        sc.feedback_for(invalid)
    assert sc.model.state() == before
    # Actual execution is allowed to disagree with the original prediction.
    legal = replace(invalid, branches=invalid.branches[:1])
    feedback = sc.feedback_for(legal)
    assert len(feedback.branches) == 1 and feedback.branches[0].actual_taken == 1
    assert feedback.meta == source.prediction.metadata()
    assert feedback.history is source.original.history


def test_missing_or_foreign_semantic_history_cannot_seed_the_reference():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    with pytest.raises(TypeError, match='independent semantic history'):
        sc.capture(token, history={})
    with pytest.raises(ValueError, match='path history'):
        sc.capture(token, history=replace(history(token), path=history(token).path ^ 1))
    assert not sc.reads and not sc.resolved


def test_sc_provider_feature_comes_from_raw_provider_not_the_chosen_alternate_direction():
    model, event, anchor, token, _ = prepared()
    joint.resolve(model, event, token,
        joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL, wrong=True))
    token = joint.query(model, event, anchor)
    direction = model.sources.snapshot(token, resolved=True)
    tagged = dict(direction.wanted)
    slot = next(slot for slot in range(4) if tagged.get(f'{slot}.has_provider'))
    assert tagged[f'{slot}.counter'] == 4 and tagged[f'{slot}.taken'] == 0
    assert tagged[f'{slot}.use_provider'] == 0
    sc = OwnedStatisticalReference()
    result = select(sc, model, token)
    assert result.prediction.metadata()['scBiasLowerBits'][slot] == 3
    assert result.prediction.metadata()['tagePred'][slot] == 1
    assert result.prediction.branches[slot].tage_counter == 4
    assert result.late.branch.position == joint.INDIRECT


@pytest.mark.parametrize('domain', ('statistical', 'tage', 'target'))
def test_correct_owner_does_not_excuse_foreign_read_pc(domain):
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    sc.capture(token, history=history(token))
    direction = model.sources.snapshot(token, resolved=True)
    target = model.sources.target_snapshot(token, resolved=True)
    if domain == 'statistical':
        bad = replace(token, pc=token.pc + 1)
        with pytest.raises(ValueError, match='checkpoint owner'):
            sc.snapshot(bad)
    else:
        if domain == 'tage':
            direction = replace(direction, read=replace(direction.read, pc=token.pc + 1))
        else:
            target = replace(target, read=replace(target.read, pc=token.pc * 2 + 2))
        with pytest.raises(ValueError, match='read PC'):
            sc.resolve(token, direction=direction, target=target)
    assert not sc.resolved


@pytest.mark.parametrize('enabled', (0, 1, None, 'true'))
def test_sc_enable_is_semantic_and_cannot_be_an_accidental_raw_value(enabled):
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    sc.capture(token, history=history(token))
    with pytest.raises(TypeError, match='semantic bool'):
        sc.resolve(token, direction=model.sources.snapshot(token, resolved=True),
            target=model.sources.target_snapshot(token, resolved=True), enabled=enabled)
    assert not sc.resolved


@pytest.mark.parametrize('enabled', (False, True))
def test_indirect_target_authority_comes_from_original_enable_not_only_a_matching_payload(enabled):
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    sc.capture(token, history=history(token))
    target = replace(model.sources.target_snapshot(token, resolved=True), enabled=enabled)
    assert target.prediction.provider is not None
    result = sc.resolve(token, direction=model.sources.snapshot(token, resolved=True), target=target)
    assert result.late.branch.position == joint.INDIRECT
    assert result.late.branch.target == (joint.INDIRECT_TARGET if enabled else joint.MAIN_WRONG)
    assert result.late.source == ('indirect-history' if enabled else 'main')


@pytest.mark.parametrize('valid', (False, True))
def test_nonconditional_indirect_candidate_never_gains_statistical_direction_authority(valid):
    model, event, anchor, token, _ = prepared(True)
    sc = OwnedStatisticalReference()
    # Invalid CommonHR leaves global/backward untrained. Three learned
    # families require seven negative votes, not the valid case's five.
    for number in range(5 if valid else 7):
        result = select(sc, model, token, context=history(token, valid=valid))
        if not valid and number == 5:
            condition_slot = next(slot for slot, branch in enumerate(result.branches)
                if branch is not None and branch.kind == Kind.CONDITIONAL)
            assert result.prediction.sums[condition_slot] == -25
            assert result.prediction.used[condition_slot] == 0
            assert result.late.branch.position == joint.CONDITION
        teach(sc, token, taken=False)
        token = joint.query(model, event, anchor)
    result = select(sc, model, token, context=history(token, valid=valid))
    indirect_slot = next(slot for slot, branch in enumerate(result.branches)
        if branch is not None and branch.kind == Kind.INDIRECT)
    assert result.prediction.used[indirect_slot] == 0
    assert result.late.branch.position == joint.INDIRECT
    assert result.late.branch.target == joint.INDIRECT_TARGET


def test_a_new_capture_cannot_overwrite_an_existing_original_read():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    saved = sc.capture(token, history=history(token))
    with pytest.raises(ValueError, match='captured twice'):
        sc.capture(token, history=history(token))
    assert sc.snapshot(token) is saved


def test_disabled_original_feedback_is_not_invented_when_later_sc_is_enabled():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    select(sc, model, token, enabled=False)
    resolution = Resolution(token.history, token.pc, (
        joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL),), origin=token)
    with pytest.raises(NotImplementedError, match='originally enabled'):
        sc.feedback_for(resolution)
    assert sc.model.commits == 0 and sc.model.learning is None


def test_only_real_conditional_feedback_has_statistical_learning_eligibility():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    select(sc, model, token)
    resolution = Resolution(token.history, token.pc, (
        joint.outcome(joint.INDIRECT, joint.INDIRECT_TARGET, Kind.INDIRECT),), origin=token)
    assert sc.feedback_for(resolution) is None
    assert sc.model.commits == 0


def test_the_layer_imports_existing_algorithms_not_signal_or_DUT_observers():
    import ast
    from pathlib import Path
    tree = ast.parse(Path('bpuverify/bpu/model/sc/ownership.py').read_text())
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {'dataclasses', 'bpuverify.bpu.model.direction_sources',
        'bpuverify.bpu.model.indirect_sources', 'bpuverify.bpu.model.pipeline',
        'bpuverify.bpu.model.selection', 'bpuverify.sc.model.semantic', 'bpuverify.sc.transaction.types'}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


def test_new_semantic_contract_preserves_the_unimplemented_full_integration_boundary():
    import json
    from pathlib import Path
    requirement = json.loads(Path('docs/bpu-statistical-prefix-contract.json').read_text())
    assert requirement['new_feature_IDs'] == 0
    assert not requirement['hardware_or_functional_credit_from_pure_tests']
    assert requirement['old_feature_contracts_and_verdicts_unchanged']
    assert 'CommonHR/IMLI' in requirement['implementation_boundary']
    assert not requirement['gap_basis']['all2260rows_caused_by_this_combination']
    # Historical measurement provenance is audited outside production tests;
    # ordinary collection must not depend on a retained results directory.
    assert requirement['gap_basis']['missing_integrated_short_history_rows'] > 0
    for location in requirement['source_chain']:
        filename, line = location.rsplit(':', 1)
        assert 0 < int(line) <= len(Path(filename).read_text().splitlines())


def test_recovery_repairs_invalid_feedback_payload_without_replacing_original_weight_read():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    original = replace(history(token, valid=False), global_history=255, backward=15)
    sc.capture(token, history=original)
    result = sc.resolve(token, direction=model.sources.snapshot(token, resolved=True),
        target=model.sources.target_snapshot(token, resolved=True))
    repaired = replace(original, global_history=254, backward=14)
    sc.publish(token, history=repaired)
    request = Resolution(token.history, token.pc, (
        joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL, taken=False),), origin=token)
    assert sc.feedback_for(request).history is repaired
    assert result.original.history is original
    assert result.prediction.read.context.global_history == 255
    assert result.prediction.read.context.backward == 15
    with pytest.raises(ValueError, match='already frozen'):
        sc.publish(token, history=original)


@pytest.mark.parametrize('field', ('path', 'loop', 'common_valid', 'global_history', 'backward'))
def test_publication_cannot_invent_a_different_valid_history_or_original(field):
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    original = history(token)
    sc.capture(token, history=original)
    sc.resolve(token, direction=model.sources.snapshot(token, resolved=True),
        target=model.sources.target_snapshot(token, resolved=True))
    modified = replace(original, **{field: (not original.common_valid if field == 'common_valid' else getattr(original, field) ^ 1)})
    with pytest.raises(ValueError, match='original path|invalid recovery'):
        sc.publish(token, history=modified)
    assert not sc.feedback_histories


def test_resolved_but_unpublished_source_has_no_feedback_history_authority():
    model, _, _, token, _ = prepared()
    sc = OwnedStatisticalReference()
    sc.capture(token, history=history(token))
    sc.resolve(token, direction=model.sources.snapshot(token, resolved=True),
        target=model.sources.target_snapshot(token, resolved=True))
    request = Resolution(token.history, token.pc, (
        joint.outcome(joint.CONDITION, joint.CONDITION_TARGET, Kind.CONDITIONAL),), origin=token)
    with pytest.raises(ValueError, match='published history'):
        sc.feedback_for(request)
