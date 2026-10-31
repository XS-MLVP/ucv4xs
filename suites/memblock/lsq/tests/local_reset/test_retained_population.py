"""All16 retained external SIDs: real returns precede legal SID reallocation."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from .owners import RetainedUncacheProgram

from suites.memblock.lsq.legacy_pins import P


class FullPopulationProgram(RetainedUncacheProgram):
    async def accept_visible(self,loads,sid):
        for _ in range(80):
            if self.env.observed[P.p_uncache_req_valid]:break
            await self.cycle()
        else:raise AssertionError("full16 visible original request never arrived")
        pa=self.env.observed[P.p_uncache_req_bits_addr]
        load=next(p for p in loads if p.paddr==pa)
        mid=await self.accept(load,sid)
        return dict(load=load,mid=mid,sid=sid)

    async def run(self):
        old=[self.load(i,10+i,i) for i in range(16)]
        for load in old:await self.dispatch(load)
        for load in old:await self.initial(load)
        external=[await self.accept_visible(old,sid) for sid in range(16)]
        assert {a["mid"] for a in external}==set(range(16))
        for _ in range(6):await self.cycle(reset=True)
        await self.idle(8)
        fresh=[self.load(i,80+i,16+i) for i in range(16)]
        for load in fresh:await self.dispatch(load)
        for load in fresh:await self.initial(load)
        new=[]
        for index,a in enumerate(external):
            await self.cycle(bus=replace(self.base.bus,response=True,response_id=a["sid"],data=0xF00DBAAD00000000+index,
                                         error=bool(index%2),nderr=not bool(index%2)))
            new.append(await self.accept_visible(fresh,a["sid"]))
        assert {a["mid"] for a in new}==set(range(16))
        for a in new:
            await self.new_return(a["sid"],0x1020304050607000+a["load"].execution.uop.lq.value)
        pending={p.execution.uop.lq.value:p for p in fresh}
        for _ in range(120):
            if not pending:break
            bank=next((b for b in range(3) if self.env.observed[P.io(f"replay_{b}_valid")]),None)
            if bank is None:await self.cycle();continue
            value=self.env.observed[P.io(f"replay_{bank}_bits_uop_lqIdx_value")]
            load=pending.pop(value)
            await self.finish_load(load,await self.grant(load),assert_empty=False)
        assert not pending
        await self.idle(16)
        assert self.env.observed[P.p_lqEmpty] and self.env.observed[P.p_sqEmpty] and not self.env.observed[P.p_replayAllocate]
        assert not self.env.observed[P.p_uncache_req_valid] and not self.env.observed[P.p_ldExceptionInfo_valid]
        self.report=self.checker.finish()
        assert len(self.report["UIDs"])==32 and len(self.report["same_slot_completion_witnesses"])==16
        return self.report

    def write(self,passed,error=None):
        result=dict(nodeid=self.env.nodeid,passed=passed,error=error,lane=self.lane,phase="full16",native_boot_records=self.boot_records,
                    online_check=self.report if passed else dict(counts=dict(self.checker.counts),events=self.checker.events,unfinished=True),
                    scope="full-output native comparison and bounded per-UID events; declared retained external NC pool, not native Uncache/SoC reset")
        with Path(self.env.journal.name).with_name("local-reset-summary.json").open("x") as f:f.write(json.dumps(result,indent=2)+"\n")


@pytest.mark.parametrize("lane",range(3))
async def test_local_reset_retains_full16_external_SIDs_and_new_same_LQ_slots_all_really_complete(lsq,lane):
    trace=FullPopulationProgram(lsq,lane,"full16")
    try:await trace.run()
    except BaseException as exc:
        trace.write(False,repr(exc));raise
    trace.write(True)
