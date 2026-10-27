"""Choose an input-only recurrence; retain complete four-way requirements."""
from bpuverify.common.model.configuration import PHR_STORAGE_BITS
from bpuverify.bpu.case.abtb.later_taken_four_plan import (
    PHASES, checkpoint_route, input_qualified, final_comparison, required_operations,
    plan as four_plan, programs as four_programs, selected_program as four_selected,
    joint_proof as four_proof)
from bpuverify.bpu.case.abtb.later_taken_five_plan import (
    plan as five_plan, programs as five_programs, selected_program as five_selected,
    joint_proof as five_proof)


def plan(bank, entry_set):
    five_edges = bank != 0
    intent = dict((five_plan if five_edges else four_plan)(bank, entry_set))
    intent['recurrence_edges'] = 5 if five_edges else 4
    intent['natural_cycles_per_phase'] = max(64, (PHR_STORAGE_BITS + 7)//8 + 2)
    intent['cadence_selection_from_input_bank_only'] = True
    return intent


def programs(intent, alias):
    return (five_programs if intent['recurrence_edges'] == 5 else four_programs)(intent, alias)


def selected_program(intent, alias, goal):
    return (five_selected if intent['recurrence_edges'] == 5 else four_selected)(intent, alias, goal)


def joint_proof(intent):
    return (five_proof if intent['recurrence_edges'] == 5 else four_proof)(intent)
