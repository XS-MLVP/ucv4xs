"""External dispatch/LDU actor: no model state is used for stimulus or done."""
from dataclasses import asdict, dataclass, replace
import json

from lsqverify.replay.types import Enqueue, Uop
from lsqverify.raw.types import FtqPtr, SqPtr
from lsqverify.vlq.types import Dispatch, QueuePtr, RobPtr
from .types import Inputs, Load


@dataclass
class Owner:
    uid: int
    position: int
    rob: RobPtr
    dispatch_lane: int
    load: Load
    completed_tick: object = None
    feedback_slot: object = None


class LoadActor:
    def __init__(self, env):
        self.env = env
        self.head = self.tail = self.sequence = self.rob_sequence = 0
        self.live, self.all, self.completed, self.issued = {}, {}, set(), {}

    def emit(self, event, **fields):
        self.env.actor_journal.write(json.dumps(dict(event=event, nodeid=self.env.nodeid, tick=self.env.last_tick, **fields)) + "\n")

    def make_load(self, position, rob, uid):
        u = Uop(rob=rob, lq=QueuePtr.encode(position), sq=SqPtr.encode(10), ftq=FtqPtr(bool(uid & 64), uid % 64),
                offset=uid % 32, rvc=bool(uid & 1), checkpoint=0x9876000000000000 | uid, operation=6, destination=uid % 256)
        return Load(Enqueue(True, u, vaddr=0x100000 + uid * 64, mask=0xFF), fullva=0xABC0000000000000 | uid,
                    paddr=0x80000000 + uid * 64, gpaddr=(1 << 55) | uid, update_address=True)

    async def dispatch(self, flows=(1,), *, lanes=None, configure=None):
        lanes = tuple(range(len(flows))) if lanes is None else tuple(lanes)
        assert len(lanes) == len(flows) and tuple(sorted(set(lanes))) == lanes and self.tail - self.head + sum(flows) <= 120
        dispatch, owners = [Dispatch()] * 8, []
        position = self.tail
        for lane, count in zip(lanes, flows, strict=True):
            rob = RobPtr.encode(self.rob_sequence)
            self.rob_sequence += 1
            dispatch[lane] = Dispatch(True, rob, QueuePtr.encode(position), count)
            for offset in range(count):
                self.sequence += 1
                load = self.make_load(position + offset, rob, self.sequence)
                if configure:
                    load = configure(load)
                owners.append(Owner(self.sequence, position + offset, rob, lane, load))
            position += count
        await self.step(Inputs(dispatch=tuple(dispatch)), new_owners=owners)
        return [o.uid for o in owners]

    def owner(self, uid):
        return self.all[uid]

    async def execute(self, uids, *, lanes=None, controls=None):
        lanes = tuple(range(len(uids))) if lanes is None else tuple(lanes)
        loads = [Load()] * 3
        for lane, uid in zip(lanes, uids, strict=True):
            owner = self.all[uid]
            assert owner.position in self.live and owner.completed_tick is None
            loads[lane] = owner.load
        return await self.step(replace(controls or Inputs(), loads=tuple(loads)))

    async def feedback(self, uids, *, controls=None, need_replay=False, causes=0):
        loads = [Load()] * 3
        for lane, uid in enumerate(uids):
            owner = self.all[uid]
            assert uid in self.issued
            loads[lane] = replace(owner.load, execution=replace(owner.load.execution, valid=True, replay_feedback=True,
                                  slot=self.issued[uid], need_replay=need_replay, causes=causes), update_address=not need_replay)
        return await self.step(replace(controls or Inputs(), loads=tuple(loads)))

    async def step(self, inp=None, *, new_owners=()):
        inp = inp or Inputs()
        await self.env.cycle(inp)
        pre, post, tick = self.env.pre_observed, self.env.observed, self.env.last_tick
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and inp.replay_ready[bank]:
                encoded_lq = QueuePtr(bool(pre[p + "bits_uop_lqIdx_flag"]), pre[p + "bits_uop_lqIdx_value"])
                owner = next(o for o in self.live.values() if QueuePtr.encode(o.position) == encoded_lq)
                assert owner.uid not in self.issued and owner.completed_tick is None
                assert (pre[p + "bits_uop_robIdx_flag"], pre[p + "bits_uop_robIdx_value"], pre[p + "bits_uop_robIdx_isFormer"]) == (int(owner.rob.flag), owner.rob.value, int(owner.rob.former))
                assert pre[p + "bits_vaddr"] == owner.load.execution.vaddr
                slot = pre[p + "bits_replayQueueIdx"]
                assert slot % 3 == bank and slot < 120 and slot not in self.issued.values()
                self.issued[owner.uid] = slot
                owner.feedback_slot = slot
                self.emit("replay_fire", uid=owner.uid, slot=slot, bank=bank)
        for load in inp.loads:
            req = load.execution
            if not req.valid:
                continue
            owner = next(o for o in self.live.values() if QueuePtr.encode(o.position) == req.uop.lq)
            assert owner.rob == req.uop.rob and owner.completed_tick is None
            if req.replay_feedback:
                assert self.issued.pop(owner.uid) == req.slot
            if not req.need_replay and load.update_address:
                owner.completed_tick = tick
            self.emit("execute", uid=owner.uid, replay=req.replay_feedback, need_replay=req.need_replay,
                      update_address=load.update_address, feedback_slot=req.slot, load=asdict(load))
        if post["io_lqDeq_valid"]:
            count = post["io_lqDeq_bits"]
            assert 1 <= count <= 8
            for position in range(self.head, self.head + count):
                owner = self.live[position]
                assert owner.completed_tick is not None and owner.completed_tick + 4 <= tick and owner.uid not in self.completed
                self.completed.add(owner.uid)
                del self.live[position]
                self.emit("complete", uid=owner.uid, position=position, completed_input_tick=owner.completed_tick)
            self.head += count
        for owner in new_owners:
            assert owner.position == self.tail and owner.position not in self.live
            self.live[owner.position] = self.all[owner.uid] = owner
            self.tail += 1
            self.emit("allocate", owner=asdict(owner))
        assert 0 <= self.tail - self.head <= 120
        return post

    async def drain(self, limit=600, *, controls=None):
        base = replace(controls or Inputs(), replay_ready=(True,) * 3)
        for _ in range(limit):
            feed = list(self.issued)[:3]
            if feed:
                await self.feedback(feed, controls=base)
            else:
                incomplete = [o.uid for o in self.live.values() if o.completed_tick is None and not o.load.execution.need_replay][:3]
                if incomplete:
                    await self.execute(incomplete, controls=base)
                else:
                    await self.step(base)
            if not self.live and not self.issued:
                for _ in range(6):
                    await self.step(base)
                assert self.env.observed["io_lqEmpty"] and not self.env.observed["io_replayAllocate"] and not self.env.observed["io_uncache_req_valid"]
                return
        raise AssertionError("external LoadQueue UIDs/feedback failed fair drain")

    def checked(self, names, uids):
        assert set(uids) <= self.completed
        self.env.prove(*names)
        self.emit("checked", names=names, uids=uids, completed=sorted(self.completed))
