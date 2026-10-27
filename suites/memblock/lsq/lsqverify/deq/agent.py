"""External PSQ/ROB and fair bus actors, all decisions from public history.

The real DUT still contains its real EnterSbufferQueue. This actor supplies
only the external rdata/deq windows, permissions and response handshakes.
"""
from dataclasses import asdict, dataclass, replace
import json

from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr
from .types import DeqControl, Inputs, SecondPage, Store


@dataclass
class Owner:
    uid: int
    position: int
    store: Store
    rob: RobPtr
    second_page: object = None
    finished: bool = False


class PsqAgent:
    def __init__(self, env, *, base=0):
        self.env = env
        self.head = self.read = self.tail = base
        self.sequence = 0
        self.owners, self.parts = {}, {}
        self.completed, self.aborted = set(), set()
        self.pending = None
        self.history = []
        self.emit("start", base=base)

    def emit(self, event, **fields):
        self.env.agent_journal.write(json.dumps({"nodeid": self.env.nodeid, "event": event, **fields}) + "\n")

    def add(self, store, *, rob=None, second_page=None):
        assert self.tail - self.head < 64
        assert store.memory_type in (0, 1, 2, 5, 7)
        assert not store.inactive or not (store.data_valid or store.address_valid)
        self.sequence += 1
        owner = Owner(self.sequence, self.tail, store, rob or RobPtr.encode(self.sequence % 320), second_page)
        self.owners[self.tail] = owner
        self.parts[owner.uid] = set()
        self.tail += 1
        self.emit("allocate", owner=asdict(owner))
        return owner.uid

    def inputs(self, **controls):
        stores, deq = [], []
        for lane in range(2):
            owner = self.owners.get(self.read + lane)
            store = owner.store if owner else Store()
            # Actual PSQ/VSQ can commit the current ROB-head special while
            # older retired normal stores are still stalled in dataQueue.
            # Do not manufacture a read==deq restriction absent from that
            # parent: it hid zero-write ownership and finish-order failures.
            stores.append(store)
            owner = self.owners.get(self.head + lane)
            deq.append(DeqControl(owner.store.inactive, owner.store.committed, owner.finished) if owner else DeqControl())
        owner = self.owners.get(self.read)
        page = SecondPage(True, owner.second_page, SqPtr.encode(owner.position)) if owner and owner.second_page is not None else SecondPage()
        inp = Inputs(tuple(stores), tuple(deq), (True, True), SqPtr.encode(self.read), (SqPtr.encode(self.head), SqPtr.encode(self.head + 1)),
                     owner.rob if owner else RobPtr(), self.tail - self.head, uncache_ready=True, cache_ready=True, writeback_ready=True,
                     second_page=page)
        if self.pending:
            kind, _, _ = self.pending
            inp = replace(inp, **({"cache_response": True} if kind == "cache" else {"uncache_ack_valid": True} if kind == "nc" else {"uncache_response": True}))
        return replace(inp, **controls)

    async def step(self, **controls):
        inp = self.inputs(**controls)
        old_head, old_read = self.head, self.read
        change = await self.env.cycle(inp)
        pre = self.env.pre_observed
        assert (change["read_move"], change["deq_move"]) == (pre["io_rdataPtrMoveCnt"], pre["io_sqDeqCnt"])
        old_owner = self.owners.get(old_read)
        bus_request = pre["io_toDCache_req_valid"] and inp.cache_ready
        unc_request = pre["io_toUncacheBuffer_req_valid"] and inp.uncache_ready
        response = False
        if self.pending:
            kind, uid, _ = self.pending
            response = (kind == "cache" and pre["io_toDCache_resp_ready"] and inp.cache_response or
                        kind == "nc" and change["nc_ack"] or kind == "io" and inp.uncache_response)
            if response:
                self.pending = None
        if bus_request or unc_request:
            assert self.pending is None and old_owner is not None
            kind = "cache" if bus_request else "nc" if old_owner.store.memory_type in (1, 5) else "io"
            self.pending = (kind, old_owner.uid, self.env.last_tick)
        consumed = []
        for seg in change["consumed"]:
            owner = next(owner for owner in self.owners.values() if owner.position % 256 == seg["sq"])
            assert seg["part"] not in self.parts[owner.uid]
            self.parts[owner.uid].add(seg["part"])
            consumed.append({"uid": owner.uid, **seg})
        if change["wb_fire"] or change["nc_ack"]:
            assert old_owner is not None and not old_owner.finished
            # Actual PSQ handleFinishSet is WB.fire OR NC store idResp, not
            # the later external NC bus response (NewStoreQueue:1658-1659).
            old_owner.finished = True
        moved = []
        for position in range(old_read, old_read + change["read_move"]):
            owner = self.owners[position]
            store = owner.store
            assert store.committed
            if store.inactive:
                pass
            elif store.cache_operation or store.memory_type:
                assert position == old_read and (change["wb_fire"] or change["nc_ack"])
            else:
                assert any(seg["sq"] == position % 256 for seg in change["accepted"])
            moved.append(owner.uid)
        self.read += change["read_move"]
        retired = []
        for position in range(old_head, old_head + change["deq_move"]):
            owner = self.owners[position]
            store = owner.store
            assert store.committed and owner.uid not in self.completed
            if store.inactive:
                assert position < self.read
            elif store.cache_operation or store.memory_type:
                assert owner.finished
            else:
                assert self.parts[owner.uid] == ({0, 1} if store.cross_word else {0})
            self.completed.add(owner.uid)
            retired.append(owner.uid)
            del self.owners[position]
        self.head += change["deq_move"]
        assert self.head <= self.read <= self.tail and self.tail - self.head <= 64
        event = {"tick": self.env.last_tick, "head_before": old_head, "read_before": old_read, "head_after": self.head, "read_after": self.read,
                 "retired": retired, "read_uids": moved, "consumed": consumed, "wb_uid": old_owner.uid if old_owner and change["wb_fire"] else None,
                 "nc_ack_uid": old_owner.uid if old_owner and change["nc_ack"] else None, "request_kind": self.pending[0] if bus_request or unc_request else None}
        self.history.append(event)
        self.emit("step", **event)
        return event

    async def drain(self, limit=100):
        for _ in range(limit):
            await self.step()
            if not self.owners and self.pending is None and not self.env.model.words:
                for _ in range(3):
                    await self.step()
                return
        raise AssertionError("PSQ actor failed to drain through actual public credits")

    def checked(self, names, uids):
        assert set(uids) <= self.completed
        self.env.coverage.sample(names, self.env.last_tick)
        self.env.coverage.sample(names, self.env.last_tick, checked=True)
        self.emit("checked", tick=self.env.last_tick, names=names, uids=list(uids), completed=sorted(self.completed), aborted=sorted(self.aborted))

    async def reset(self):
        old = sorted(owner.uid for owner in self.owners.values())
        for _ in range(3):
            await self.env.cycle(Inputs(reset=True))
        self.aborted.update(old)
        self.owners.clear()
        self.pending = None
        self.head = self.read = self.tail = 0
        self.history.append({"tick": self.env.last_tick, "reset_aborted": old})
        self.emit("reset", tick=self.env.last_tick, aborted=old)
        return old
