
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from math import prod
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef
from bpuverify.abtb.model.state.counter import TRANSITIONS
from bpuverify.abtb.case.state.scope import bank_index
from bpuverify.abtb.case.state.scope import set_axis
from bpuverify.abtb.case.state.scope import way_axis
from bpuverify.abtb.case.state.scope import order_axis


def transition_coverage(bank, sets, *, capture=True):
    bank_index(bank)
    sets = set_axis(sets)
    axes = dict(bank=(bank,),set_index=tuple(sets),way=range(4),transition=TRANSITIONS)
    points = tuple(CoverPointDef(name,{str(value):Bin.values(value) for value in values})
                   for name,values in axes.items())
    return CoverGroupDef('abtb_counter_transitions',points,
        crosses=(CrossDef('physical_transition_matrix',tuple(axes),
            max_auto_bins=prod(len(values) for values in axes.values())),)
    ).instantiate(f'kunminghu_v3.abtb.counter_transitions.bank{bank}', capture=capture)


def write_coverage(group,path):
    write_functional_coverage(CoverageDatabase([group]), output_path(path))


def gate_coverage(bank,sets):
    bank_index(bank)
    sets = set_axis(sets)
    axes=dict(bank=(bank,),set_index=tuple(sets),role=('disabled_nt','disabled_t','invalid_meta_nt','invalid_meta_t'))
    points=tuple(CoverPointDef(name,{str(value):Bin.values(value) for value in values})
                 for name,values in axes.items())
    return CoverGroupDef('abtb_counter_feedback_gates',points,
        crosses=(CrossDef('physical_gate_matrix',tuple(axes),
            max_auto_bins=prod(len(values) for values in axes.values())),)
    ).instantiate(f'kunminghu_v3.abtb.counter_feedback_gates.bank{bank}')



def priority_coverage(bank):
    bank_index(bank)
    axes = dict(bank=(bank,), way=range(4), before=range(4), operation=('inc', 'dec'))
    points = tuple(CoverPointDef(name, {str(value): Bin.values(value) for value in values})
                   for name, values in axes.items())
    return CoverGroupDef('abtb_same_cell_reset_training_priority', points,
        crosses=(CrossDef('real_same_cell_collision', tuple(axes), max_auto_bins=32),)
    ).instantiate(f'kunminghu_v3.abtb.reset_training_priority.bank{bank}')


ORDERS = ('ascending', 'descending', 'interleaved', 'boundary')
PHASES = ('pending', 'dirty_rewrite', 'drained', 'clean_reactivate')


def capacity_coverage(bank, orders):
    bank_index(bank)
    orders = order_axis(orders)
    axes = dict(bank=(bank,), order=tuple(orders), slot=range(4), phase=PHASES)
    points = tuple(CoverPointDef(name, {str(value): Bin.values(value) for value in values})
                   for name, values in axes.items())
    return CoverGroupDef('abtb_write_buffer_capacity', points,
        crosses=(CrossDef('four_slots_full_payload_lifecycle', tuple(axes), max_auto_bins=64),)
    ).instantiate(f'kunminghu_v3.abtb.write_buffer_capacity.bank{bank}')


def replacer_coverage(bank, same_set, *, sets, victims):
    bank_index(bank)
    sets, victims = set_axis(sets), way_axis(victims)
    if type(same_set) is not bool:
        raise ValueError('same_set must be bool')
    axes = dict(bank=(bank,), set_index=sets, victim_way=victims,
                relation=('same_set' if same_set else 'different_set',))
    points = tuple(CoverPointDef(name,{str(value):Bin.values(value) for value in values})
                   for name,values in axes.items())
    return CoverGroupDef('abtb_replacer_priority',points,
        crosses=(CrossDef('physical_replacer_priority',tuple(axes),
            max_auto_bins=prod(len(values) for values in axes.values())),)
    ).instantiate(f'kunminghu_v3.abtb.replacer_priority.bank{bank}.same{same_set}')
