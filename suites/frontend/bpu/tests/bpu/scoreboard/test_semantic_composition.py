"""Independent BPU composition contracts, without signals/register seeds."""
from dataclasses import replace

import pytest

from bpuverify.bpu.model.path_history import PathHistoryReference, path_contribution
from bpuverify.bpu.model.selection import Branch, Choice, Kind, StackAction, early, middle, final, middle_repair, final_repair, fallthrough
from bpuverify.common.model.folded_history import folded_history_values, PHR_FOLD_LAYOUT


PC = 0x40000800


def test_path_history_uses_owned_full_words_and_restores_an_immutable_checkpoint():
    model = PathHistoryReference()
    initial = model.checkpoint()
    current = model.advance(taken=True, cfi_pc=PC + 4, target=PC + 0x260)
    saved = model.checkpoint()
    for target in (PC + 0x342, PC + 0x420):
        current = model.advance(taken=True, cfi_pc=PC + 7, target=target)
    assert saved.history != current.history
    recovered = model.advance(taken=False, cfi_pc=PC + 2, target=PC + 16, restore=saved)
    assert recovered.history == saved.history and initial.history == 0
    assert recovered.metadata() == saved.metadata()
    assert saved.folds() == tuple(row['foldedHist'] for row in folded_history_values(
        saved.history % (1 << 31), len(PHR_FOLD_LAYOUT)))


@pytest.mark.parametrize('fault', ('foreign', 'copied', 'reset'))
def test_external_metadata_cannot_inject_a_golden_history(fault):
    model = PathHistoryReference()
    source = model.checkpoint()
    if fault == 'foreign':
        source = PathHistoryReference().checkpoint()
    elif fault == 'copied':
        source = replace(source, history=0x12345)
    else:
        model.reset()
    with pytest.raises(ValueError, match='owned'):
        model.advance(taken=False, cfi_pc=PC, target=PC, restore=source)
    assert model.history == 0


def test_taken_path_word_keeps_high_hash_bits_and_two_circular_wraps():
    model = PathHistoryReference()
    expected = 0
    for count in range(1, 54):
        expected = ((expected << 2) ^ path_contribution(PC + 7, PC + 0x6000)) & ((1 << 52) - 1)
        source = model.advance(taken=True, cfi_pc=PC + 7, target=PC + 0x6000)
        assert source.history == expected
        assert source.metadata()['phrPtr']['value'] % 2 == 0
        if count in (26, 52):
            assert source.metadata()['phrPtr'] == dict(value=0, flag=int(count == 26))


def test_retired_checkpoint_cannot_be_used_as_a_recovery_source():
    model = PathHistoryReference()
    source = model.checkpoint()
    model.retire(source)
    with pytest.raises(ValueError, match='owned'):
        model.advance(taken=False, cfi_pc=PC, target=PC, restore=source)


@pytest.mark.parametrize('offset', (0, 1, 7, 8, 2032, 2040, 2047))
def test_fallthrough_alignment_and_page_boundary_are_independent_of_a_port(offset):
    pc = PC + offset
    value = fallthrough(pc).branch
    assert value.target == min((pc // 8) * 8 + 16, (pc // 2048 + 1) * 2048)
    assert (pc // 8) * 8 + value.position + 1 == value.target


def test_any_ahead_hit_suppresses_micro_even_when_all_ahead_branches_are_not_taken():
    micro = Branch(1, PC + 0x100, Kind.DIRECT)
    conditional = Branch(3, PC + 0x200, Kind.CONDITIONAL, False)
    assert early(PC, micro=micro, ahead=(conditional,), short_history=(None,)) == fallthrough(PC)
    assert early(PC, micro=micro).branch == micro


def test_branch_order_not_way_order_and_jump_ignores_direction_override():
    entries = (Branch(9, PC + 0x100, Kind.CONDITIONAL), Branch(3, PC + 0x200, Kind.DIRECT, False))
    chosen = middle(PC, entries, (True, False))
    assert chosen.owner == 1 and chosen.branch.position == 3 and chosen.branch.taken
    late = final(PC, entries, (True, None), (False, None))
    assert late.owner == 1 and late.branch == chosen.branch


def test_s2_raw_provider_and_s3_qualified_correction_are_not_interchangeable():
    entry = Branch(4, PC + 0x100, Kind.CONDITIONAL, False)
    assert middle(PC, (entry,), (True,)).branch.taken
    assert not final(PC, (entry,), (None,), (None,)).branch.taken


def test_statistical_correction_has_priority_and_changes_selected_branch():
    entries = (Branch(2, PC + 0x100, Kind.CONDITIONAL), Branch(7, PC + 0x200, Kind.CONDITIONAL))
    s2 = middle(PC, entries, (True, True))
    s3 = final(PC, entries, (True, True), (False, None))
    assert (s2.owner, s3.owner) == (0, 1)
    assert final_repair(fallthrough(PC), s2, s3, corrected_middle=True)


@pytest.mark.parametrize('action,source,target', ((StackAction.RETURN, 'return-stack', PC + 0x400),
    (StackAction.RETURN_AND_CALL, 'main', PC + 0x100), (StackAction.CALL, 'indirect-history', PC + 0x300),
    (StackAction.NONE, 'indirect-history', PC + 0x300)))
def test_return_and_indirect_target_qualification(action, source, target):
    entry = Branch(4, PC + 0x100, Kind.INDIRECT, action=action)
    chosen = final(PC, (entry,), (None,), (None,), indirect_target=PC + 0x300, return_address=PC + 0x400)
    assert (chosen.source, chosen.branch.target) == (source, target)


def test_target_only_difference_is_late_and_mbtb_comparison_is_not_repeated_after_s2_repair():
    initial = Choice(Branch(4, PC + 0x100, Kind.DIRECT), 0, 'ahead')
    changed = Choice(replace(initial.branch, target=PC + 0x200), 0, 'main')
    assert not middle_repair(initial, changed)
    assert final_repair(initial, changed, changed, corrected_middle=False)
    assert not final_repair(initial, changed, changed, corrected_middle=True)
    returned = replace(changed, source='return-stack', branch=replace(changed.branch, target=PC + 0x300))
    assert final_repair(initial, changed, returned, corrected_middle=True)
