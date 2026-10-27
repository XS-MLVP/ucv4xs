"""The remaining lower bank1 resident source, with complete representable tags."""
from bpuverify.bpu.model.phr.model import fold
from bpuverify.bpu.model.phr.model import path_hash

from bpuverify.bpu.case.bypass import history_plan as _v15
read_indices=_v15.read_indices
full_tags=_v15.full_tags
recurring_history=_v15.recurring_history


def recipe(bank):
    if bank!=1:
        raise ValueError('this additional recipe targets physical bank1 only')
    pc,position,fallback=0x40010006,6,10
    histories=[recurring_history(pc,pos) for pos in (position,fallback)]
    indices=[read_indices(pc,(fold(h,6,6),fold(h,12,9))) for h in histories]
    assert indices[0][0]==indices[1][0] and indices[0][0]%4==bank
    assert indices[0][1]%4==bank
    return dict(bank=bank,pc=pc,position=position,fallback=fallback,
        conditional_history=histories[0],fallback_history=histories[1],
        expected_lower_index=indices[0][0],expected_conditional_upper_index=indices[0][1],
        expected_fallback_upper_index=indices[1][1],
        path_hashes=[path_hash((pc&~7)+pos,pc) for pos in (position,fallback)])
