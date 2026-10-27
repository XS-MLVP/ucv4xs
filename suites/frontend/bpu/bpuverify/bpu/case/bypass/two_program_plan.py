"""Two genuine trained programs; old physical bank is selected by real PHR folds."""
from bpuverify.bpu.model.phr.model import fold
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.case.bypass import history_plan as _v15
read_indices, full_tags, recurring_history = _v15.read_indices, _v15.full_tags, _v15.recurring_history


def program(pc, position):
    fallback = position + 4
    histories = [recurring_history(pc, pos) for pos in (position, fallback)]
    indices = [read_indices(pc, (fold(h, 6, 6), fold(h, 12, 9))) for h in histories]
    return dict(pc=pc, position=position, fallback=fallback,
        conditional_history=histories[0], fallback_history=histories[1],
        expected_lower_index=indices[0][0],
        expected_conditional_upper_index=indices[0][1],
        expected_fallback_upper_index=indices[1][1],
        path_hashes=[path_hash((pc & ~7) + pos, pc) for pos in (position, fallback)])


def recipe(bank):
    if bank not in (1, 2, 3):
        raise ValueError("missing upper captured banks are 1, 2, 3")
    pc, position = {1:(0x40010006,6), 2:(0x40010004,8), 3:(0x40010005,7)}[bank]
    old, second = program(pc, position), program(pc ^ 0x40, position)
    assert old["expected_lower_index"] % 4 == old["expected_conditional_upper_index"] % 4 == bank
    assert old["expected_conditional_upper_index"] != second["expected_conditional_upper_index"]
    return dict(bank=bank, old=old, second=second)
