"""Independent MainBTB feedback semantics; never call the driver's encoder."""
from copy import deepcopy
from suites.frontend.bpu.models.configuration import MAIN_WAYS, ALIGN_HALFWORDS


def expected_mbtb_feedback(transaction, *, branch_count=8):
    if not 1 <= len(transaction.branches) <= branch_count:
        raise ValueError('MainBTB feedback does not fit the resolve vector')
    branches = tuple(transaction.branches)+(None,)*(branch_count-len(transaction.branches))
    if sum(bool(branch.mispredict) for branch in branches if branch is not None) > 1:
        raise ValueError('MainBTB feedback permits at most one misprediction')
    # The whole-chip training port carries the four trainable MainBTB ways
    # per alignment; the VictimBTB snapshot is a prediction-only output and
    # has no metadata leaf to drive.
    return {'ready':1,'pc':transaction.pc,'next_pc':(transaction.pc//ALIGN_HALFWORDS+1)*ALIGN_HALFWORDS,
            'meta_entries':tuple(tuple(deepcopy(entry) for entry in bank[:MAIN_WAYS])
                                 for bank in transaction.meta_entries),
            'resolved':tuple(None if branch is None else {
                'target':branch.target,'taken':branch.taken,'position':branch.position,
                'branch_type':branch.branch_type,'ras_action':branch.ras_action,'mispredict':branch.mispredict,
            } for branch in branches)}


def observed_mbtb_feedback(sample):
    bits = sample['bits']
    return {'ready':sample['ready'],'pc':bits['start_pc0'],'next_pc':bits['start_pc1'],
            'meta_entries':tuple(tuple(deepcopy(entry) for entry in bank) for bank in bits['meta_entries']),
            'resolved':tuple(None if not branch['valid'] else {key:branch[key]
                for key in ('target','taken','position','branch_type','ras_action','mispredict')}
                for branch in bits['branches'])}
