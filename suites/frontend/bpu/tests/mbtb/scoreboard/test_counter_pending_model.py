"""Independent feedback semantics and the bounded counter-retention reference."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.transaction.types import MbtbEntry
from bpuverify.mbtb.model.counter import expected_mbtb_counter_activity
from bpuverify.mbtb.model.counter import expected_mbtb_counter_states
from bpuverify.mbtb.model.counter import summarize_mbtb_counter_activity
from bpuverify.mbtb.driver.feedback import expected_mbtb_feedback
from bpuverify.mbtb.driver.feedback import observed_mbtb_feedback


@pytest.mark.parametrize("align", (0, 1))
@pytest.mark.parametrize("bank", range(4))
@pytest.mark.parametrize("way", range(4))
@pytest.mark.parametrize("taken", (0, 1))
def test_counter_reference_keeps_bank_set_way_and_flow_control(align, bank, way, taken):
    blocked = expected_mbtb_counter_activity(align, bank, way, taken, "blocked", sets=(31, 32))
    flow = expected_mbtb_counter_activity(align, bank, way, taken, "flow", sets=(31, 32))
    expected = tuple({"align": align, "bank": bank, "set_idx": index, "way_mask": 1 << way,
                      "counters": tuple((3 if taken else 1) if i == way else None for i in range(4))}
                     for index in (31, 32))
    assert blocked["requests"] == flow["requests"] == expected
    assert blocked["writebacks"] == flow["writebacks"] == expected
    assert blocked["input_to_request_ticks"] == flow["input_to_request_ticks"] == (2, 2)
    assert blocked["buffered_enqueues"] == ((align, bank),) * 2
    assert flow["buffered_enqueues"] == ()
    assert blocked["peak_occupancy"] == 2 and flow["peak_occupancy"] == 0
    assert blocked["writeback_offsets"] == (2, 4) and flow["writeback_offsets"] == (2, 2)
    assert blocked["request_blocked"] == (1, 1) and flow["request_blocked"] == (0, 0)


@pytest.mark.parametrize("kwargs", (
    {"align": 2}, {"bank": -1}, {"way": 4}, {"taken": 2}, {"mode": "queue"},
    {"sets": (31, 31)}, {"sets": (0, 256)}, {"sets": (1,)},
    {"reads": 3}, {"reads": 4.5},
))
def test_counter_reference_rejects_out_of_scope_inputs(kwargs):
    args = dict(align=0, bank=0, way=0, taken=0, mode="blocked")
    args.update(kwargs)
    with pytest.raises(ValueError):
        expected_mbtb_counter_activity(**args)


def test_counter_request_expectations_are_not_shared_with_writebacks():
    expected = expected_mbtb_counter_activity(0, 0, 0, 0, "blocked")
    expected["requests"][0]["set_idx"] = 63
    assert expected["writebacks"][0]["set_idx"] == 1
    assert expected["requests"][1]["set_idx"] == 2


def prepared_states():
    return [{"entries": tuple(MbtbEntry(1, 1, 0x1000 + key * 0x100 + way, way, 1, 0)
                              for way in range(10)),
             "meta_entries": tuple(tuple({"rawHit": 1, "counter_value": 2, "position": align * 5 + way}
                                          for way in range(5)) for align in range(2))}
            for key in range(4)]


@pytest.mark.parametrize("align,way,taken", ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0)))
def test_counter_state_reference_changes_only_selected_targets_and_is_frozen(align, way, taken):
    before = prepared_states()
    original = deepcopy(before)
    expected = expected_mbtb_counter_states(before, align, way, taken)
    assert before == original and expected[2:] == original[2:]
    for key in (0, 1):
        for index, entry in enumerate(original[key]["entries"]):
            assert expected[key]["entries"][index] == (replace(entry, taken=taken)
                                                       if index == align * 5 + way else entry)
        assert expected[key]["meta_entries"][align][way]["counter_value"] == (3 if taken else 1)
        assert expected[key]["meta_entries"][align][1 - way] == original[key]["meta_entries"][align][1 - way]
    before[2]["meta_entries"][0][0]["counter_value"] = 0
    assert expected[2]["meta_entries"][0][0]["counter_value"] == 2


@pytest.mark.parametrize("field,value", (("rawHit", 0), ("counter_value", 1)))
def test_counter_state_reference_requires_a_real_initial_hit(field, value):
    before = prepared_states()
    before[0]["meta_entries"][0][0][field] = value
    with pytest.raises(ValueError, match="real conditional hit"):
        expected_mbtb_counter_states(before, 0, 0, 0)


def feedback():
    return MbtbBatchTraining(0x40001003, prepared_states()[0]["meta_entries"], (
        MbtbBranchFeedback(0x40009000, 0, 1, 1, ras_action=0, mispredict=1), None,
        MbtbBranchFeedback(0x40009400, 0, 2, 3, ras_action=2, mispredict=0),
    ))


def test_feedback_reference_preserves_sparse_slots_and_freezes_metadata():
    transaction = feedback()
    expected = expected_mbtb_feedback(transaction)
    assert expected["pc"] == 0x40001003 and expected["next_pc"] == 0x40001010
    assert expected["ready"] == 1 and len(expected["resolved"]) == 8
    assert expected["resolved"][0] == {"target": 0x40009000, "taken": 0, "position": 1,
                                       "branch_type": 1, "ras_action": 0, "mispredict": 1}
    assert expected["resolved"][1] is None and expected["resolved"][2]["ras_action"] == 2
    assert expected["resolved"][3:] == (None,) * 5
    transaction.meta_entries[0][0]["counter_value"] = 0
    assert expected["meta_entries"][0][0]["counter_value"] == 2


def test_feedback_observer_ignores_payload_of_invalid_slots_only():
    transaction = feedback()
    expected = expected_mbtb_feedback(transaction)
    sample = {"ready": 1, "bits": {"start_pc0": expected["pc"], "start_pc1": expected["next_pc"],
              "meta_entries": transaction.meta_entries,
              "branches": tuple({"valid": 0, "target": 99} if branch is None else {"valid": 1, **branch}
                                 for branch in expected["resolved"])}}
    assert observed_mbtb_feedback(sample) == expected
    sample["bits"]["branches"][0]["target"] ^= 1
    assert observed_mbtb_feedback(sample) != expected


@pytest.mark.parametrize("branches", ((), (MbtbBranchFeedback(1, 1, 0, 1, mispredict=1),) * 2))
def test_feedback_reference_rejects_empty_or_multiple_mispredictions(branches):
    with pytest.raises(ValueError):
        expected_mbtb_feedback(replace(feedback(), branches=branches))


def queue(**updates):
    values = dict(enq_valid=0, enq_ready=1, deq_valid=0, deq_ready=1, enq_set=0, enq_way=0,
                  deq_set=0, deq_way=0, enq_ptr=0, deq_ptr=0, empty=1, maybe_full=0, do_enq=0,
                  enq_counters=(0, 0), deq_counters=(0, 0))
    values.update(updates)
    return values


def frame(tick, active):
    return SimpleNamespace(event=SimpleNamespace(tick=tick), value={"queues": ((active, queue()),
                                                                                            (queue(), queue()))})


def test_counter_summarizer_uses_observed_handshakes_and_masks_unused_way():
    frames = [frame(12, queue(enq_valid=1, enq_set=31, enq_way=2, enq_counters=(999, 3),
                             deq_valid=1, deq_set=31, deq_way=2, deq_counters=(888, 3)))]
    observed = summarize_mbtb_counter_activity(frames, [SimpleNamespace(event=SimpleNamespace(tick=10))],
        [SimpleNamespace(accepted_event=SimpleNamespace(tick=10), completed_event=SimpleNamespace(tick=14))], "flow")
    expected = ({"align": 0, "bank": 0, "set_idx": 31, "way_mask": 2, "counters": (None, 3)},)
    assert observed["requests"] == observed["writebacks"] == expected
    assert observed["input_to_request_ticks"] == observed["writeback_offsets"] == (2,)
    assert observed["peak_occupancy"] == 0 and observed["lookup_completion_ticks"] == (4,)
    frames[0].value["queues"][0][0]["deq_ready"] = 0
    assert summarize_mbtb_counter_activity(frames, [], [], "blocked")["writebacks"] == ()


def test_missing_input_or_lookup_evidence_is_reportable_not_an_index_error():
    actual = summarize_mbtb_counter_activity([frame(12, queue(enq_valid=1, deq_valid=1,
        do_enq=1, empty=0, maybe_full=1))], [], [], "blocked")
    assert actual["input_to_request_ticks"] == actual["writeback_offsets"] == (None,)
    assert actual["peak_occupancy"] == 4 and actual["buffered_enqueues"] == ((0, 0),)
    assert actual["read_overlap"] is False


@pytest.mark.parametrize("transactions,lookups", (((), (object(),)), ((object(),), ())))
async def test_empty_checked_counter_overlap_rejects_before_drive(transactions, lookups):
    with pytest.raises(ValueError, match="feedback and prediction"):
        await MbtbAgent.train_during_predictions_checked(SimpleNamespace(), transactions, lookups, None,
                                                       expected_activity={}, mode="blocked")
