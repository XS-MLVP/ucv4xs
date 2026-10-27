"""Full-domain kind stream, sticky CBO intent, actual NoSpec/BlockBack boundary."""
from lsqverify.lsq_wrapper.types import Dispatch
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import QueuePtr
from .mixed_owners import rob_pointer
from .normal_mixed_owners import NormalMixedOwners


class SerializedMixedOwners(NormalMixedOwners):
    def __init__(self,env,seed):
        super().__init__(env,seed)
        self.planned_kind=None
        self.env.emit("serialized_mixed_producer_contract",KINDS=self.KINDS,WEIGHTS=self.WEIGHTS,
                      sticky_CBO_intent=True,NoSpec_BlockBack=True,LSQ_physical_empty_not_required=True)

    def dispatch(self,limit,*,forced=None):
        items,packet=[],[Dispatch()]*8
        pending_only=self.fair and forced is None
        if pending_only and self.planned_kind is None:
            return tuple(packet),items
        barrier=any(s["subtype"]=="cbo" and not s["retired"] and not s["rob_cancelled"] for s in self.program)
        if barrier:
            self.counts["CBO_BlockBack_admission_wait_edges"]+=1
            return tuple(packet),items
        for _ in range(limit):
            if self.rob_tail-self.pending()>=300:break
            kind=self.planned_kind or forced or self.rng.choices(self.KINDS,self.WEIGHTS)[0]
            if kind=="cbo" and (items or any(not s["retired"] and not s["rob_cancelled"] for s in self.program)):
                self.planned_kind=kind
                self.counts["CBO_NoSpec_sticky_intent_wait_edges"]+=1
                break
            is_load=kind in self.KINDS[:4]
            if (self.lq_tail-self.lq_head>=120) if is_load else (self.sq_tail-self.sq_head>=128):
                # Preserve even a capacity-blocked sampled instruction type.
                self.planned_kind=kind
                break
            items.append(self.make(kind,unique=forced is not None))
            if self.planned_kind is not None:
                assert self.planned_kind==kind
                self.planned_kind=None
            if kind=="cbo":
                self.counts["actual_empty_ROB_serial_CBO_admissions"]+=1
                break
            if pending_only:break
        for lane,s in zip(sorted(self.rng.sample(range(8),len(items))),items):
            packet[lane]=Dispatch(True,1 if s["kind"]=="load" else 2,rob_pointer(s["order"]),1,
                                  load_start=QueuePtr.encode(s["position"]) if s["kind"]=="load" else QueuePtr(),
                                  store_end=SqPtr.encode(s["position"]+1) if s["kind"]=="store" else SqPtr())
        return tuple(packet),items

    async def drain(self):
        await super().drain()
        while self.planned_kind is not None:
            planned=self.planned_kind
            before=self.sequence
            # No new random type is drawn: dispatch consumes this sticky
            # pending intent first; even its ordinary alias/error domain stays.
            await self.step()
            assert self.sequence>before and any(s["uid"]>before and s["subtype"]==planned for s in self.history)
            await super().drain()
        self.env.emit("serialized_mixed_all_pending_kind_intents_dispatched",remaining=0)
