"""True empty-ROB CBO dispatch, no younger admission until original WB/retire."""
from dataclasses import replace

from lsqverify.load_queue.types import Load
from lsqverify.lsq_wrapper.types import Dispatch
from lsqverify.raw.types import SqPtr
from .special_owners import SpecialOwners


class SerializedCboOwners(SpecialOwners):
    async def allocate(self):
        assert len(self.owners)==1
        owner=self.owners[0]
        assert owner.cbo in range(4) and owner.rob==self.base.pending
        await self.cycle(dispatch=(Dispatch(True,2,owner.rob,1,store_end=SqPtr.encode(owner.position+1)),)+(Dispatch(),)*7)
        self.env.emit("serialized_CBO_alone_dispatch",position=owner.position,rob=owner.rob.value,
                      scope="empty external ROB, no younger Load admitted in the CBO epoch")

    async def retire_then_load(self):
        owner=self.owners[0]
        assert self.fulfilled(owner) and self.wbs and not self.wbs[-1]["denied"] and not self.wbs[-1]["corrupt"]
        self.base=replace(self.base,pending=self.load.execution.uop.rob,pending_next=self.load.execution.uop.rob)
        await self.idle(8)
        assert self.head==owner.position+1
        await self.cycle(dispatch=(Dispatch(True,1,self.load.execution.uop.rob,1,load_start=self.load.execution.uop.lq),)+(Dispatch(),)*7)
        await self.cycle(loads=(self.load,Load(),Load()))
        self.env.emit("serialized_CBO_retired_then_younger_Load_dispatched",position=owner.position,actual_CBO_WB_tick=self.wbs[-1]["tick"])
