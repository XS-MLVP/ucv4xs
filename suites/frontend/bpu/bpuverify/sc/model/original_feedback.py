"""Reuse the qualified independent eligibility oracle; add feedback intent."""
from dataclasses import dataclass

from bpuverify.sc.transaction.types import ScBatchTraining,ScBranchFeedback
from bpuverify.sc.model.eligibility import EligibilityProgram,GATES,META


@dataclass(frozen=True)
class FeedbackProgram(EligibilityProgram):
    rejection_gate: str

    def __post_init__(self):
        super().__post_init__()
        if self.rejection_gate not in GATES:raise ValueError('one explicit ineligible original-source cause required')

    @property
    def profile(self):return super().profile+'.ignore-'+self.rejection_gate

    def feedback_outcome(self,owner):
        if owner not in self.owners:raise ValueError('outcome needs a declared original owner')
        # A decoded nonconditional direct branch really takes its target.
        # Its negative learned correction is the discriminating adversary;
        # the positive peer is a legal same-direction preservation control.
        return 1 if self.rejection_gate=='nonconditional' else 1-owner.outcome

    def rejected_feedback(self,owner,meta):
        if owner not in self.owners:raise ValueError('feedback needs a declared original owner')
        return ScBatchTraining(owner.pc,meta,(ScBranchFeedback(owner.first_position,self.feedback_outcome(owner),0,
            mbtb_hit=int(self.rejection_gate!='main-miss'),
            branch_type=2 if self.rejection_gate=='nonconditional' else 1),))


def expected_offer(transaction,*,branch_count,fold_count):
    """Full independent interface witness, not the production drive codec."""
    branch,=transaction.branches
    assert branch.prediction_slot==0
    empty=dict(rawHit=0,position=0,attribute=dict(branchType=0,rasAction=0),counter_value=0)
    source=dict(rawHit=branch.mbtb_hit,position=branch.position,
        attribute=dict(branchType=branch.branch_type,rasAction=0),counter_value=0)
    return dict(valid=1,ready=1,pc=transaction.pc,history=(1,0,0,0,(0,)*fold_count),
        meta={key:tuple(transaction.meta[key]) for key in META},mbtb_meta=((source,empty),(empty,empty)),
        branches=tuple(dict(valid=int(index==0),taken=branch.actual_taken if index==0 else 0,
            position=branch.position if index==0 else 0,branch_type=branch.branch_type if index==0 else 0)
            for index in range(branch_count)))
