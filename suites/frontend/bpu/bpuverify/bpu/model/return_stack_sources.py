"""Nine independent algorithms, with source-owned logical return stacks.

Calls/returns come from our S1/S2/S3 selections, never component input wires.
Main RAS owns exact pre-S3 originals; public commits and recoveries must name
those originals. MicroRAS reduces the two in-flight operation windows using
our main-stack top. No sampled target, pointer or operation seeds either model.
"""
from dataclasses import dataclass, replace

from bpuverify.bpu.model.statistical_joint_sources import StatisticalJointSources
from bpuverify.bpu.model.selection import StackAction
from bpuverify.ras.model.semantic import RasReference, Events, Recovery, Retirement, instruction_return
from bpuverify.uras.model.semantic import UrasReference, RasEvents, Operation, Action


@dataclass(frozen=True, slots=True)
class ReturnStackSnapshot:
    owner: object
    original: object
    top: int
    decision: object = None

    def redirect_metadata(self):
        group, calls, repeat = self.original.program.redirect_key()
        return dict(ssp=group,sctr=repeat,tosw=dict(flag=calls//16,value=calls%16))

    def commit_metadata(self):
        group, calls = self.original.program.commit_key()
        return dict(ssp=group,tosw=dict(flag=calls//16,value=calls%16))


def operation(token, decision):
    return Operation(Action(decision.branch.action),token.pc,decision.branch.position)


class ReturnStackSources(StatisticalJointSources):
    has_own_ras = True
    unsupported_learning = ()

    def __init__(self):
        super().__init__()
        self.ras = RasReference()
        self.micro_ras = UrasReference()
        self.return_originals = {}

    def reset(self):
        super().reset()
        self.ras.reset()
        self.micro_ras.reset()
        self.return_originals.clear()

    def return_snapshot(self, token):
        return self._return_owner(token.history)

    def _return_owner(self, owner):
        saved = self.return_originals.get(owner.sequence)
        if saved is None or saved.owner is not owner:
            raise ValueError('return-stack source is absent, retired or belongs to another original')
        self.ras.require_original(saved.original)
        return saved

    def choose(self, token, stage, enabled):
        result = super().choose(token,stage,enabled)
        if not result.branch.taken or not result.branch.action & StackAction.RETURN:
            return result
        if stage == 1 and self.micro_ras.result.usable:
            # MicroRAS's current public forwarding contract is independent
            # of enable: Bpu.scala wires enable, but MicroRas does not use it.
            # Keep the real early predictor source label in perf metadata.
            return replace(result,branch=replace(result.branch,target=self.micro_ras.result.target))
        if stage == 3 and enabled[2] and enabled[6]:
            return replace(result,branch=replace(result.branch,target=self.ras.projection['top']),source='return-stack')
        return result

    def return_events(self, events, cycle):
        first, second, third = cycle.tokens
        early, middle, late = cycle.decisions
        recovery = retirement = original = None
        if events.redirect is not None:
            request = events.redirect
            saved = self._return_owner(request.source)
            group,calls,repeat = saved.original.program.redirect_key()
            recovery = Recovery(group,calls,repeat,int(request.action),
                2*(request.cfi_pc+1) if request.action & StackAction.CALL else None,saved.original)
        if events.commit is not None:
            request = events.commit
            saved = self.return_snapshot(request.source)
            group,calls = saved.original.program.commit_key()
            retirement = Retirement(group,calls,int(request.action),saved.original)
        if third is not None:
            original = self.return_snapshot(third).original
        action = None if third is None else int(late.branch.action)
        ras = Events(action=action,address=instruction_return(third.pc*2,late.branch.position)
            if action is not None and action & 2 else None,recovery=recovery,retirement=retirement,
            enabled=bool(cycle.enabled[2] and cycle.enabled[6]),origin=original)
        micro = RasEvents(main_top=self.ras.projection['top'],
            accept=operation(first,early) if cycle.fires[1] else None,
            correct_pending=operation(second,middle) if cycle.middle_repair else None,
            correct_retiring=operation(third,late) if cycle.final_repair else None,
            advance=bool(cycle.fires[2]),retire=bool(cycle.fires[3]),redirect=events.redirect is not None)
        return ras,micro

    def validate(self, events, cycle):
        ras,_ = self.return_events(events,cycle)
        # In particular, a cancelled/borrowed/duplicate commit must fail before
        # any of the nine algorithms, path history or token stages can change.
        self.ras.preview(ras)
        super().validate(events,cycle)

    def advance(self, events, cycle, issued):
        ras,micro = self.return_events(events,cycle)
        third = cycle.tokens[2]
        if third is not None:
            saved = self.return_snapshot(third)
            self.return_originals[third.history.sequence] = replace(saved,decision=cycle.decisions[2])
        self.micro_ras.advance(micro)
        self.ras.advance(ras)
        second = cycle.tokens[1]
        if second is not None and not cycle.flushes[1]:
            original = self.ras.capture_original()
            self.return_originals[second.history.sequence] = ReturnStackSnapshot(
                second.history,original,self.ras.projection['top'])
        super().advance(events,cycle,issued)

    def validate_release(self, token):
        saved = self.return_originals.get(token.history.sequence)
        if saved is None:
            return
        original = saved.original
        if ((self.ras.pending_recovery is not None and self.ras.pending_recovery.origin is original)
                or self.ras.pending_retirement_origin is original):
            raise ValueError('pending return-stack recovery or retirement still owns this original')

    def retain(self, tokens):
        tokens = tuple(tokens)
        keys = {token.history.sequence for token in tokens}
        expired = [key for key in self.return_originals if key not in keys]
        for key in expired:
            saved = self.return_originals[key]
            if ((self.ras.pending_recovery is not None and self.ras.pending_recovery.origin is saved.original)
                    or self.ras.pending_retirement_origin is saved.original):
                raise ValueError('pending return-stack operation still owns this source')
        super().retain(tokens)
        for key in expired:
            self.ras.release_original(self.return_originals.pop(key).original)

    def main_pending(self):
        return super().main_pending() or self.ras.pending_recovery is not None or self.ras.pending_retirement is not None
