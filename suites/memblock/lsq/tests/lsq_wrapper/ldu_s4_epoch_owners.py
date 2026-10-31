"""Unique stable virtual/physical pages for real contiguous S4 generations."""
from dataclasses import replace

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery
from .ldu_s4_precise_owners import PreciseOrdinaryS4Program, PATTERNS as BASE_PATTERNS, LEGAL_CASES
from .ldu_s4_plain_owners import HIT, MISS, AF, PF
from .memory_owners import cached_load
from .mixed_owners import rob_pointer


PATTERNS={**BASE_PATTERNS,"head_miss_tail_af":(MISS,AF),"head_miss_tail_pf":(MISS,PF)}
MISS_FAULT_CASES=((False,"head_miss_tail_af"),(True,"head_miss_tail_af"),(True,"head_miss_tail_pf"))
EPOCH_CASES=(*LEGAL_CASES,*MISS_FAULT_CASES)


class EpochPreciseS4Program(PreciseOrdinaryS4Program):
    def __init__(self,*args,page_tag=0,**kwargs):
        super().__init__(*args,**kwargs)
        self.page_tag=page_tag
        # This positive epoch stream is intentionally non-aliasing: Store uses
        # word2, Load head/tail use word3/word0. Existing alias FAILs stay in the
        # full random/Forward ranges; this is not a replacement for them.
        self.store=replace(self.store,vaddr=self.store.vaddr+32,paddr=self.store.paddr+32)
        offset=4092 if self.page else 60
        self.target=cached_load(self.start_lq+1,rob_pointer(self.start_rob+3),self.start_sq+1,
                                0x20000000+16384*page_tag+offset,0xA1000000+16384*page_tag+offset)

    async def split(self,load,pattern,*,feedback=False):
        self.last_cache_events=pattern
        lane=self.lane;head,tail=pattern;va,pa=load.execution.vaddr,load.paddr
        tv=va//16*16+16
        tp=0xB2000000+16384*self.page_tag if va%4096==4092 else pa//16*16+16
        self.checker.declare(load,pattern,lane,self.env.last_tick+2,feedback,tail_pa=tp)
        lanes=lambda value,empty:tuple(value if n==lane else empty for n in range(3))
        def query(event,addr,mask):
            u=load.execution.uop;dv=not event.miss
            return (lanes(RarQuery(True,u.rob,u.lq,addr,dv),RarQuery()),
                    lanes(RawQuery(True,u.rob,u.sq,addr,mask,dv,u.rvc,u.ftq,u.offset,u.checkpoint),RawQuery()))
        self.env.emit("S4_unique_page_source_before_S0",head_VA=va,head_PA=pa,tail_VA=tv,tail_PA=tp,page_tag=self.page_tag,
                      scope="chosen stable external TLB mapping, not native TLB or persisted per-cycle trace")
        await self.cycle(queries=lanes(Query(True,va,load.execution.uop.sq,3),Query()))
        await self.cycle(queries=lanes(Query(True,tv,load.execution.uop.sq,4),Query()),
                         translations=lanes(Translation(pa,head.tlb_page_fault),Translation()))
        rar,raw=query(head,pa,61440)
        await self.cycle(translations=lanes(Translation(tp,tail.tlb_page_fault),Translation()),rar_queries=rar,raw_queries=raw)
        hx=(32 if head.tag_error else 0)|(8192 if head.tlb_page_fault else 0)
        tx=(32 if tail.tag_error else 0)|(8192 if tail.tlb_page_fault else 0)
        hc=None if hx else 5 if head.mshr_nack else 6 if head.miss else None
        tc=None if tx else 5 if tail.mshr_nack else 6 if tail.miss else None
        hr,tr=bool(hx or hc is not None),bool(tx or tc is not None)
        rar,raw=query(tail,tp,15)
        one=lanes(hr,False)
        await self.cycle(rar_queries=rar,raw_queries=raw,rar_revoke_last=one,raw_revoke_last=one)
        selected=hc if hc is not None else tc;exc=hx if hx else tx
        state=next(s for s in reversed(self.loads) if not s["cancelled"] and s["load"].execution.uop.lq==load.execution.uop.lq)
        q=replace(load.execution,uop=replace(load.execution.uop,exceptions=exc),aligned_type=4,last_beat=bool(pa&64),
                  need_replay=selected is not None,causes=0 if selected is None else 1<<selected,unaligned_head=hc is not None,
                  replay_feedback=feedback,slot=state["grant"] if feedback else 0,mshr=3 if hc==6 else 9,
                  handled=head.miss if hc==6 else tail.miss,tlb_id=2 if hc is not None else 13,tlb_full=hc is None,special_eligible=selected in(3,5,6))
        packet=replace(load,execution=q,exceptions=exc,update_address=bool(hx or hc is None and(tx or tc is None)),
                       fullva=load.fullva if hx else tv,gpaddr=0x201000000+pa if hx else 0x211000000+tp,hyper=False,nonleaf=False)
        one,two=lanes(hr or tr,False),lanes(not hr and tr,False)
        await self.cycle(loads=lanes(packet,Load()),rar_revoke_last=one,raw_revoke_last=one,rar_revoke_older=two,raw_revoke_older=two)
        self.last_packet=packet
        return packet
