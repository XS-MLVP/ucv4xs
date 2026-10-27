"""Hand-derived index, qualification and full-state replacement oracles."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.mbtb.transaction.types import MbtbEntry
from bpuverify.mbtb.model.replacement import MbtbReplacementGeometry
from bpuverify.mbtb.model.replacement import MbtbReplacementState
from bpuverify.mbtb.model.replacement import MbtbFourWayLru
from bpuverify.mbtb.model.replacement import expected_mbtb_replacement_feedback
from bpuverify.mbtb.model.replacement import expected_mbtb_replacement_state
from bpuverify.mbtb.model.replacement import mbtb_replacement_geometry
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.replacement_scenario import replacement_vectors


@pytest.mark.parametrize('index', range(256))
def test_geometry_covers_all_indices_and_both_sram_set_halves(index):
    for align in range(2):
        for upper in range(2):
            vectors = replacement_vectors(index, align, upper)
            wanted = ((align, index % 4, index // 4 + 64 * upper, index),
                      (align, index % 4, index // 4 + 64 * (1 - upper), index),
                      (align, index % 4, (index // 4 ^ 1) + 64 * upper, index ^ 4),
                      (1 - align, index % 4, index // 4 + 64 * upper, index))
            assert tuple(mbtb_replacement_geometry(vector.pc, vector.position) for vector in vectors) == tuple(
                MbtbReplacementGeometry(*geometry) for geometry in wanted)
            assert vectors[0].pc == vectors[3].pc
            assert vectors[0].pc ^ vectors[1].pc == 8192


@pytest.mark.parametrize('align', (0, 1))
@pytest.mark.parametrize('upper', (0, 1))
@pytest.mark.parametrize('mode,ways', (
    ('taken_way0', (3, 2, 3, 3)), ('taken_way1', (3, 2, 3, 3)),
    ('not_taken', (1, 3, 3, 3)), ('lookup_only', (1, 3, 3, 3)),
))
def test_hand_derived_allocation_sequence_shares_only_alias_lru(align, upper, mode, ways):
    vectors = replacement_vectors(31, align, upper)
    model = MbtbReplacementState()
    for vector in vectors:
        assert tuple(model.allocate(vector.pc, vector.position + i) for i in range(4)) == (3, 2, 1, 0)
    alias = vectors[1]
    selected = 0 if mode == 'taken_way0' else 1
    for peer in reversed(tuple(way for way in range(4) if way != selected)):
        model.feedback(alias.pc, alias.position, peer, taken=1)
    if mode != 'lookup_only':
        model.feedback(alias.pc, alias.position, selected, taken=int(mode != 'not_taken'))
    assert tuple(model.allocate(vector.pc, vector.position + 2) for vector in vectors) == ways
    assert model.victim(vectors[0].pc, vectors[0].position) == model.victim(alias.pc, alias.position)
    # A new model represents reset; there is no global mutable policy state.
    assert MbtbReplacementState().victim(alias.pc, alias.position) == 3


@pytest.mark.parametrize('pc,position', ((-16, 1), (8, 1), (16.0, 1), ('16', 1),
                                      (0, -1), (0, 32), (0, 1.5), (0, None)))
def test_reference_rejects_unsupported_geometry(pc, position):
    model = MbtbReplacementState()
    with pytest.raises(ValueError):
        model.allocate(pc, position)
    assert model._cells == {}


@pytest.mark.parametrize('way,taken', ((-1, 1), (4, 1), (None, 1), (0, -1), (1, 2), (0, '1')))
def test_bad_feedback_does_not_create_or_change_a_cell(way, taken):
    model = MbtbReplacementState()
    with pytest.raises(ValueError):
        model.feedback(0, 1, way, taken=taken)
    assert model._cells == {}


def prepared():
    return dict(entries=tuple(MbtbEntry(int(slot % 5 < 4), 1, 0x40009000 + slot * 0x100,
                              1 + slot % 5 + 16 * (slot // 5), 1, 0) for slot in range(10)),
                meta_entries=tuple(tuple(dict(rawHit=int(way < 4), counter_value=2, position=1 + way + 16 * align,
                                              attribute=dict(branchType=1, rasAction=0))
                                         for way in range(5)) for align in range(2)))


def victim_snapshot(wanted, before, align, way):
    active, victim = align * 5 + way, align * 5 + 4
    values = list(wanted['entries'])
    values[victim] = replace(before['entries'][active], taken=1)
    wanted['entries'] = tuple(values)
    wanted['meta_entries'][align][4].update(deepcopy(before['meta_entries'][align][way]), counter_value=2)


@pytest.mark.parametrize('align', (0, 1))
@pytest.mark.parametrize('way', range(4))
def test_full_state_update_changes_only_independently_selected_victim(align, way):
    state = prepared()
    before = deepcopy(state)
    newcomer = BranchVector(0, 0x4000C000, 5 + 16 * align, 1)
    expected = expected_mbtb_replacement_state(state, align, way, newcomer)
    wanted = deepcopy(before)
    active = 5 * align + way
    wanted['entries'] = tuple(replace(entry, target=newcomer.target, position=newcomer.position)
                              if slot == active else entry for slot, entry in enumerate(before['entries']))
    wanted['meta_entries'][align][way]['position'] = newcomer.position
    victim_snapshot(wanted, before, align, way)
    assert expected == wanted and state == before
    expected['meta_entries'][align][way]['counter_value'] = 3
    assert state == before


@pytest.mark.parametrize('kwargs', ({'align': 2}, {'way': -1},
                                  {'newcomer': BranchVector(0, 1, 17, 1)},
                                  {'newcomer': BranchVector(0, 1, 1, 3)},
                                  {'newcomer': BranchVector(0, -1, 1, 1)}))
def test_full_state_update_rejects_unsupported_scope(kwargs):
    args = dict(prepared=prepared(), align=0, way=0, newcomer=BranchVector(0, 1, 1, 1))
    args.update(kwargs)
    with pytest.raises(ValueError):
        expected_mbtb_replacement_state(**args)


def test_shadow_and_replacement_use_the_same_policy_class():
    from bpuverify.mbtb.model.replacement import MbtbFourWayLru as shadow_lru
    assert shadow_lru is MbtbFourWayLru


@pytest.mark.parametrize('align', (0, 1))
@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('taken,counter', ((0, 1), (1, 3)))
def test_qualification_and_replacement_preserve_or_reset_real_conditional_counters(align, way, taken, counter):
    state = prepared()
    before = deepcopy(state)
    qualified = expected_mbtb_replacement_feedback(state, align, way, taken=taken)
    wanted = deepcopy(before)
    active = 5 * align + way
    wanted['entries'] = tuple(replace(entry, taken=taken) if i == active else entry
                              for i, entry in enumerate(wanted['entries']))
    wanted['meta_entries'][align][way]['counter_value'] = counter
    assert qualified == wanted and state == before
    newcomer = BranchVector(0, 0x4000C000, 5 + 16 * align, 1)
    replaced = expected_mbtb_replacement_state(qualified, align, way, newcomer)
    wanted['entries'] = tuple(replace(entry, target=newcomer.target, position=newcomer.position, taken=1)
                              if i == active else entry for i, entry in enumerate(wanted['entries']))
    wanted['meta_entries'][align][way].update(position=newcomer.position, counter_value=2)
    victim_snapshot(wanted, qualified, align, way)
    assert replaced == wanted and qualified['meta_entries'][align][way]['counter_value'] == counter
