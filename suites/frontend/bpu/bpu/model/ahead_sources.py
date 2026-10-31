"""Owned ahead reads composed with independently learned Micro/Main BTBs.

Ahead prediction is not a lookup at the current request PC: read the previous
path's index, match its entries against the next target, and reuse that same
read on a later correction. S3 learning uses the frame frozen at S1 acceptance.
The current profile admits nonconditional control flow. Conditional early
learning requires the independent MicroTAGE composition and explicitly raises;
this is not an always-miss replacement for an enabled learned predictor.
"""
from dataclasses import dataclass

from suites.frontend.bpu.abtb.model.semantic import AbtbReference,Events,Feedback,Source
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.model.selection import Branch,Kind,StackAction,early


def history_feature(checkpoint):
    # The frozen configuration uses the (6,6) fold's low four bits. Compute
    # from owned logical history, not a sampled fold or an ABTB index token.
    return checkpoint.history % 16


def old_history(events,cycle,issued):
    if events.redirect is not None:return events.redirect.source
    first,second,third=cycle.tokens
    if cycle.final_repair:return third.history
    if cycle.middle_repair:return second.history
    return first.history if first is not None else None if issued is None else issued.history


@dataclass(frozen=True,slots=True)
class AheadSnapshot:
    owner: object
    frame: object
    enabled: bool


class AheadSources(BranchTargetSources):
    has_own_ahead=True
    unsupported_learning=(3,4,5,6)

    def __init__(self):
        super().__init__()
        self.ahead=AbtbReference()
        self.ahead_reads={}
        self.last_ahead_events=None

    def reset(self):
        super().reset()
        self.ahead.reset()
        self.ahead_reads.clear()
        self.last_ahead_events=None

    def snapshot(self,token):
        saved=self.ahead_reads.get(token.history.sequence)
        if saved is None or saved.owner is not token.history:
            raise ValueError('AheadBTB source is absent, retired or belongs to another checkpoint')
        return saved

    def choose(self,token,stage,enabled):
        base=super().choose(token,stage,enabled)
        if stage!=1 or not enabled[1]:return base
        frame=self.ahead.frame
        candidates=[None]*4
        if frame is not None and frame.valid:
            if frame.pc!=token.pc:raise AssertionError('AheadBTB read frame is not the current owned request')
            values=frame.values()
            for way,hit in enumerate(frame.hits):
                if not hit:continue
                candidates[way]=Branch(values[f'{way}.position'],values[f'{way}.target'],Kind(values[f'{way}.kind']),
                    bool(values[f'{way}.taken']),StackAction(values[f'{way}.action']))
        return early(token.pc,micro=base.branch if base.source=='micro' else None,ahead=tuple(candidates),
            short_history=self.early_directions(token,tuple(candidates),enabled))

    def early_directions(self,token,candidates,enabled):
        if any(branch is not None and branch.kind==Kind.CONDITIONAL for branch in candidates):
            raise NotImplementedError('conditional AheadBTB prediction requires independent MicroTAGE composition')
        return (None,)*4

    def validate(self,events,cycle):
        super().validate(events,cycle)
        self.validate_early(events,cycle)

    def validate_early(self,events,cycle):
        if cycle.enabled[1] and (any(choice is not None and choice.branch.kind==Kind.CONDITIONAL for choice in cycle.decisions)
                or events.feedback is not None and any(branch is not None and branch.kind==Kind.CONDITIONAL for branch in events.feedback.branches)):
            raise NotImplementedError('conditional early learning requires independent MicroTAGE composition')

    def fast_feedback(self,token,decision):
        saved=self.snapshot(token)
        frame=saved.frame
        if not saved.enabled or frame is None or not frame.valid:return None
        branch=decision.branch
        return Feedback(token.pc,branch.target,branch.taken,branch.position,int(branch.kind),int(branch.action),True,
            frame.read.row,1<<frame.read.bank,tuple(Source(hit,entry.position,entry.kind,entry.action,entry.target)
                for hit,entry in zip(frame.hits,frame.read.entries,strict=True)))

    def defined_metadata(self,token):
        saved=self.snapshot(token);frame=saved.frame
        active=saved.enabled and frame is not None and frame.valid
        values=dict(valid=int(active))
        if not active:return values
        values.update(row=frame.read.row,banks=1<<frame.read.bank)
        for way,(hit,entry) in enumerate(zip(frame.hits,frame.read.entries,strict=True)):
            values[f'{way}.hit']=int(hit)
            if hit:
                values.update({f'{way}.position':entry.position,f'{way}.kind':entry.kind,
                    f'{way}.action':entry.action,f'{way}.target_low':entry.target})
        return values

    def advance(self,events,cycle,issued):
        first,second,third=cycle.tokens
        if first is not None and cycle.fires[1] and not cycle.flushes[0]:
            self.ahead_reads[first.history.sequence]=AheadSnapshot(first.history,self.ahead.frame,cycle.enabled[1])
        feedback=self.fast_feedback(third,cycle.decisions[2]) if third is not None and cycle.enabled[1] else None
        history=old_history(events,cycle,issued)
        first_choice=cycle.decisions[0]
        ahead_events=Events(read_pc=cycle.next_pc,history=0 if history is None else history_feature(history),
            select=cycle.fires[0],match_pc=cycle.next_pc if first_choice is None else first_choice.branch.target,
            consume=cycle.fires[1],remember=cycle.fires[2],
            override='s3' if cycle.final_repair else 's2' if cycle.middle_repair else None,
            override_pc=cycle.decisions[2].branch.target if cycle.final_repair else cycle.decisions[1].branch.target if cycle.middle_repair else 0,
            redirect=events.redirect is not None,feedback=feedback,enabled=cycle.enabled[1],ready=events.initialization_complete)
        super().advance(events,cycle,issued)
        self.ahead.advance(ahead_events)
        self.last_ahead_events=ahead_events

    def retain(self,tokens):
        keys={token.history.sequence for token in tokens}
        self.ahead_reads={key:value for key,value in self.ahead_reads.items() if key in keys}

    def main_pending(self):
        return (super().main_pending() or self.ahead.offered is not None or self.ahead.decision is not None
            or self.ahead.cleanup is not None or any(pending.outstanding for pending in self.ahead.pending))
