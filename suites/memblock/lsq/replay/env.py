from dataclasses import asdict, replace
import json

from suites.memblock.lsq.raw.types import FtqPtr, SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr
from .types import Cause, Enqueue, Inputs, Uop

PERSISTENT = {"ready", "address_ready", "address_bits", "data_ready", "data_bits", "dequeue", "upper", "sq_empty",
              "writeback", "rar_full", "raw_full", "head"}


class ReplayEnv:
    def __init__(self, driver, before, after, model, coverage, journal):
        self.driver, self.before, self.after, self.model = driver, before, after, model
        self.coverage, self.journal = coverage, journal
        self.controls = Inputs()
        self.last_tick = -1
        self.observed = None
        self.last_change = None
        self.history = []

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
                self.last_change = change
                self.history.append(change)
            except BaseException as error:
                record["error"] = repr(error)
                raise
            finally:
                self.journal.write(json.dumps(record) + "\n")
                if not record["checked"]:
                    self.journal.flush()
            if post.event.tick == edge.tick:
                return change

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
        return next(owner.uid for owner in self.model.owners.values() if owner.request == request)

    def arm(self, names, uids, *, reuse=False):
        self.coverage.arm(names, uids, self.last_tick, self.model.sequence, reuse=reuse)

    async def issue(self, slot=None):
        for _ in range(40):
            candidates = [owner for owner in self.model.owners.values() if (slot is None or owner.slot == slot) and not owner.issued]
            if any(self.observed[f"io_replay_{owner.slot % 3}_valid"] and
                   self.observed[f"io_replay_{owner.slot % 3}_bits_replayQueueIdx"] == owner.slot for owner in candidates):
                selected = next(owner for owner in candidates if self.observed[f"io_replay_{owner.slot % 3}_valid"] and
                                self.observed[f"io_replay_{owner.slot % 3}_bits_replayQueueIdx"] == owner.slot)
                change = await self.cycle(ready=tuple(bank == selected.slot % 3 for bank in range(3)))
                assert selected.uid in change["fired"]
                return selected.slot, selected.uid
            await self.cycle()
        raise AssertionError(("no expected replay within 40 cycles", slot))

    async def feedback(self, slot, *, lane=0, again=None):
        owner = self.model.owners[slot]
        if lane != owner.input_lane:
            self.arm("LRQ-OWNER.other_lane", [owner.uid])
        if again is None:
            req = replace(owner.request, valid=True, replay_feedback=True, slot=slot, need_replay=False)
        else:
            req = replace(again, valid=True, replay_feedback=True, slot=slot)
        return await self.cycle({lane: req})

    async def complete(self, slot=None, *, lane=0):
        if slot is None or not self.model.owners[slot].issued:
            slot, uid = await self.issue(slot)
        else:
            uid = self.model.owners[slot].uid
        change = await self.feedback(slot, lane=lane)
        assert uid in change["completed"]
        await self.idle(4)
        return uid

    async def issue_all(self):
        for _ in range(240):
            if all(owner.issued for owner in self.model.owners.values()):
                return
            await self.cycle(ready=(True,) * 3)
        raise AssertionError("ready Replay banks did not all issue within bound")

    async def release_all(self):
        assert all(owner.issued for owner in self.model.owners.values())
        slots = list(self.model.owners)
        for offset in range(0, len(slots), 3):
            reqs = {lane: replace(self.model.owners[slot].request, valid=True, replay_feedback=True, slot=slot, need_replay=False)
                    for lane, slot in enumerate(slots[offset:offset + 3])}
            await self.cycle(reqs)
        await self.idle(8, ready=(False,) * 3)
        assert not self.model.owners and not self.observed["io_replayAllocate"]
