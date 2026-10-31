"""Public original-UID response producer; no model/private-state decisions."""
from dataclasses import replace
import hashlib
import json

from suites.memblock.lsq.forward.types import Query as ForwardQuery,Translation
from suites.memblock.lsq.load_queue.types import Inputs as LqInputs,Load,Bypass,Bus as LqBus
from suites.memblock.lsq.lsq_wrapper.types import Inputs as WrapperInputs,Dispatch as WrapperDispatch,Bus as WrapperBus
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery,FtqPtr,SqPtr
from suites.memblock.lsq.replay.types import Enqueue,Uop
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.vlq.types import Dispatch,QueuePtr,Redirect,RobPtr

ALL=(1<<64)-1
PROFILES=((0,False,False),(ALL,True,False),(0,False,True),(ALL,True,True))


def lane_tuple(value,lane,empty):
    return tuple(value if index==lane else empty for index in range(3))


def save(path,dut,rows,stream,**totals):
    path.write_text(json.dumps(dict(format="lsq-load-response-payload-witness-v1",dut=dut,rows=rows,
        checked_public_stream_SHA256=stream.hexdigest(),**totals),indent=2)+"\n")


def check(pins,expected,label):
    difference={name:[pins[name],value] for name,value in expected.items() if pins[name]!=value}
    assert not difference,(label,difference)


async def uncache_trace(env,path):
    from suites.memblock.lsq.load_uncache.sequences import red
    rows,stream,rob=[],hashlib.sha256(),0
    for nc in (True,False):
        for generation,(data,error,nderr) in enumerate(PROFILES):
            visited=set()
            for index in range(16):
                uid=len(rows)+1;position=uid-1;lane=position%3
                va,pa=0x100000+position*64,0x80000000+position*64
                request=env.request(nc=nc,lq=position,rob=rob,paddr=pa,vaddr=va,tag=uid)
                request=replace(request,entry=replace(request.entry,fullva=va,gpaddr=0,mask=255,
                    hyper=False,nonleaf=False,memory_backed=True),need_replay=True,uncache_cause=True)
                await env.enqueue({lane:request},pending=request.entry.rob)
                for _ in range(80):
                    if env.observed["io_uncache_req_valid"]:break
                    await env.cycle()
                assert env.observed["io_uncache_req_valid"]
                mid=env.observed["io_uncache_req_bits_id"]
                assert 0<=mid<16 and mid not in visited
                visited.add(mid)
                await env.take_bus(request,mid)
                sid=(uid-1)%16
                await env.bind(mid,sid);await env.respond(sid,data,error=error,nderr=nderr)
                await env.wait_wakeup(request)
                await env.consume(request,data,lane=lane,error=error,nderr=nderr)
                assert uid in env.completed
                if error or nderr:
                    await env.cycle(red(request.entry.rob,self_flush=True));await env.idle(8)
                else:rob+=1
                row=dict(uid=uid,position=position,nc=nc,generation=generation,mid=mid,sid=sid,lane=lane,
                    data=data,error=error,nderr=nderr,actual_s1_PA_checked=True,actual_s2_data_checked=True,
                    actual_exception_metadata_checked=True,external_fault_redirect=bool(error or nderr),
                    local_completion=True,architectural_retirement_claimed=not(error or nderr))
                rows.append(row);add_digest(stream,row)
            assert visited==set(range(16))
    assert len(rows)==len(env.completed)==128
    env.prove("LQU-BYPASS.payload_pool")
    save(path,"load_queue_uncache",rows,stream,local_UID_completions=128,clean_UID_completions=32,requests=128,acks=128,responses=128,
         fault_local_completions=96,external_fault_redirects=96,resets_between_profiles=0,
         VLQ_Replay_S3_claimed=False,Backend_trap_implementation_claimed=False)


class ParentProducer:
    def __init__(self,env,wrapper):
        self.env,self.wrapper=env,wrapper
        self.stream=hashlib.sha256()
        self.rob=self.position=self.head=self.requests=self.acks=self.responses=self.grants=self.feedbacks=0
        self.nc=True
        self.current=self.mid=self.sid=self.slot=self.s3_tick=None
        self.exception_prefix="io_ldExceptionInfo_" if wrapper else "io_exceptionInfo_"
        self.deq_prefix="io_toLsqEnqCtrl_lqDeq_" if wrapper else "io_lqDeq_"

    async def step(self,**fields):
        common=dict(pending=RobPtr.encode(self.rob),pending_next=RobPtr.encode(self.rob))
        if self.wrapper:
            packet=WrapperInputs(**dict(common,**fields))
        else:
            packet=LqInputs(**dict(common,sq_empty=True,**fields))
        await self.env.cycle(packet)
        pre,post,tick=self.env.pre_observed,self.env.observed,self.env.last_tick
        load=self.current
        if pre["io_uncache_req_valid"] and packet.bus.ready:
            assert load is not None and self.mid is None
            expected=dict(cmd=0,addr=load.paddr,vaddr=load.execution.vaddr,mask=255,nc=int(self.nc),memBackTypeMM=1,
                robIdx_flag=int(load.execution.uop.rob.flag),robIdx_value=load.execution.uop.rob.value,robIdx_isFormer=1)
            check(pre,{"io_uncache_req_bits_"+key:value for key,value in expected.items()},"original-response-pool-bus-owner")
            self.mid=pre["io_uncache_req_bits_id"];self.requests+=1
        if packet.bus.ack:
            assert self.mid==packet.bus.mid and self.sid is None
            self.sid=packet.bus.sid;self.acks+=1
        if packet.bus.response:
            assert self.sid==packet.bus.response_id
            self.responses+=1
        for bank in range(3):
            prefix=f"io_replay_{bank}_"
            if pre[prefix+"valid"] and packet.replay_ready[bank]:
                assert load is not None and self.slot is None
                q=load.execution.uop
                check(pre,{prefix+"bits_uop_lqIdx_flag":int(q.lq.flag),prefix+"bits_uop_lqIdx_value":q.lq.value,
                           prefix+"bits_uop_robIdx_value":q.rob.value,prefix+"bits_uop_robIdx_flag":int(q.rob.flag)},"original-response-pool-Replay-grant")
                self.slot=pre[prefix+"bits_replayQueueIdx"]
                assert self.slot%3==bank and self.slot<120
                self.grants+=1
        for item in packet.loads:
            if item.execution.valid and item.execution.replay_feedback:
                assert self.slot is not None and item.execution.slot==self.slot
                self.feedbacks+=1
                assert not item.execution.need_replay and item.update_address
                self.s3_tick=tick
        if post[self.deq_prefix+"valid"]:
            assert post[self.deq_prefix+"bits"]==1 and self.s3_tick is not None
            assert self.s3_tick+4<=tick and self.head==self.position
            self.head+=1
        if self.wrapper:
            assert post["io_sqEmpty"] and not post["io_toLsqEnqCtrl_sqDeq_valid"]
        add_digest(self.stream,[tick,int(pre["io_uncache_req_valid"]),self.requests,self.acks,self.responses,
                               self.grants,self.feedbacks,self.head,self.s3_tick])
        return post

    def bus(self,**fields):
        return WrapperBus(outstanding=self.nc,**fields) if self.wrapper else LqBus(**fields)

    async def pipeline(self,*,replay=False,error=False,nderr=False):
        load=self.current;q=load.execution;u=q.uop;lane=self.position%3
        fields={}
        if self.wrapper:
            fields["queries"]=lane_tuple(ForwardQuery(True,q.vaddr,u.sq,3),lane,ForwardQuery())
        if replay:
            fields["bypass"]=lane_tuple(Bypass(True,u.lq,self.nc,not self.nc),lane,Bypass())
        await self.step(**fields)
        prefix=f"io_bypass_{lane}_";exc=self.exception_prefix
        if replay:
            check(self.env.observed,{prefix+"s1Resp_valid":1,prefix+"s1Resp_bits_paddr":load.paddr,
                exc+"valid":1,exc+"bits_vaddr":load.fullva,exc+"bits_gpaddr":0,
                exc+"bits_robIdx_value":u.rob.value,exc+"bits_robIdx_flag":int(u.rob.flag),
                exc+"bits_robIdx_isFormer":1,exc+"bits_exceptionVec_19":int(error),exc+"bits_exceptionVec_5":int(nderr)},"original-response-pool-s1-PA-exception")
            self.s1_evidence={key:value for key,value in self.env.observed.items()
                if key==prefix+"s1Resp_valid" or key==prefix+"s1Resp_bits_paddr" or key==exc+"valid"
                or key.startswith(exc+"bits_")}
        await self.step(**({"translations":lane_tuple(Translation(load.paddr),lane,Translation())} if self.wrapper else {}))
        if replay:
            check(self.env.observed,{prefix+"s2Resp_valid":1,prefix+"s2Resp_bits_data":self.data*((1<<64)+1),
                prefix+"s2Resp_bits_derr":int(error),prefix+"s2Resp_bits_nderr":int(nderr)},"original-response-pool-s2-all-bits")
            self.s2_evidence={prefix+key:self.env.observed[prefix+key] for key in
                ("s2Resp_valid","s2Resp_bits_data","s2Resp_bits_derr","s2Resp_bits_nderr")}
        query=not replay or self.nc
        fields={}
        if query:
            fields=dict(rar_queries=lane_tuple(RarQuery(True,u.rob,u.lq,load.paddr,replay,self.nc and replay),lane,RarQuery()),
                raw_queries=lane_tuple(RawQuery(True,u.rob,u.sq,load.paddr,255,replay,u.rvc,u.ftq,u.offset,u.checkpoint),lane,RawQuery()))
        await self.step(**fields)
        if query:
            assert self.env.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
            assert self.env.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
            assert not self.env.observed[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        exceptions=(int(error)<<19|int(nderr)<<5) if replay else 0
        packet=replace(load,execution=replace(q,uop=replace(u,exceptions=exceptions),need_replay=not replay,
            causes=0 if replay else 1,replay_feedback=replay,slot=self.slot if replay else 0,
            aligned_type=3,last_beat=bool(load.paddr&64)),update_address=replay,exceptions=exceptions)
        revoke=not replay or bool(exceptions)
        await self.step(loads=lane_tuple(packet,lane,Load()),rar_revoke_last=tuple(revoke and i==lane for i in range(3)),
                        raw_revoke_last=tuple(revoke and i==lane for i in range(3)))
        written=dict(tick=self.env.last_tick,lane=lane,update_address=packet.update_address,
            need_replay=packet.execution.need_replay,causes=packet.execution.causes,
            load_exceptions=packet.exceptions,uop_exceptions=packet.execution.uop.exceptions,
            aligned_type=packet.execution.aligned_type,last_beat=packet.execution.last_beat,
            replay_feedback=packet.execution.replay_feedback,slot=packet.execution.slot)
        if replay:self.final_S3=written
        else:self.first_S3=written

    async def fault_redirect(self):
        await self.step(redirect=Redirect(True,RobPtr.encode(self.rob),True))
        target=None;sq_target=None
        for age in range(40):
            await self.step()
            pins=self.env.observed
            prefix="io_toLsqEnqCtrl_lqRedirectPtr_" if self.wrapper else "io_lqRedirect_"
            if pins[prefix+"valid"]:
                target=QueuePtr(bool(pins[prefix+"bits_flag"]),pins[prefix+"bits_value"])
            if self.wrapper and pins["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                sq_target=128*pins["io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag"]+64*pins["io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag"]+pins["io_toLsqEnqCtrl_sqRedirectPtr_bits_value"]
            stalled=pins["io_toLsqEnqCtrl_lqRecoverStall" if self.wrapper else "io_lqRecoverStall"]
            if age>=8 and target is not None and not stalled and (not self.wrapper or sq_target==0 and not pins["io_toLsqEnqCtrl_sqRecoverStall"]):break
        assert target==QueuePtr.encode(self.position+1)


async def parent_trace(env,path,*,wrapper=False):
    producer=ParentProducer(env,wrapper);rows=[]
    for nc in (True,False):
        producer.nc=nc
        for generation,(data,error,nderr) in enumerate(PROFILES):
            visited=set()
            for index in range(16):
                pos=producer.position;uid=pos+1;lane=pos%3
                va=0x100000+pos*64;pa=0x80000000+pos*64
                u=Uop(rob=RobPtr.encode(producer.rob),lq=QueuePtr.encode(pos),sq=SqPtr(),operation=6,
                      ftq=FtqPtr(False,pos%64),offset=pos%32,rvc=False,checkpoint=0x9876000000000000|uid)
                load=Load(Enqueue(True,u,vaddr=va,mask=255,nc=nc,aligned_type=3,last_beat=bool(pa&64),
                                  need_replay=True,causes=1),fullva=va,paddr=pa,mmio=not nc,update_address=False)
                producer.current=load;producer.mid=producer.sid=producer.slot=producer.s3_tick=None;producer.data=data
                request=WrapperDispatch(True,1,u.rob,1,load_start=u.lq) if wrapper else Dispatch(True,u.rob,u.lq,1)
                empty=WrapperDispatch() if wrapper else Dispatch()
                await producer.step(dispatch=(request,)+(empty,)*7)
                await producer.pipeline()
                for _ in range(80):
                    if env.observed["io_uncache_req_valid"]:break
                    await producer.step()
                assert env.observed["io_uncache_req_valid"] and producer.head==pos
                await producer.step(bus=producer.bus(ready=True))
                mid=producer.mid;sid=pos%16
                assert mid is not None and 0<=mid<16 and mid not in visited
                visited.add(mid)
                await producer.step(bus=producer.bus(ack=True,mid=mid,sid=sid))
                await producer.step(bus=producer.bus(response=True,response_id=sid,data=data,error=error,nderr=nderr))
                for _ in range(80):
                    bank=next((b for b in range(3) if env.observed[f"io_replay_{b}_valid"]),None)
                    if bank is not None:break
                    await producer.step()
                assert bank is not None
                await producer.step(replay_ready=tuple(b==bank for b in range(3)))
                assert producer.slot is not None and producer.head==pos
                await producer.pipeline(replay=True,error=error,nderr=nderr)
                for _ in range(80):
                    await producer.step()
                    if producer.head==pos+1:break
                assert producer.head==pos+1
                for _ in range(4):await producer.step()
                if error or nderr:await producer.fault_redirect()
                else:producer.rob+=1
                row=dict(uid=uid,position=pos,nc=nc,generation=generation,mid=mid,sid=sid,lane=lane,
                    data=data,error=error,nderr=nderr,actual_s1_PA_checked=True,actual_s2_data_checked=True,
                    actual_exception_metadata_checked=True,replay_slot=producer.slot,S3_update_first=False,
                    S3_update_final=True,S3_exceptions=int(error)<<19|int(nderr)<<5,
                    actual_LQ_head=producer.head,local_completion=True,external_fault_redirect=bool(error or nderr),
                    observed_s1=producer.s1_evidence,observed_s2=producer.s2_evidence,
                    actual_driven_first_S3=producer.first_S3,actual_driven_final_S3=producer.final_S3,
                    architectural_retirement_claimed=not(error or nderr))
                rows.append(row);add_digest(producer.stream,row)
                producer.position+=1
            assert visited==set(range(16))
    assert producer.head==producer.requests==producer.acks==producer.responses==producer.grants==producer.feedbacks==128
    assert env.observed["io_lqEmpty"] and not env.observed["io_replayAllocate"] and not env.observed["io_uncache_req_valid"]
    if wrapper:env.prove("LSQ-BUS.load_only","LSQ-EXCEPTION.load_clean","LSQ-EXCEPTION.load_fault")
    else:env.prove("LQ-UNCACHE.payload_pool")
    save(path,"lsq_wrapper" if wrapper else "load_queue",rows,producer.stream,local_UID_completions=128,clean_UID_completions=32,
         requests=128,acks=128,responses=128,actual_Replay_grants=128,actual_slot_feedbacks=128,
         fault_local_completions=96,external_fault_redirects=96,resets_between_profiles=0,
         Backend_trap_implementation_claimed=False,store_mixed_acceptance_claimed=False)
