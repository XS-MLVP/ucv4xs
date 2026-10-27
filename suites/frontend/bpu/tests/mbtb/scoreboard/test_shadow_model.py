"""Independent LRU selection, physical ownership and cold-feedback constraints."""
from copy import deepcopy

import pytest

from bpuverify.mbtb.model.entry import mbtb_retarget_targets
from bpuverify.mbtb.model.replacement import MbtbTwoWayLru
from bpuverify.mbtb.model.shadow import expected_mbtb_shadow_activity
from bpuverify.mbtb.model.shadow import expected_mbtb_shadow_request_ways
from bpuverify.mbtb.model.shadow import require_mbtb_shadow_cold_metadata
from bpuverify.mbtb.case.resident_scenario import resident_vectors
from bpuverify.mbtb.case.shadow_scenario import prepare


SPAN = 1 << 20
PATTERNS = (("fit_overflow", (0, 1), (0, 1)),
            ("overflow_underflow", (1, -1), (1, 2)),
            ("underflow_fit", (-1, 0), (2, 0)))


@pytest.mark.parametrize("context,set_idx", ((0, 1), (1, 31)))
@pytest.mark.parametrize("align", (0, 1))
@pytest.mark.parametrize("bank", (0, 1))
@pytest.mark.parametrize("owner", (0, 1))
@pytest.mark.parametrize("phase", ("clean_first", "pending_second"))
@pytest.mark.parametrize("mode", ("blocked", "flow"))
@pytest.mark.parametrize("pattern,deltas,carries", PATTERNS)
def test_shadow_reference_separates_request_victim_from_retained_owner(
        context, set_idx, align, bank, owner, phase, mode, pattern, deltas, carries):
    pc = 0x40001000 + (set_idx << 5) + (bank << 4)
    targets = mbtb_retarget_targets(pc, 0x40009000, pattern)
    assert targets == tuple((1024 + delta) * SPAN + lower
                            for delta, lower in zip(deltas, (0xA000, 0xB000), strict=True))
    request_ways = (1 - owner, owner) if phase == "clean_first" else (owner, 1 - owner)
    payloads = tuple(dict(align=align, bank=bank, way=request_ways[index], set_idx=set_idx, tag=2,
                         branch_type=3, ras_action=0, position=1, carry=carries[index], lower=lower)
                     for index, lower in enumerate((0xA000, 0xB000)))
    writebacks = tuple(dict(payloads[index], way=owner)
                       for index in ((1,) if mode == "blocked" else (0, 1)))
    ready = int(mode == "flow")
    wanted = dict(requests=payloads, writebacks=writebacks, input_to_request_ticks=(4, 4),
                  request_read_state=((0, ready), (int(phase == "clean_first"), ready)),
                  writeback_offsets=(2,) if mode == "blocked" else (6, 6), read_overlap=True,
                  lookups=24, lookup_cadence_ok=True, lookup_completion_ticks=(4,) * 24)
    assert expected_mbtb_shadow_request_ways(owner, phase) == request_ways
    assert expected_mbtb_shadow_activity(pc, 1 + align * 8, owner, targets, mode, phase) == wanted


@pytest.mark.parametrize("initial", (0, 1))
@pytest.mark.parametrize("touch", (0, 1))
def test_lru_touch_and_consecutive_allocations_are_an_independent_state_machine(initial, touch):
    model = MbtbTwoWayLru(initial)
    model.touch(touch)
    assert model.victim == 1 - touch
    assert tuple(model.allocate() for _ in range(4)) == (1 - touch, touch, 1 - touch, touch)
    assert model.victim == 1 - touch


def test_lru_reset_victim_is_way_one():
    assert MbtbTwoWayLru().victim == 1


@pytest.mark.parametrize("way", (-1, 2, "0", None, 0.5))
def test_lru_rejects_unknown_physical_way_without_changing_state(way):
    with pytest.raises(ValueError, match="way 0/1"):
        MbtbTwoWayLru(way)
    model = MbtbTwoWayLru()
    with pytest.raises(ValueError, match="way 0/1"):
        model.touch(way)
    assert model.victim == 1


@pytest.mark.parametrize("kwargs", (
    {"owner": -1}, {"owner": 2}, {"phase": "global_pending"},
    {"pc": -16}, {"pc": 8}, {"pc": 16.0}, {"position": 0}, {"position": 8},
    {"targets": ()}, {"targets": (1,)}, {"targets": (1, 1)}, {"targets": (1.5, 2)},
    {"targets": (-1, 2)}, {"targets": (1, 2 * SPAN)}, {"mode": "queue"},
    {"reads": 3}, {"reads": 4.5},
))
def test_shadow_activity_rejects_unsupported_geometry_or_scope(kwargs):
    args = dict(pc=0, position=1, owner=0, targets=(1, 2), mode="blocked", phase="clean_first")
    args.update(kwargs)
    with pytest.raises(ValueError):
        expected_mbtb_shadow_activity(**args)


def test_cross_way_request_edits_do_not_alias_the_original_owner_writebacks():
    expected = expected_mbtb_shadow_activity(0, 1, 0, (1, 2), "flow", "clean_first")
    assert [payload["way"] for payload in expected["requests"]] == [1, 0]
    assert [payload["way"] for payload in expected["writebacks"]] == [0, 0]
    expected["requests"][0]["lower"] = 3
    expected["requests"][1]["way"] = 1
    assert [payload["lower"] for payload in expected["writebacks"]] == [1, 2]
    assert [payload["way"] for payload in expected["writebacks"]] == [0, 0]


def cold_metadata():
    return tuple(tuple({"rawHit": 0, "counter_value": 2} for _ in range(2)) for _ in range(2))


def test_cold_metadata_validation_does_not_modify_or_invent_counter_state():
    cold = cold_metadata()
    before = deepcopy(cold)
    require_mbtb_shadow_cold_metadata(cold)
    assert cold == before


@pytest.mark.parametrize("align,way", ((0, 0), (0, 1), (1, 0), (1, 1)))
def test_cold_metadata_validation_rejects_any_initial_hit(align, way):
    cold = cold_metadata()
    cold[align][way]["rawHit"] = 1
    with pytest.raises(ValueError, match="all-miss"):
        require_mbtb_shadow_cold_metadata(cold)


@pytest.mark.parametrize("metadata", (None, {}, (), ((), ()), (({}, {}), ({}, {})),
                                     ((0, 0), (0, 0)), (({"rawHit": 0},), ({"rawHit": 0},))))
def test_cold_metadata_validation_rejects_missing_or_ambiguous_shape(metadata):
    with pytest.raises(ValueError, match="cold metadata"):
        require_mbtb_shadow_cold_metadata(metadata)


@pytest.mark.parametrize("context", (0, 1))
@pytest.mark.parametrize("align", (0, 1))
@pytest.mark.parametrize("bank", (0, 1))
@pytest.mark.parametrize("stride", (0, 1))
def test_shared_resident_vectors_preserve_index_geometry_and_optional_distinct_tags(context, align, bank, stride):
    vectors = resident_vectors(context, align, bank, target_type=3, tag_stride=stride)
    sets = (1, 2, 3) if context == 0 else (31, 32, 33)
    assert tuple((vector.pc >> 5) & 63 for vector in vectors) == (*sets, sets[-1])
    assert tuple((vector.pc >> 4) & 1 for vector in vectors) == (bank, bank, bank, 1 - bank)
    assert tuple((vector.pc >> 11) & 65535 for vector in vectors) == tuple(2 + index * stride for index in range(4))
    assert all(vector.position == 1 + align * 8 and vector.branch_type == 3 for vector in vectors)


@pytest.mark.parametrize("owner,phase", ((-1, "clean_first"), (2, "pending_second"), (0, "unknown")))
async def test_shadow_preparation_rejects_bad_scope_before_any_dut_operation(owner, phase):
    with pytest.raises(ValueError):
        await prepare(None, 0, 0, 0, owner, phase)
