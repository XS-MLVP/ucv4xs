"""Independent two-key identity, carry, retention and frozen-state checks."""
from copy import deepcopy
from dataclasses import replace

import pytest

from suites.frontend.bpu.mbtb.transaction.types import MbtbEntry
from suites.frontend.bpu.mbtb.model.entry_keys import entry_key_coordinate
from suites.frontend.bpu.mbtb.model.entry_keys import entry_key_tag
from suites.frontend.bpu.mbtb.model.entry_keys import expected_mbtb_entry_keys_activity
from suites.frontend.bpu.mbtb.model.entry_keys import expected_mbtb_entry_keys_states
from suites.frontend.bpu.mbtb.model.entry_keys import mbtb_entry_key_targets
from suites.frontend.bpu.mbtb.case.entry_keys_scenario import check_case
from suites.frontend.bpu.mbtb.case.resident_scenario import prepare


SPAN = 1 << 20
PAIRS = (("fit_overflow", (0, 1), (0, 1)),
         ("overflow_underflow", (1, -1), (1, 2)),
         ("underflow_fit", (-1, 0), (2, 0)))


@pytest.mark.parametrize("align", (0, 1))
@pytest.mark.parametrize("bank", range(4))
@pytest.mark.parametrize("way", range(4))
@pytest.mark.parametrize("mode", ("blocked", "flow"))
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("pair,deltas,carries", PAIRS)
def test_two_key_reference_keeps_target_identity_and_order(align, bank, way, mode, reverse, pair, deltas, carries):
    # Two real keys in the same internal bank but distinct 256-set rows.
    pcs = (0x40010000 + (31 << 8) + (bank << 5) + (align << 4),
           0x40010000 + (32 << 8) + (bank << 5) + (align << 4))
    targets = mbtb_entry_key_targets(pcs, (0x40009000, 0x40009100), pair)
    assert targets == tuple((1024 + delta) * SPAN + lower
                            for delta, lower in zip(deltas, (0xA000, 0xB100), strict=True))
    indices = (1, 0) if reverse else (0, 1)
    expected = expected_mbtb_entry_keys_activity(tuple(pcs[i] for i in indices), 1 + align * 16, way,
                                               tuple(targets[i] for i in indices), mode)
    payloads = tuple(dict(align=align, bank=bank, way=way, set_idx=entry_key_coordinate(pcs[i])[2],
                          tag=entry_key_tag(pcs[i]),
                         branch_type=3, ras_action=0, position=1, carry=carries[i], lower=(0xA000, 0xB100)[i])
                     for i in indices)
    assert expected["requests"] == expected["writebacks"] == payloads
    assert expected["input_to_request_ticks"] == (4, 4)
    assert expected["request_read_state"] == ((0, int(mode == "flow")), (1, int(mode == "flow")))
    assert expected["writeback_offsets"] == ((2, 4) if mode == "blocked" else (6, 6))
    assert expected["lookups"] == 24 and expected["lookup_completion_ticks"] == (4,) * 24


@pytest.mark.parametrize("kwargs", (
    {"pcs": ()}, {"pcs": (0,)}, {"pcs": (-16, 32)}, {"pcs": (8, 32)},
    {"pcs": (0.0, 32)}, {"pcs": (0, 16)}, {"pcs": (0, 0)}, {"pcs": (0, 0x8000)},
    {"position": 0}, {"position": 8}, {"way": 4}, {"mode": "queue"}, {"reads": 3},
    {"reads": 4.5}, {"targets": ()}, {"targets": (1,)}, {"targets": (1.5, 2)},
    {"targets": (-1, 2)}, {"targets": (0, 2 * SPAN)},
))
def test_two_key_activity_reference_rejects_out_of_scope_inputs(kwargs):
    args = dict(pcs=(0, 0x100), position=1, way=0, targets=(1, 2), mode="blocked")
    args.update(kwargs)
    with pytest.raises(ValueError):
        expected_mbtb_entry_keys_activity(**args)


def test_two_distinct_keys_may_store_the_same_target_but_still_need_two_writebacks():
    expected = expected_mbtb_entry_keys_activity((0, 0x80), 1, 0, (1, 1), "blocked")
    assert len(expected["writebacks"]) == 2
    assert expected["writebacks"][0]["set_idx"] == 0 and expected["writebacks"][1]["set_idx"] == 1


def test_two_key_request_and_writeback_payloads_do_not_alias():
    expected = expected_mbtb_entry_keys_activity((0, 0x80), 1, 0, (1, SPAN + 2), "blocked")
    expected["requests"][1]["carry"] = 2
    assert expected["writebacks"][1]["carry"] == 1
    assert expected["writebacks"][0]["carry"] == 0


@pytest.mark.parametrize("pcs,original,pair", (
    ((), (), "fit_overflow"), ((SPAN,), (SPAN, SPAN), "fit_overflow"),
    ((SPAN, SPAN), (SPAN,), "fit_overflow"), ((SPAN, SPAN), (SPAN, SPAN), "unknown"),
    ((SPAN, SPAN + 32), (SPAN, 0), "fit_overflow"),
    ((float(SPAN), SPAN), (SPAN, SPAN), "fit_overflow"),
))
def test_two_key_target_preparation_rejects_unsupported_scope(pcs, original, pair):
    with pytest.raises(ValueError):
        mbtb_entry_key_targets(pcs, original, pair)


def residents():
    return [{"entries": tuple(MbtbEntry(1, 1, 0x1000 + key * 0x100 + index, index, 3, 0)
                              for index in range(10)),
             "meta_entries": tuple(tuple({"rawHit": 1, "counter_value": 2, "position": align * 5 + way}
                                          for way in range(5)) for align in range(2))}
            for key in range(4)]


@pytest.mark.parametrize("align,way", tuple((a,w) for a in (0,1) for w in range(4)))
def test_two_key_state_reference_updates_each_target_and_preserves_every_neighbor(align, way):
    before = residents()
    original = deepcopy(before)
    targets = (0x4010A000, 0x3FF0B100)
    expected = expected_mbtb_entry_keys_states(before, align, way, targets)
    assert before == original and expected[2:] == original[2:]
    for key in (0, 1):
        assert expected[key]["meta_entries"] == original[key]["meta_entries"]
        for index, entry in enumerate(original[key]["entries"]):
            assert expected[key]["entries"][index] == (replace(entry, target=targets[key])
                                                        if index == align * 5 + way else entry)
    before[1]["meta_entries"][align][way]["counter_value"] = 0
    before[3]["meta_entries"][0][0]["counter_value"] = 0
    assert expected[1]["meta_entries"][align][way]["counter_value"] == 2
    assert expected[3]["meta_entries"][0][0]["counter_value"] == 2


@pytest.mark.parametrize("key", (0, 1))
@pytest.mark.parametrize("field,value", (("rawHit", 0), ("counter_value", 1), ("branch_type", 2), ("valid", 0)))
def test_two_key_state_reference_requires_both_genuine_hits(key, field, value):
    before = residents()
    if field in ("branch_type", "valid"):
        entries = list(before[key]["entries"])
        entries[0] = replace(entries[0], **{field: value})
        before[key]["entries"] = tuple(entries)
    else:
        before[key]["meta_entries"][0][0][field] = value
    with pytest.raises(ValueError, match="two real indirect hits"):
        expected_mbtb_entry_keys_states(before, 0, 0, (1, 2))


@pytest.mark.parametrize("kwargs", ({"align": 2}, {"way": -1}, {"targets": (1,)},
                                     {"targets": (-1, 2)}, {"targets": (1.5, 2)}, {"prepared": ()}))
def test_two_key_state_reference_rejects_bad_geometry_or_targets(kwargs):
    args = dict(prepared=residents(), align=0, way=0, targets=(1, 2))
    args.update(kwargs)
    with pytest.raises(ValueError):
        expected_mbtb_entry_keys_states(**args)


@pytest.mark.parametrize("stride", (-1, "one", 0.5))
async def test_resident_prepare_rejects_bad_stride_before_any_dut_operation(stride):
    with pytest.raises(ValueError, match="tag stride"):
        await prepare(None, 0, 0, 0, 0, tag_stride=stride)


async def test_two_key_scenario_rejects_unknown_order_before_any_dut_operation():
    with pytest.raises(ValueError, match="order"):
        await check_case(None, None, 0, 0, 0, 0, "blocked", "unknown", "fit_overflow")
