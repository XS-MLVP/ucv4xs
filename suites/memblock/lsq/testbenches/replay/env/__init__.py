from dataclasses import asdict, dataclass, replace
import json

from suites.memblock.lsq.testbenches.uncache_entry.model import is_younger

from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.replay.transactions import Cause
from suites.memblock.lsq.testbenches.replay.transactions import Enqueue
from suites.memblock.lsq.testbenches.replay.transactions import Inputs
from suites.memblock.lsq.testbenches.replay.transactions import Uop

@dataclass
class LiveOwner:
    uid: int
    slot: int
    input_lane: int
    request: object
    mshr: int = 0
    version: int = 0
    issued: bool = False
    # Public dependency state: an UNCACHE owner stays blocked until its own
    # LQ wakeup is driven on the public input.
    blocked: bool = False


PERSISTENT = {"ready", "address_ready", "address_bits", "data_ready", "data_bits", "dequeue", "upper", "sq_empty",
              "writeback", "rar_full", "raw_full", "head"}


class ReplayEnv:
    def __init__(self, driver, before, after, model, coverage, journal):
        self.driver, self.before, self.after, self.model = driver, before, after, model
        self.coverage, self.journal = coverage, journal
        self.controls = Inputs()
        self.last_tick = -1
        self.observed = None
        self.response = self.pre_response = None
        self.last_change = None
        self.history = []
        # Allocation input owns a generation; only an observed bank handshake
        # grants it. There is no public allocation-ID response on this DUT.
        self.owners = {}
        self.sequence = 0
        self.mshr_history = [0] * 120
        self._reset_pool()
        self.completed_uids = set()
        self.last_fired = ()

    @staticmethod
    def compare(actual, expected, phase, tick):
        for field, value in expected.items():
            assert actual[field] == value, ("replay-cycle", tick, phase, field, actual[field], value)

    async def cycle(self, enqueues=(), **kwargs):
        if isinstance(enqueues, dict):
            enqueues = tuple(enqueues.get(lane, Enqueue()) for lane in range(3))
        elif not enqueues:
            enqueues = (Enqueue(),) * 3
        persistent = {name: value for name, value in kwargs.items() if name in PERSISTENT}
        self.controls = replace(self.controls, **persistent)
        inp = replace(self.controls, enqueues=tuple(enqueues), **{name: value for name, value in kwargs.items() if name not in PERSISTENT})
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved Replay cycle"
            self.last_tick = post.event.tick
            observed_inp, actual_before = pre.value
            assert observed_inp == post.value[0]
            if post.event.tick == edge.tick:
                assert observed_inp == inp, ("Replay typed adapter input mismatch", observed_inp, inp)
            record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(observed_inp),
                      "post_input": asdict(post.value[0]), "before": actual_before, "after": post.value[1], "checked": False}
            try:
                expected_before = self.model.expected(observed_inp)
                record["expected_before"] = expected_before
                if not observed_inp.reset:
                    self.compare(actual_before, expected_before, "before", pre.event.tick)
                change = self.model.advance(observed_inp)
                expected_after = self.model.expected(post.value[0])
                record.update(change=change, expected_after=expected_after)
                if not observed_inp.reset:
                    self.compare(post.value[1], expected_after, "after", post.event.tick)
                    record["checked"] = True
                self.coverage.observe(observed_inp, change, self.model, post.event.tick)
                self.observed = post.value[1]
                self.pre_response = self.driver.ports.observe(actual_before)
                self.response = self.driver.ports.observe(self.observed)
                self.last_change = self._update_ledger(observed_inp, self.pre_response)
                self.history.append(change)
            except BaseException as error:
                record["error"] = repr(error)
                raise
            finally:
                self.journal.write(json.dumps(record) + "\n")
                if not record["checked"]:
                    self.journal.flush()
            if post.event.tick == edge.tick:
                return self.last_change

    def debug_owners(self):
        return [(o.slot, o.uid, o.request.causes, o.blocked, o.issued, o.mshr) for o in self.owners.values()]

    @property
    def pool_available(self):
        return len(self.available)

    def _reset_pool(self):
        # Contract-derived allocation schedule, NOT observed internal slots.
        # Return N -> bank select N+1 -> FIFO return N+2; preallocation credit
        # becomes visible one edge after that. Actual Replay identity is bound
        # and checked separately at its public valid/ready grant.
        self.available = list(range(120))
        self.advertised = 120
        self.waiting = [set() for _ in range(4)]
        self.selected = ()
        self.cooldown = [0] * 3
        self.previous_fire = (False,) * 3
        self.delayed_load_wakeups = ()

    def _update_ledger(self, inp, pre_response):
        """Independent Replay owner/pool ledger from sampled public windows.

        A public replay handshake (pre-edge valid with the lane ready) grants
        re-execution but does not release the slot; only a matching feedback
        with ``need_replay=False`` releases it.  Canceled owners are a redirect
        suffix. Allocation slot order is derived from the documented FIFO,
        not observed at allocation and not supplied by a second model.
        """
        if inp.reset:
            self.owners.clear()
            self.sequence = 0
            self.mshr_history = [0] * 120
            self._reset_pool()
            self.completed_uids = set()
            self.last_fired = ()
            return {"allocated": [], "fired": [], "completed": [], "cooldown": list(self.cooldown)}
        fired, completed, allocated = [], [], []
        fires = tuple(item.valid and inp.ready[bank] for bank, item in enumerate(pre_response.replay))
        for bank in range(3):
            visible = pre_response.replay[bank]
            if not fires[bank]:
                continue
            slot = visible.replay_queue_idx
            owner = self.owners.get(slot)
            assert owner is not None, ("public replay handshake for an unowned slot", slot)
            uop = owner.request.uop
            assert (visible.lq_idx_flag, visible.lq_idx_value, visible.rob_idx_flag,
                    visible.rob_idx_value, visible.rob_idx_former, visible.checkpoint_id, visible.sq) == (
                        uop.lq.flag, uop.lq.value, uop.rob.flag, uop.rob.value, uop.rob.former, uop.checkpoint, uop.sq), (
                            "public Replay grant changed its request-owned generation", slot, owner.uid)
            owner.issued = True
            owner.scheduled = True
            fired.append({"uid": owner.uid, "slot": slot, "bank": bank})
        self.last_fired = tuple(item["uid"] for item in fired)
        # Contract threshold from consecutive sampled handshakes, not the
        # model's private cooldown. A cold bank finishes its 16-edge period.
        for bank, fire in enumerate(fires):
            count = self.cooldown[bank]
            self.cooldown[bank] = (count + 1) % 16 if count >= 12 or self.previous_fire[bank] and fire else 0
        self.previous_fire = fires
        freed = []
        for slot, owner in self.owners.items():
            if inp.redirect.valid and (is_younger(owner.request.uop.rob, inp.redirect.rob) or
                                       inp.redirect.flush_self and owner.request.uop.rob == inp.redirect.rob):
                freed.append(slot)
            # MMIO/NC wakeups have one local register (contract section 4).
            # Apply the previous sampled input to an already resident owner;
            # a same-edge feedback below establishes a fresh wait obligation.
            if owner.blocked and any(wakeup.valid and wakeup.lq == owner.request.uop.lq
                                     for wakeup in self.delayed_load_wakeups):
                owner.blocked = False
        incoming = [request for request in inp.enqueues if request.valid]
        for request in incoming:
            if not request.replay_feedback:
                continue
            owner = self.owners.get(request.slot)
            assert owner is not None, ("feedback for an unowned slot", request.slot)
            assert owner.issued, ("feedback requires its own prior public handshake", request.slot)
            if not request.need_replay:
                freed.append(request.slot)
                self.completed_uids.add(owner.uid)
                completed.append({"uid": owner.uid, "slot": request.slot})
            else:
                owner.request = request
                owner.version += 1
                owner.issued = owner.scheduled = False
                owner.blocked = request.causes == 1 << Cause.UNCACHE
                if request.handled:
                    owner.mshr = self.mshr_history[request.slot] = request.mshr
        self.delayed_load_wakeups = (inp.mmio, inp.nc)
        for slot in sorted(set(freed)):
            self.owners.pop(slot, None)
        need_new = [request.valid and request.need_replay and not request.replay_feedback and
                    not (inp.redirect.valid and (is_younger(request.uop.rob, inp.redirect.rob) or
                                                 inp.redirect.flush_self and request.uop.rob == inp.redirect.rob))
                    for request in inp.enqueues]
        if sum(need_new) > min(3, self.advertised):
            raise ValueError("new replay allocation outside the preallocated pool prefix")
        for lane, request in enumerate(inp.enqueues):
            if not need_new[lane]:
                continue
            slot = self.available.pop(0)
            assert slot not in self.owners, ("preallocated slot still owned", slot)
            self.sequence += 1
            if request.handled:
                self.mshr_history[slot] = request.mshr
            self.owners[slot] = LiveOwner(self.sequence, slot, lane, request,
                                          mshr=self.mshr_history[slot], issued=False,
                                          blocked=request.causes == 1 << Cause.UNCACHE)
            allocated.append({"uid": self.sequence, "slot": slot, "input_lane": lane})
        self.advertised = len(self.available)
        self.available.extend(self.selected)
        selected = []
        for bank in self.waiting:
            if bank:
                slot = min(bank)
                bank.remove(slot)
                selected.append(slot)
        self.selected = tuple(selected)
        for slot in set(freed):
            self.waiting[slot % 4].add(slot)
        groups = [set(self.available), set(self.owners), set(self.selected), *self.waiting]
        assert len(self.available) == len(groups[0]) and sum(map(len, groups)) == 120
        assert len(set().union(*groups)) == 120
        for index, group in enumerate(groups):
            assert all(not group & other for other in groups[:index]), "Replay ownership overlap"
        return {"allocated": allocated, "fired": fired, "completed": completed, "cooldown": list(self.cooldown)}

    async def reset(self):
        self.controls = Inputs()
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(3)

    async def idle(self, cycles=1, **kwargs):
        return [await self.cycle(**kwargs) for _ in range(cycles)]

    def request(self, cause=Cause.BANK_CONFLICT, *, rob=10, lq=20, sq=7, tag=1, **kwargs):
        uop = Uop(RobPtr.encode(rob), QueuePtr.encode(lq), SqPtr.encode(sq), FtqPtr(bool(tag & 64), tag % 64),
                  tag % 32, bool(tag & 1), 0xABCDEF0000000000 | tag, 6, bool(tag & 1), bool(tag & 2),
                  bool(tag & 4), bool(tag & 8), (tag * 7) % 256, bool(tag & 16), SqPtr.encode(sq), bool(tag & 32), False)
        return replace(Enqueue(True, uop, 0x1234567800000 | (tag % 16), 0xA55A, False, False, False, False, 0,
                               False, True, 0, 5, SqPtr.encode(sq), SqPtr.encode(sq), False, True, 1 << int(cause), 7), **kwargs)

    def uid(self, request):
        return next(owner.uid for owner in self.owners.values() if owner.request == request)

    def arm(self, names, uids, *, reuse=False):
        self.coverage.arm(names, uids, self.last_tick, self.sequence, reuse=reuse)

    async def issue(self, slot=None):
        for _ in range(40):
            candidates = [owner for owner in self.owners.values()
                          if (slot is None or owner.slot == slot) and not owner.issued]
            selected = next((owner for owner in candidates
                              if self.response.replay[owner.slot % 3].valid and
                              self.response.replay[owner.slot % 3].replay_queue_idx == owner.slot), None)
            if selected is not None:
                await self.cycle(ready=tuple(bank == selected.slot % 3 for bank in range(3)))
                assert selected.uid in self.last_fired, (
                    "public handshake did not reach the owned replay slot", selected)
                return selected.slot, selected.uid
            await self.cycle()
        raise AssertionError(("no expected replay within 40 cycles", slot))

    async def feedback(self, slot, *, lane=0, again=None):
        owner = self.owners[slot]
        if lane != owner.input_lane:
            self.arm("LRQ-OWNER.other_lane", [owner.uid])
        if again is None:
            req = replace(owner.request, valid=True, replay_feedback=True, slot=slot, need_replay=False)
        else:
            req = replace(again, valid=True, replay_feedback=True, slot=slot)
        return await self.cycle({lane: req})

    async def complete(self, slot=None, *, lane=0):
        if slot is None or not self.owners[slot].issued:
            slot, uid = await self.issue(slot)
        else:
            uid = self.owners[slot].uid
        await self.feedback(slot, lane=lane)
        assert uid in self.completed_uids, ("feedback did not release the owned slot", uid)
        await self.idle(4)
        return uid

    async def issue_all(self):
        for _ in range(240):
            if all(owner.issued for owner in self.owners.values()):
                return
            await self.cycle(ready=(True,) * 3)
        raise AssertionError("ready Replay banks did not all issue within bound")

    async def release_all(self):
        assert all(owner.issued for owner in self.owners.values())
        slots = list(self.owners)
        for offset in range(0, len(slots), 3):
            reqs = {lane: replace(self.owners[slot].request, valid=True, replay_feedback=True, slot=slot, need_replay=False)
                    for lane, slot in enumerate(slots[offset:offset + 3])}
            await self.cycle(reqs)
        await self.idle(8, ready=(False,) * 3)
        assert not self.owners and not self.response.replay_allocate
