"""Shared semantic composition for cold-early, SC-disabled component scopes.

TAGE state/frames are independently owned. MainBTB base inputs remain a
declared cut point; branch targets come from the program's stimulus contract.
This is not an all-predictor BPU reference model.
"""
from dataclasses import dataclass

from toffee import CheckContext, ScoreboardMode

from bpuverify.bpu.model.selection import Branch, Kind, early, middle, final, middle_repair, final_repair


def prediction_values(tick,prediction):
    return (tick,prediction.start_pc,prediction.target,prediction.taken,prediction.position,
            prediction.s2_override,prediction.s3_override)


def project(tick,pc,choice,mid=False,late=False):
    branch = choice.branch
    return tick,pc,branch.target,int(branch.taken),branch.position,int(mid),int(late)


@dataclass(frozen=True,slots=True)
class ExpectedSelection:
    metadata: tuple
    early: tuple
    repairs: tuple
    context: CheckContext

    def check(self,board,source,repairs):
        board.check(expected=self.early,actual=prediction_values(source.prediction_tick,source.prediction),context=self.context)
        board.check(expected=self.repairs,actual=tuple(prediction_values(tick,p) for tick,p in repairs),context=self.context)


def selection_for(checker,source,*,pc,positions,targets):
    meta = tuple(checker.source_expected(source,p) for p in positions)
    frame,wanted,bases = next((frame,wanted,bases) for tick,frame,wanted,_,bases in checker.expected
                             if tick==source.meta_tick-4)
    context = CheckContext(checker.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
        request=dict(point='independent TAGE direction composition',source=source,owned_metadata=meta,
                     frame=frame,bases=bases,state=checker.model.state()))
    checker.board.check(expected=(pc,4),actual=(frame.read.pc,source.meta_tick-source.prediction_tick),context=context)
    slots = tuple(next(slot for slot,base in enumerate(bases)
        if base.valid and frame.positions[slot]==p) for p in positions)
    entries = tuple(Branch(p,target,Kind.CONDITIONAL,bases[slot].taken)
                    for p,target,slot in zip(positions,targets,slots,strict=True))
    s1 = early(pc)
    s2 = middle(pc,entries,tuple(bool(wanted[f'{slot}.fast_taken']) if wanted.get(f'{slot}.fast_valid') else None
                               for slot in slots))
    s3 = final(pc,entries,tuple(bool(wanted[f'{slot}.taken']) if wanted[f'{slot}.valid'] else None
                              for slot in slots),(None,)*len(slots))
    repaired = middle_repair(s1,s2)
    repairs = []
    if repaired:
        repairs.append(project(source.prediction_tick+2,pc,s2,mid=True))
    if final_repair(s1,s2,s3,corrected_middle=repaired):
        repairs.append(project(source.meta_tick,pc,s3,late=True))
    return ExpectedSelection(meta,project(source.prediction_tick,pc,s1),tuple(repairs),context)
