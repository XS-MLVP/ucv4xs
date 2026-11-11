"""Real scalar head/tail producer inputs, original effects and precise traps.

External cache events are recorded BEFORE S0. They are declared producer
stimuli, not native LoadUnit/DCache proof or an actor-computed answer oracle.
"""
from dataclasses import asdict, dataclass, replace

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Dispatch
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.rar.transactions import Query as RarQuery
from suites.memblock.lsq.testbenches.raw.transactions import Query as RawQuery
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.transactions import Refill
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.mixed_owners import rob_pointer
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import word


@dataclass(frozen=True)
class CacheEvent:
    tag_error: bool = False
    tl_d_corrupt: bool = False
    mshr_nack: bool = False
    miss: bool = False


HIT, AF, HWE, NACK, MISS = (CacheEvent(), CacheEvent(tag_error=True), CacheEvent(tl_d_corrupt=True),
                           CacheEvent(mshr_nack=True), CacheEvent(miss=True))
PATTERNS = dict(clean=(HIT,HIT), head_af=(AF,HIT), tail_af=(HIT,AF), head_hwe=(HWE,HIT), tail_hwe=(HIT,HWE),
                head_af_tail_hwe=(AF,HWE), head_hwe_tail_af=(HWE,AF), head_af_tail_nack=(AF,NACK),
                head_hwe_tail_nack=(HWE,NACK), head_nack_tail_af=(NACK,AF), head_nack_tail_hwe=(NACK,HWE),
                head_nack_tail_miss=(NACK,MISS), head_miss_tail_nack=(MISS,NACK))


def exception(event):
    return int(event.tag_error)<<5 | int(event.tl_d_corrupt)<<19


def replay(event):
    if exception(event):return None
    return 5 if event.mshr_nack else 6 if event.miss else None


class S4Program:
    def __init__(self, env, lane, page, *, start_sq=0, start_lq=0, start_rob=8, uid_base=0):
        self.env,self.lane,self.page = env,lane,page
        self.start_sq,self.start_lq,self.start_rob=start_sq,start_lq,start_rob
        self.base = Inputs(pending=rob_pointer(start_rob),pending_next=rob_pointer(start_rob))
        self.store = StoreOwner(start_sq,rob_pointer(start_rob),0x90000+64*start_sq,0xC090000+64*start_sq,
                                value=0x8877665544332211^(start_sq<<16))
        va,pa = (0x45FFC,0xA145FFC) if page else (0x4503C,0xA14503C)
        self.blocker = cached_load(start_lq,rob_pointer(start_rob+2),start_sq+1,0x88000,0xA188000)
        self.target = cached_load(start_lq+1,rob_pointer(start_rob+3),start_sq+1,va,pa)
        self.loads = []
        self.sequence,self.sq_head,self.released=uid_base,start_sq,0
        self.s2 = False
        self.address = self.data = self.executed_store = self.store_done = False
        self.consumed = None
        self.last_packet = None
        self.cancelled = []

    async def cycle(self, **fields):
        packet=replace(self.base,attributes=(Attributes(),Attributes()),**fields)
        await self.env.cycle(packet)
        pre,post,t = self.env.pre_response,self.env.response,self.env.last_tick
        if self.s2:self.executed_store=True
        self.s2=any(a.valid and not a.tlb_miss for a in packet.addresses)
        for a in packet.addresses:
            if a.valid:
                assert not self.address and a.rob==self.store.rob
                self.address=True
        for d in packet.data:
            if d.valid:
                assert not self.data and d.sq==SqPtr.encode(self.start_sq)
                self.data=True
        for p in packet.loads:
            e=p.execution
            if not e.valid:continue
            s=next(s for s in reversed(self.loads) if not s["cancelled"] and s["load"].execution.uop.lq==e.uop.lq)
            assert s["load"].execution.uop.rob==e.uop.rob
            if e.replay_feedback:assert s["grant"]==e.slot
            if not e.need_replay and p.update_address:
                assert not s["sent"]
                s["sent"]=True
            s["last"]=p
        for bank in range(3):
            response=pre.replays[bank]
            if response.valid and packet.replay_ready[bank]:
                s=next(s for s in reversed(self.loads) if not s["cancelled"] and
                       s["load"].execution.uop.lq==QueuePtr(bool(response.lq_idx_flag),response.lq_idx_value))
                assert s["grant"] is None
                s["grant"]=response.replay_queue_idx
                assert s["grant"]%3==bank
                for bit in (23,19,15,7,6):assert response.exceptions>>bit&1==0
        for lane in range(2):
            actual_word=(pre.sbuffer_word_0,pre.sbuffer_word_1)[lane]
            if actual_word is not None and packet.sbuffer_ready[lane]:
                assert self.consumed is None and self.executed_store and self.data
                va,pa,mask,value=self.store.words()[0]
                self.env.expect_sbuffer_word(lane,word(vaddr=va,addr=pa,mask=mask,data=value,wline=0),
                                 "S4 surviving original Store actual bytes",before=True,data_mask=(1<<64)-1)
                self.consumed=t
        head=128*post.sq_deq_ptr.first+64*post.sq_deq_ptr.second+post.sq_deq_ptr.value
        if head!=self.sq_head%256:
            assert head==(self.start_sq+1)%256 and self.sq_head==self.start_sq and self.consumed+2==t
            self.sq_head,self.store_done=self.start_sq+1,True
        if post.lq_dequeue.valid:
            live=[s for s in self.loads if not s["cancelled"] and not s["complete"]]
            count=post.lq_dequeue.count
            assert 0<count<=len(live)
            for s in live[:count]:
                assert s["sent"]
                s["complete"]=True
                self.released+=1
        assert pre.uncache_request is None and pre.mmio_stout is None and pre.cmo_request is None

    async def dispatch(self, loads, *, store=False):
        ds=[Dispatch(True,2,self.store.rob,1,store_end=SqPtr.encode(self.start_sq+1))] if store else []
        if store:self.sequence+=1
        for load in loads:
            self.sequence+=1
            self.loads.append(dict(uid=self.sequence,load=load,sent=False,complete=False,cancelled=False,grant=None,last=None))
            ds.append(Dispatch(True,1,load.execution.uop.rob,1,load_start=load.execution.uop.lq))
        await self.cycle(dispatch=tuple(ds)+(Dispatch(),)*(8-len(ds)))

    async def split(self, load, pattern, *, feedback=False):
        lane=self.lane
        head,tail=pattern
        va,pa=load.execution.vaddr,load.paddr
        assert va%16==12 and load.execution.uop.operation==6
        tail_va=va//16*16+16
        # Noncontiguous PA belongs to the actual crossing-page request, not
        # every later same-slot replacement merely because this CASE used it.
        tail_pa=(0xB246000 if self.page and va%4096==4092 else pa//16*16+16)
        stimuli=dict(load=asdict(load),head=asdict(head),tail=asdict(tail),tail_VA=tail_va,tail_PA=tail_pa,
                     head_MSHR=3,tail_MSHR=9,head_TLB_id=2,tail_TLB_id=13,head_TLB_full=False,tail_TLB_full=True,head_gpaddr=0x201000000+pa,
                     tail_gpaddr=0x211000000+tail_pa,head_nonleaf=False,tail_nonleaf=True,tail_hyper=True,
                     CSR_cache_error_enable=True,EnableAccurateLoadError=False,feedback=feedback)
        self.env.emit("S4_external_cache_stimulus_before_S0",**stimuli)
        def lanes(value,empty):return tuple(value if n==lane else empty for n in range(3))
        def queries(event,addr,mask):
            u=load.execution.uop
            dv=event.tl_d_corrupt or not event.miss
            return (lanes(RarQuery(True,u.rob,u.lq,addr,dv,False),RarQuery()),
                    lanes(RawQuery(True,u.rob,u.sq,addr,mask,dv,u.rvc,u.ftq,u.offset,u.checkpoint),RawQuery()))
        await self.cycle(queries=lanes(Query(True,va,load.execution.uop.sq,3),Query()))
        await self.cycle(queries=lanes(Query(True,tail_va,load.execution.uop.sq,4),Query()),
                         translations=lanes(Translation(pa),Translation()))
        response=self.env.response.forward[lane]
        assert response.valid and not response.forward_mask
        assert not any((response.addr_invalid,response.data_invalid,response.forward_invalid,response.match_invalid))
        rar,raw=queries(head,pa,0xF000)
        await self.cycle(translations=lanes(Translation(tail_pa),Translation()),rar_queries=rar,raw_queries=raw)
        assert self.env.pre_response.rar_nuke[lane].req_ready and self.env.pre_response.raw_nuke[lane].req_ready
        assert not self.env.response.rar_nuke[lane].nuke
        hr,tr=replay(head),replay(tail)
        hx,tx=exception(head),exception(tail)
        hrev,trev=bool(hr is not None or hx),bool(tr is not None or tx)
        rar,raw=queries(tail,tail_pa,15)
        one=lanes(hrev,False)
        await self.cycle(rar_queries=rar,raw_queries=raw,rar_revoke_last=one,raw_revoke_last=one)
        assert self.env.pre_response.rar_nuke[lane].req_ready and self.env.pre_response.raw_nuke[lane].req_ready
        assert not self.env.response.rar_nuke[lane].nuke
        cause=hr if hr is not None else tr
        chosen=head if hr==6 else tail
        fault=hx if hx else tx
        writeback=bool(hx or hr is None and (tx or tr is None))
        s=next(s for s in reversed(self.loads) if not s["cancelled"] and s["load"].execution.uop.lq==load.execution.uop.lq)
        q=replace(load.execution,uop=replace(load.execution.uop,exceptions=fault),aligned_type=4,last_beat=bool(pa&64),
                  need_replay=cause is not None,causes=0 if cause is None else 1<<cause,unaligned_head=hr is not None,
                  replay_feedback=feedback,slot=s["grant"] if feedback else 0,mshr=3 if hr==6 else 9,handled=chosen.miss,
                  tlb_id=2 if hr is not None else 13,tlb_full=hr is None,special_eligible=cause in (3,5,6))
        packet=replace(load,execution=q,exceptions=fault,update_address=writeback,fullva=va if hx else tail_va,
                       gpaddr=stimuli["head_gpaddr"] if hx else stimuli["tail_gpaddr"],nonleaf=False if hx else True,hyper=True)
        one,two=lanes(trev or hrev,False),lanes(not hrev and trev,False)
        await self.cycle(loads=lanes(packet,Load()),rar_revoke_last=one,raw_revoke_last=one,rar_revoke_older=two,raw_revoke_older=two)
        self.last_packet=packet
        return packet

    async def grant(self, packet):
        if packet.execution.causes==1<<6:
            for _ in range(4):
                await self.cycle(refills=(Refill(True,9),Refill()))
                assert not any(item.valid for item in self.env.response.replays),"tail MSHR cannot wake original head miss"
            await self.cycle(refills=(Refill(True,3),Refill()))
        for _ in range(80):
            bank=next((b for b,item in enumerate(self.env.response.replays) if item.valid),None)
            if bank is not None:break
            await self.cycle()
        else:raise AssertionError("S4 original Replay never actually granted")
        await self.cycle(replay_ready=tuple(b==bank for b in range(3)))

    async def trap_and_reuse(self):
        assert self.last_packet.exceptions and self.last_packet.update_address
        target=next(s for s in self.loads if s["load"] is self.target)
        await self.cycle(redirect=Redirect(True,self.target.execution.uop.rob,True))
        target["cancelled"]=True
        self.cancelled.append(target)
        ptr=None
        for _ in range(60):
            await self.cycle()
            p=self.env.response
            if p.lq_redirect_ptr is not None:ptr=120*p.lq_redirect_ptr.flag+p.lq_redirect_ptr.value
            if ptr is not None and not p.lq_recover_stall and not p.sq_recover_stall:break
        assert ptr==(self.start_lq+1)%240
        for _ in range(4):await self.cycle()
        new=cached_load(self.start_lq+1,rob_pointer(self.start_rob+4),self.start_sq+1,0x4703C,0xA24703C)
        await self.dispatch([new])
        return new

    async def clean_aligned(self,load):
        lane=(self.lane+1)%3
        lanes=lambda x,e:tuple(x if n==lane else e for n in range(3))
        u=load.execution.uop
        await self.cycle(queries=lanes(Query(True,load.execution.vaddr,u.sq,3),Query()))
        await self.cycle(translations=lanes(Translation(load.paddr),Translation()))
        await self.cycle(rar_queries=lanes(RarQuery(True,u.rob,u.lq,load.paddr,True),RarQuery()),
                         raw_queries=lanes(RawQuery(True,u.rob,u.sq,load.paddr,255,True,u.rvc,u.ftq,u.offset,u.checkpoint),RawQuery()))
        await self.cycle(loads=lanes(replace(load,execution=replace(load.execution,aligned_type=3,last_beat=bool(load.paddr&64))),Load()))

    async def finish(self, final):
        addresses,data=[Address(),Address()],[Data(),Data()]
        addresses[self.lane%2],data[1-self.lane%2]=self.store.address(),self.store.data()
        await self.cycle(addresses=tuple(addresses),data=tuple(data))
        for _ in range(3):await self.cycle()
        await self.clean_aligned(self.blocker)
        if final is not self.target:await self.split(final,(HIT,HIT))
        self.base=replace(self.base,pending=rob_pointer(self.start_rob+5),pending_next=rob_pointer(self.start_rob+5),sbuffer_ready=(True,True))
        for _ in range(100):
            await self.cycle()
            if self.store_done and all(s["complete"] or s["cancelled"] for s in self.loads):break
        assert self.store_done and all(s["complete"] or s["cancelled"] for s in self.loads)
        for _ in range(12):await self.cycle()
        assert self.env.response.lq_empty and self.env.response.sq_empty and not self.env.response.replay_allocate
        for old in self.cancelled:assert any(s["uid"]>old["uid"] and s["complete"] and s["load"].execution.uop.lq.value==old["load"].execution.uop.lq.value for s in self.loads)
