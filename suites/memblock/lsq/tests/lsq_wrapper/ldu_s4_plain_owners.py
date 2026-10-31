"""Ordinary LD PF/AF S4 stimuli, no HLV/unsolicited poison assumptions."""
from dataclasses import asdict, dataclass, replace

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery
from .ldu_s4_owners import S4Program


@dataclass(frozen=True)
class OrdinaryEvent:
    tag_error: bool = False
    tlb_page_fault: bool = False
    mshr_nack: bool = False
    miss: bool = False


HIT,AF,PF,NACK,MISS=(OrdinaryEvent(),OrdinaryEvent(tag_error=True),OrdinaryEvent(tlb_page_fault=True),
                     OrdinaryEvent(mshr_nack=True),OrdinaryEvent(miss=True))
PATTERNS=dict(clean=(HIT,HIT),head_af=(AF,HIT),tail_af=(HIT,AF),head_pf=(PF,HIT),tail_pf=(HIT,PF),
              head_af_tail_pf=(AF,PF),head_pf_tail_af=(PF,AF),head_af_tail_nack=(AF,NACK),head_pf_tail_nack=(PF,NACK),
              head_nack_tail_af=(NACK,AF),head_nack_tail_pf=(NACK,PF),head_nack_tail_miss=(NACK,MISS),head_miss_tail_nack=(MISS,NACK))


def fault(e):return int(e.tag_error)<<5 | int(getattr(e,"tlb_page_fault",False))<<13


def cause(e):return None if fault(e) else 5 if e.mshr_nack else 6 if e.miss else None


class OrdinaryS4Program(S4Program):
    async def split(self,load,pattern,*,feedback=False):
        lane=self.lane
        head,tail=pattern
        va,pa=load.execution.vaddr,load.paddr
        tv=va//16*16+16
        tp=0xB246000 if self.page and va%4096==4092 else pa//16*16+16
        config=dict(load=asdict(load),head=asdict(head),tail=asdict(tail),tail_VA=tv,tail_PA=tp,
                    head_MSHR=3,tail_MSHR=9,head_TLB_id=2,tail_TLB_id=13,head_TLB_full=False,tail_TLB_full=True,
                    head_gpaddr=0x201000000+pa,tail_gpaddr=0x211000000+tp,head_nonleaf=False,tail_nonleaf=False,tail_hyper=False,
                    CSR_cache_error_enable=True,EnableAccurateLoadError=False,feedback=feedback,
                    boundary="ordinaryLD_PF_AF_chosen_before_S0_no_unsolicited_D_channel_or_HLV")
        self.env.emit("S4_ordinary_external_stimulus_before_S0",**config)
        lanes=lambda value,empty:tuple(value if n==lane else empty for n in range(3))
        def queries(event,addr,mask):
            u=load.execution.uop
            dv=not event.miss
            return (lanes(RarQuery(True,u.rob,u.lq,addr,dv),RarQuery()),
                    lanes(RawQuery(True,u.rob,u.sq,addr,mask,dv,u.rvc,u.ftq,u.offset,u.checkpoint),RawQuery()))
        await self.cycle(queries=lanes(Query(True,va,load.execution.uop.sq,3),Query()))
        await self.cycle(queries=lanes(Query(True,tv,load.execution.uop.sq,4),Query()),
                         translations=lanes(Translation(pa,bool(getattr(head,"tlb_page_fault",False))),Translation()))
        p=f"io_forward_{lane}_s2Resp_"
        assert self.env.observed[p+"valid"]==int(not getattr(head,"tlb_page_fault",False))
        rar,raw=queries(head,pa,61440)
        await self.cycle(translations=lanes(Translation(tp,bool(getattr(tail,"tlb_page_fault",False))),Translation()),rar_queries=rar,raw_queries=raw)
        assert self.env.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and self.env.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
        assert not self.env.observed[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        assert self.env.observed[p+"valid"]==int(not getattr(tail,"tlb_page_fault",False))
        hc,tc,hx,tx=cause(head),cause(tail),fault(head),fault(tail)
        hr,tr=bool(hx or hc is not None),bool(tx or tc is not None)
        rar,raw=queries(tail,tp,15)
        one=lanes(hr,False)
        await self.cycle(rar_queries=rar,raw_queries=raw,rar_revoke_last=one,raw_revoke_last=one)
        assert self.env.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and self.env.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
        assert not self.env.observed[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        selected=hc if hc is not None else tc
        exc=hx if hx else tx
        wb=bool(hx or hc is None and (tx or tc is None))
        state=next(s for s in reversed(self.loads) if not s["cancelled"] and s["load"].execution.uop.lq==load.execution.uop.lq)
        q=replace(load.execution,uop=replace(load.execution.uop,exceptions=exc),aligned_type=4,last_beat=bool(pa&64),
                  need_replay=selected is not None,causes=0 if selected is None else 1<<selected,unaligned_head=hc is not None,
                  replay_feedback=feedback,slot=state["grant"] if feedback else 0,mshr=3 if hc==6 else 9,
                  handled=head.miss if hc==6 else tail.miss,tlb_id=2 if hc is not None else 13,tlb_full=hc is None,
                  special_eligible=selected in (3,5,6))
        packet=replace(load,execution=q,exceptions=exc,update_address=wb,fullva=load.fullva if hx else tv,
                       gpaddr=config["head_gpaddr"] if hx else config["tail_gpaddr"],hyper=False,nonleaf=False)
        one,two=lanes(hr or tr,False),lanes(not hr and tr,False)
        await self.cycle(loads=lanes(packet,Load()),rar_revoke_last=one,raw_revoke_last=one,rar_revoke_older=two,raw_revoke_older=two)
        self.last_packet=packet
        return packet
