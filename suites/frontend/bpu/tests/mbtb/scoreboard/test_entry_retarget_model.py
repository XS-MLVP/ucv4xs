"""Independent partial-target and pending-entry reference contracts."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.mbtb.transaction.types import MbtbEntry
from bpuverify.mbtb.model.entry import expected_mbtb_entry_activity
from bpuverify.mbtb.model.entry import expected_mbtb_entry_states
from bpuverify.mbtb.model.entry import mbtb_retarget_targets
from bpuverify.mbtb.model.entry import summarize_mbtb_entry_activity


SPAN = 1 << 20
PATTERNS = (("fit_overflow", (0, 1), (0, 1)),
            ("overflow_underflow", (1, -1), (1, 2)),
            ("underflow_fit", (-1, 0), (2, 0)))


@pytest.mark.parametrize("align", (0, 1))
@pytest.mark.parametrize("bank", (0, 1))
@pytest.mark.parametrize("way", (0, 1))
@pytest.mark.parametrize("mode", ("blocked", "flow"))
@pytest.mark.parametrize("pattern,deltas,carries", PATTERNS)
def test_entry_reference_keeps_complete_target_geometry_and_writeback_order(align, bank, way, mode, pattern, deltas, carries):
    pc = 0x40001000 + (31 << 5) + (bank << 4)
    targets = mbtb_retarget_targets(pc, 0x40009000, pattern)
    assert targets == tuple((1024 + delta) * SPAN + lower
                            for delta, lower in zip(deltas, (0xA000, 0xB000), strict=True))
    expected = expected_mbtb_entry_activity(pc, 1 + align * 8, way, targets, mode)
    requests = tuple(dict(align=align, bank=bank, way=way, set_idx=31, tag=(pc >> 11) & 65535,
                         branch_type=3, ras_action=0, position=1, carry=carry, lower=lower)
                     for carry, lower in zip(carries, (0xA000, 0xB000), strict=True))
    assert expected["requests"] == requests
    assert expected["writebacks"] == (requests[1:] if mode == "blocked" else requests)
    assert expected["input_to_request_ticks"] == (4, 4)
    assert expected["request_read_state"] == ((0, int(mode == "flow")), (1, int(mode == "flow")))
    assert expected["writeback_offsets"] == ((2,) if mode == "blocked" else (6, 6))
    assert expected["lookups"] == 24 and expected["lookup_completion_ticks"] == (4,) * 24


@pytest.mark.parametrize("kwargs", (
    {"pc": -8}, {"pc": 3}, {"position": 0}, {"position": 8}, {"way": 2},
    {"mode": "queue"}, {"reads": 3}, {"reads": 4.5}, {"targets": ()},
    {"targets": (1, 1)}, {"targets": (-1, 0)}, {"targets": (0, 2 * SPAN)},
))
def test_entry_reference_rejects_out_of_scope_inputs(kwargs):
    args = dict(pc=0, position=1, way=0, targets=(1, 2), mode="blocked")
    args.update(kwargs)
    with pytest.raises(ValueError):
        expected_mbtb_entry_activity(**args)


@pytest.mark.parametrize("pc,target,pattern", (
    (0, 0, "fit_overflow"), (SPAN, 0, "fit_overflow"),
    (SPAN, 2 * SPAN - 0x1000, "fit_overflow"), (SPAN, SPAN, "unknown"),
))
def test_target_preparation_rejects_nonrepresentable_scope(pc, target, pattern):
    with pytest.raises(ValueError):
        mbtb_retarget_targets(pc, target, pattern)


def test_entry_reference_request_and_writeback_payloads_do_not_alias():
    expected = expected_mbtb_entry_activity(0, 1, 0, (1, SPAN + 2), "blocked")
    expected["requests"][1]["carry"] = 2
    assert expected["writebacks"][0]["carry"] == 1


def residents():
    return [{"entries": tuple(MbtbEntry(1, 1, 0x1000 + key * 0x100 + way, way, 3, 0)
                              for way in range(4)),
             "meta_entries": tuple(tuple({"rawHit": 1, "counter_value": 2, "position": align * 2 + way}
                                          for way in range(2)) for align in range(2))}
            for key in range(4)]


@pytest.mark.parametrize("align,way", ((0, 0), (0, 1), (1, 0), (1, 1)))
def test_entry_state_reference_changes_only_latest_full_target_and_is_frozen(align, way):
    before = residents()
    original = deepcopy(before)
    expected = expected_mbtb_entry_states(before, align, way, 0x4010A000)
    assert before == original and expected[1:] == original[1:]
    assert expected[0]["meta_entries"] == original[0]["meta_entries"]
    for index, entry in enumerate(original[0]["entries"]):
        assert expected[0]["entries"][index] == (replace(entry, target=0x4010A000)
                                                 if index == align * 2 + way else entry)
    before[3]["meta_entries"][0][0]["counter_value"] = 0
    assert expected[3]["meta_entries"][0][0]["counter_value"] == 2


@pytest.mark.parametrize("field,value", (("rawHit", 0), ("counter_value", 1), ("branch_type", 2), ("valid", 0)))
def test_entry_state_reference_requires_genuine_initial_indirect_hit(field, value):
    before = residents()
    if field in ("branch_type", "valid"):
        entries = list(before[0]["entries"])
        entries[0] = replace(entries[0], **{field: value})
        before[0]["entries"] = tuple(entries)
    else:
        before[0]["meta_entries"][0][0][field] = value
    with pytest.raises(ValueError, match="real indirect hit"):
        expected_mbtb_entry_states(before, 0, 0, 1)


def port(**updates):
    values = dict(write_valid=0, read_valid=0, read_ready=1)
    for direction in ("write", "read"):
        for key, value in dict(set_idx=31, tag=7, branch_type=3, ras_action=0,
                               position=1, carry=1, lower=0xA000).items():
            values[f"{direction}_{key}"] = value
    values.update(updates)
    return values


def frame(tick, active):
    return SimpleNamespace(event=SimpleNamespace(tick=tick),
        value={"banks": (((port(), port()), (port(), port())),
                          ((port(), port()), (port(), active)))})


def events(ticks):
    return [SimpleNamespace(event=SimpleNamespace(tick=tick)) for tick in ticks]


@pytest.mark.parametrize("mode", ("blocked", "flow"))
def test_entry_summarizer_uses_all_bank_way_handshakes_and_observed_events(mode):
    ready = int(mode == "flow")
    frames = [frame(14, port(write_valid=1, read_ready=ready)),
              frame(16, port(write_valid=1, write_carry=2, write_lower=0xB000,
                             read_valid=1, read_ready=ready))]
    if mode == "flow":
        frames.append(frame(18, port(read_valid=1, read_carry=2, read_lower=0xB000)))
    else:
        frames.append(frame(58, port(read_valid=1, read_carry=2, read_lower=0xB000)))
    lookups = [SimpleNamespace(accepted_event=SimpleNamespace(tick=tick),
                               completed_event=SimpleNamespace(tick=tick + 4)) for tick in range(10, 58, 2)]
    actual = summarize_mbtb_entry_activity(frames, events((10, 12)), lookups, mode)
    payloads = tuple(dict(align=1, bank=1, way=1, set_idx=31, tag=7, branch_type=3,
                         ras_action=0, position=1, carry=carry, lower=lower)
                     for carry, lower in ((1, 0xA000), (2, 0xB000)))
    assert actual["requests"] == payloads
    assert actual["writebacks"] == (payloads[1:] if mode == "blocked" else payloads)
    assert actual["input_to_request_ticks"] == (4, 4)
    assert actual["writeback_offsets"] == ((2,) if mode == "blocked" else (6, 6))
    assert actual["read_overlap"] and actual["lookup_cadence_ok"]
    assert actual["lookup_completion_ticks"] == (4,) * 24


def test_missing_entry_event_evidence_is_reportable_not_an_index_error():
    actual = summarize_mbtb_entry_activity([frame(14, port(write_valid=1, read_valid=1))], [], [], "blocked")
    assert actual["input_to_request_ticks"] == actual["writeback_offsets"] == (None,)
    assert not actual["read_overlap"] and not actual["lookup_cadence_ok"]


@pytest.mark.parametrize("transactions,lookups", (((), (object(),)), ((object(),), ())))
async def test_empty_checked_entry_overlap_rejects_before_drive(transactions, lookups):
    with pytest.raises(ValueError, match="feedback and prediction"):
        await MbtbAgent.train_entry_during_predictions_checked(SimpleNamespace(), transactions, lookups, None,
                                                             expected_activity={}, mode="blocked")
