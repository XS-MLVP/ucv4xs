"""Normal public RAW owners, full capacity, original rollback and refetch."""
from collections import deque
from dataclasses import replace
import hashlib
import json

from suites.memblock.lsq.forward.types import Query,Translation
from suites.memblock.lsq.load_queue.types import Inputs as LqInputs,Load
from suites.memblock.lsq.lsq_wrapper.types import Inputs as WrapperInputs,Dispatch as WrapperDispatch,Address,Data
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery,Store,FtqPtr,SqPtr
from suites.memblock.lsq.replay.types import Enqueue,Uop
from suites.memblock.lsq.vlq.types import Dispatch,QueuePtr,Redirect,RobPtr

ALL=(1<<64)-1


def lanes(value,lane,empty,count=3):return tuple(value if i==lane else empty for i in range(count))


def checkpoint(phase,index):
    if phase==0:return 0
    if phase==1:return ALL
    value=((index+1)*0x9E3779B97F4A7C15 ^ 0xA536D240B17E908F)&ALL
    return value if phase==2 else value^ALL


class RawOwners:
    def __init__(self,env,wrapper,target):
        self.env,self.wrapper,self.target=env,wrapper,target
        self.uid=self.head=self.tail=self.rob=self.sq=self.local=self.fires=self.dequeues=0
        self.queue=deque();self.current={};self.rows=[];self.expected_rollback=None;self.rollback=None
        self.permitted=False;self.store=None;self.ready=0;self.sent_store=False
        self.RAW_handshakes=self.capacity_nacks=0
        self.previous_pending_next=None;self.committing=False;self.commit_pairs=[]
        self.digest=hashlib.sha256()
        self.deq="io_toLsqEnqCtrl_lqDeq_" if wrapper else "io_lqDeq_"

    async def step(self,**fields):
        common=dict(pending=RobPtr.encode(self.rob),pending_next=RobPtr.encode(self.rob))
        if self.wrapper:
            packet=WrapperInputs(**dict(common,sbuffer_ready=(self.permitted,)*2,**fields))
        else:
            packet=LqInputs(**dict(common,address_ready=SqPtr.encode(self.ready),sq_empty=False,**fields))
        if self.previous_pending_next is not None:assert packet.pending==self.previous_pending_next
        pending=160*int(packet.pending.flag)+packet.pending.value
        pending_next=160*int(packet.pending_next.flag)+packet.pending_next.value
        delta=(pending_next-pending)%320
        assert packet.pending.former and packet.pending_next.former and delta<=8 and pending%8+delta<=8
        self.previous_pending_next=packet.pending_next
        await self.env.cycle(packet)
        pre,post,tick=self.env.pre_observed,self.env.observed,self.env.last_tick
        if self.committing:self.commit_pairs.append([tick,self.rob,self.rob+delta])
        for load in packet.loads:
            q=load.execution
            if q.valid:
                state=next(item for item in self.current.values() if item['load'].execution.uop==q.uop)
                assert state['written'] is None
                if not q.need_replay and load.update_address:state['written']=tick
                else:assert q.causes==1<<10 and not load.update_address
        if post[self.deq+'valid']:
            count=post[self.deq+'bits'];assert 0<count<=len(self.queue)
            for _ in range(count):
                state=self.queue.popleft()
                assert state['position']==self.head and state['written'] is not None and not state['local_complete']
                assert state['written']+4<=tick
                state['local_complete']=True;self.head+=1;self.local+=1
        for lane in range(2):
            prefix=f'io_nuke_rollback_{lane}_'
            if post[prefix+'valid']:
                expected=self.expected_rollback
                assert expected is not None and lane==expected['lane'] and tick==expected['tick']
                wanted=expected['fields'];actual={name:post[prefix+name] for name in wanted}
                assert actual==wanted,('original-RAW-owner',actual,wanted)
                assert self.rollback is None
                self.rollback=dict(actual_fields=actual,actual_tick=tick,store_lane=lane,original_UID=expected['uid'])
                self.expected_rollback=None
                u=self.current[expected['uid']]['load'].execution.uop;a=self.store
                train=dict(io_mdpTrain_valid=1,io_mdpTrain_bits_ftqIdx_value=u.ftq.value,
                    io_mdpTrain_bits_ftqOffset=u.offset,io_mdpTrain_bits_isRVC=int(u.rvc),
                    io_mdpTrain_bits_stFtqIdx_value=a['ftq'].value,io_mdpTrain_bits_stFtqOffset=a['offset'],
                    io_mdpTrain_bits_stIsRVC=int(a['rvc']))
                assert {name:post[name] for name in train}==train
        if self.wrapper:
            for lane in range(2):
                prefix=f'io_sbuffer_req_{lane}_'
                if pre[prefix+'valid'] and packet.sbuffer_ready[lane]:
                    assert self.store is not None and self.sent_store and self.fires==self.sq
                    s=self.store;expected=dict(bits_addr=s['pa'],bits_vaddr=s['va'],bits_mask=255,bits_wline=0)
                    assert {name:pre[prefix+name] for name in expected}==expected
                    assert pre[prefix+'bits_data']&ALL==s['data']
                    self.fires+=1;s['fire_tick']=tick
            if post['io_toLsqEnqCtrl_sqDeq_valid']:
                assert post['io_toLsqEnqCtrl_sqDeq_bits']==1 and self.fires==self.sq+1 and self.dequeues==self.sq
                assert self.store['fire_tick']+2==tick
                self.dequeues+=1
        assert not post['io_uncache_req_valid']
        self.digest.update(json.dumps([tick,self.head,self.tail,self.local,self.fires,self.dequeues,
            [post[f'io_nuke_rollback_{lane}_valid'] for lane in range(2)]]).encode())
        return post

    async def idle(self,count=1):
        for _ in range(count):await self.step()

    def make(self,rob,index,phase):
        self.uid+=1;pos=self.tail
        va=0x100000+phase*0x10000+index*64;pa=0x80100000+phase*0x10000+index*64
        u=Uop(rob=RobPtr.encode(rob),lq=QueuePtr.encode(pos),sq=SqPtr.encode(self.sq+1),
              operation=6,ftq=FtqPtr(bool(rob//256%2),rob//4%64),offset=2*(rob%4),rvc=False,
              checkpoint=checkpoint(phase,index))
        load=Load(Enqueue(True,u,vaddr=va,mask=255,aligned_type=3,last_beat=bool(pa&64)),
                  fullva=va,paddr=pa,update_address=True)
        state=dict(uid=self.uid,index=index,position=pos,load=load,written=None,local_complete=False,ROB_cancelled=False)
        self.current[self.uid]=state;return state

    async def dispatch(self,state):
        u=state['load'].execution.uop
        request=WrapperDispatch(True,1,u.rob,1,load_start=u.lq) if self.wrapper else Dispatch(True,u.rob,u.lq,1)
        empty=WrapperDispatch() if self.wrapper else Dispatch()
        assert state['position']==self.tail
        self.queue.append(state);self.tail+=1
        await self.step(dispatch=(request,)+(empty,)*7)

    async def pipeline(self,state,*,full=False,refetch=False):
        load=state['load'];q=load.execution;u=q.uop;lane=(state['index']+self.sq)%3
        await self.step(**({'queries':lanes(Query(True,q.vaddr,u.sq,3),lane,Query())} if self.wrapper else {}))
        await self.step(**({'translations':lanes(Translation(load.paddr),lane,Translation())} if self.wrapper else {}))
        if self.wrapper:
            prefix=f'io_forward_{lane}_s2Resp_'
            assert self.env.observed[prefix+'valid']==1
            same=refetch and state['index']==self.target
            for byte in range(16):
                valid=same and byte<8
                assert self.env.observed[prefix+f'bits_forwardMask_{byte}']==int(valid)
                if valid:assert self.env.observed[prefix+f'bits_forwardData_{byte}']==self.store['data']>>(8*byte)&255
            if refetch:
                for name in ('forwardInvalid','matchInvalid','addrInvalid_valid','dataInvalid_valid'):
                    assert not self.env.observed[prefix+'bits_'+name]
        raw=RawQuery(True,u.rob,u.sq,load.paddr,255,True,u.rvc,u.ftq,u.offset,u.checkpoint)
        rar=RarQuery(True,u.rob,u.lq,load.paddr,True)
        await self.step(raw_queries=lanes(raw,lane,RawQuery()),rar_queries=lanes(rar,lane,RarQuery()))
        pre,post=self.env.pre_observed,self.env.observed
        assert pre[f'io_ldu_rawNukeQuery_{lane}_req_ready']==int(not full)
        if not refetch:
            self.RAW_handshakes+=int(not full);self.capacity_nacks+=int(full)
        assert pre[f'io_ldu_rarNukeQuery_{lane}_req_ready']==1
        assert post[f'io_ldu_rarNukeQuery_{lane}_resp_bits_nuke']==0
        final=replace(load,execution=replace(q,need_replay=full,causes=1<<10 if full else 0),update_address=not full)
        revoke=tuple(full and n==lane for n in range(3))
        await self.step(loads=lanes(final,lane,Load()),rar_revoke_last=revoke,raw_revoke_last=revoke)

    async def recover(self,cutoff,cancelled):
        # Local LSQ release and architectural ROB cancellation are independent.
        for state in cancelled:state['ROB_cancelled']=True
        active=[state for state in cancelled if not state['local_complete']]
        assert len(active)==1 and list(self.queue)==active
        expected=self.tail-1
        self.queue.clear();self.tail=expected
        await self.step(redirect=Redirect(True,cutoff,True))
        lq_return=None;sq_return=None
        for age in range(60):
            await self.step();p=self.env.observed
            prefix='io_toLsqEnqCtrl_lqRedirectPtr_' if self.wrapper else 'io_lqRedirect_'
            if p[prefix+'valid']:lq_return=120*p[prefix+'bits_flag']+p[prefix+'bits_value']
            if self.wrapper and p['io_toLsqEnqCtrl_sqRedirectPtr_valid']:
                sq_return=128*p['io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag']+64*p['io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag']+p['io_toLsqEnqCtrl_sqRedirectPtr_bits_value']
            stall=p['io_toLsqEnqCtrl_lqRecoverStall' if self.wrapper else 'io_lqRecoverStall']
            if age>=8 and lq_return is not None and not stall and (not self.wrapper or sq_return is not None and not p['io_toLsqEnqCtrl_sqRecoverStall']):break
        assert lq_return==expected%240 and self.head==expected
        if self.wrapper:assert sq_return==(self.sq+1)%256
        return dict(actual_LQ_tail=lq_return,actual_SQ_tail=sq_return,cancelled_UIDs=[s['uid'] for s in cancelled],
                    locally_completed_then_ROB_cancelled=[s['uid'] for s in cancelled if s['local_complete']],
                    active_uncompleted_cancelled=[s['uid'] for s in active])

    async def commit_to(self,end):
        # Fixed ROB uses one CommitWidth=8 line at a time. Present next one
        # sample before pending, with a legal commit-stall edge between lines.
        self.permitted=True;self.committing=True;self.commit_pairs=[]
        try:
            while self.rob<end:
                next_head=min(end,(self.rob//8+1)*8)
                await self.step(pending_next=RobPtr.encode(next_head))
                self.rob=next_head
                await self.step()
        finally:self.committing=False

    async def program(self,phase):
        base=self.rob;self.ready=self.sq;self.permitted=False;self.sent_store=False
        before_handshakes,before_nacks=self.RAW_handshakes,self.capacity_nacks
        self.uid+=1;store_uid=self.uid
        va=0x100000+phase*0x10000+self.target*64;pa=0x80100000+phase*0x10000+self.target*64
        self.store=dict(uid=store_uid,rob=RobPtr.encode(base),va=va,pa=pa,data=0x8877665544332211^(phase*0x1111111111111111),
                        ftq=FtqPtr(bool(base//256%2),base//4%64),offset=2*(base%4),rvc=False)
        if self.wrapper:
            request=WrapperDispatch(True,2,self.store['rob'],1,store_end=SqPtr.encode(self.sq+1))
            await self.step(dispatch=(request,)+(WrapperDispatch(),)*7)
            await self.step(data=lanes(Data(True,SqPtr.encode(self.sq),6,self.store['data']),phase%2,Data(),2))
        original=[]
        for index in range(57):
            state=self.make(base+1+index,index,phase);original.append(state)
            await self.dispatch(state);await self.pipeline(state,full=index==56)
        await self.idle(6)
        assert all(state['local_complete'] for state in original[:56])
        assert not original[56]['local_complete'] and list(self.queue)==[original[56]]
        assert not any(self.env.observed[f'io_replay_{b}_valid'] for b in range(3))
        target=original[self.target];u=target['load'].execution.uop;s=self.store;lane=self.target%2
        fields=dict(bits_robIdx_flag=int(u.rob.flag),bits_robIdx_value=u.rob.value,bits_robIdx_isFormer=int(u.rob.former),
            bits_ftqIdx_flag=int(u.ftq.flag),bits_ftqIdx_value=u.ftq.value,bits_ftqOffset=u.offset,bits_isRVC=int(u.rvc),
            bits_debug_runahead_checkpoint_id=u.checkpoint,bits_stFtqIdx_flag=int(s['ftq'].flag),
            bits_stFtqIdx_value=s['ftq'].value,bits_stFtqOffset=s['offset'],bits_stIsRVC=int(s['rvc']))
        self.rollback=None
        sta_tick=self.env.last_tick+2
        self.expected_rollback=dict(lane=lane,tick=self.env.last_tick+6,fields=fields,uid=target['uid'])
        if self.wrapper:
            sta=Address(True,self.sq%64,6,va,pa,3,rob=s['rob'],ftq=s['ftq'],ftq_offset=s['offset'],rvc=s['rvc'],mask=255)
            await self.step(addresses=lanes(sta,lane,Address(),2));self.sent_store=True
        else:
            sta=Store(True,s['rob'],pa,255,ftq_flag=s['ftq'].flag,ftq_value=s['ftq'].value,ftq_offset=s['offset'],is_rvc=s['rvc'])
            await self.step(stores=lanes(sta,lane,Store(),2))
        await self.idle(2)
        assert self.rollback is not None and self.expected_rollback is None
        # For isolated LQ, this explicit external SQ feedback is supplied only
        # after the original STA and its fixed N+2 observation. Wrapper has no
        # writable substitute: its real SQ produces the ready pointer itself.
        self.ready=self.sq+1
        recovery=await self.recover(u.rob,original[self.target:])
        refetched=[]
        for index in range(self.target,57):
            new=self.make(base+1+index,index,phase);refetched.append(new)
            await self.dispatch(new);await self.pipeline(new,refetch=True)
        await self.idle(6)
        assert all(state['local_complete'] for state in refetched) and not self.queue and self.head==self.tail
        await self.commit_to(base+58)
        if self.wrapper:
            for _ in range(80):
                await self.step()
                if self.dequeues==self.sq+1 and self.env.observed['io_sqEmpty']:break
            assert self.fires==self.dequeues==self.sq+1 and self.env.observed['io_sqEmpty']
        else:await self.idle(8)
        assert self.env.observed['io_lqEmpty'] and not self.env.observed['io_replayAllocate']
        assert not any(self.env.observed[f'io_replay_{b}_valid'] for b in range(3))
        self.rows.append(dict(phase=phase,target=self.target,store_UID=store_uid,store_ROB=base,
            original_UIDs=[state['uid'] for state in original],original_RAW_accepted_UIDs=[state['uid'] for state in original[:56]],
            original_overflow_UID=original[56]['uid'],original_checkpoint=u.checkpoint,original_target_UID=target['uid'],
            original_target_position=target['position'],original_overflow_position=original[56]['position'],
            actual_original_RAW_handshakes=self.RAW_handshakes-before_handshakes,actual_capacity_nacks=self.capacity_nacks-before_nacks,
            actual_STA_tick=sta_tick,rollback=self.rollback,recovery=recovery,
            refetched_UIDs=[state['uid'] for state in refetched],actual_final_LQ_head=self.head,
            refetch_first_position=refetched[0]['position'],refetch_first_UID=refetched[0]['uid'],
            source_projected_ROB_commit_pairs=self.commit_pairs,actual_final_ROB_pending=self.rob,
            original_Store_Sbuffer_completed=self.wrapper,actual_sbuffer_fires=self.fires if self.wrapper else None,
            original_Store_bytes_forwarded_to_new_target=self.wrapper,original_Store_PA=pa,original_Store_data=s['data'],
            max_ROB_program_items=58,unexecuted_STA_peak=1,reset_shortcuts=0))
        self.sq+=1


async def trace(env,path,target,*,wrapper=False):
    actor=RawOwners(env,wrapper,target)
    passed=False;error=None
    try:
        for phase in range(4):await actor.program(phase)
        assert len(actor.rows)==4
        if wrapper:env.prove('LSQ-RAW.conflict','LSQ-RAW.train','LSQ-RECOVER.partial','LSQ-RECOVER.reuse')
        else:env.prove('LQ-RAW.all_slots','LQ-RAW.train')
        passed=True
    except BaseException as exc:
        error=repr(exc);raise
    finally:
        path.write_text(json.dumps(dict(format='lsq-load-RAW-owner-witness-v1',dut='lsq_wrapper' if wrapper else 'load_queue',
            target=target,passed=passed,error=error,rows=actor.rows,checked_public_stream_SHA256=actor.digest.hexdigest(),
            local_Load_completions=actor.local,actual_Store_Sbuffer_fires=actor.fires,
            actual_Store_dequeues=actor.dequeues,
            last_public_terminal=dict(tick=env.last_tick,LQ_head=actor.head,LQ_tail=actor.tail,
                LQ_empty=env.observed['io_lqEmpty'],SQ_empty=env.observed['io_sqEmpty'] if wrapper else None,
                last_actual_rollback=actor.rollback),
            scope='fixed-source aligned-cacheable boundary producer; not native upstream LDU/TLB/Cache/ROB. Local LSQ release is not architectural commit. No mid-program reset or private-state stimulus.'),indent=2)+'\n')
