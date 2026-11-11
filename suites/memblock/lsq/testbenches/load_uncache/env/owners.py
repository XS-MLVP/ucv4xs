"""Stimulus ownership, not an output predictor or a copy of model events.

Allocation has no public ready/ID, so its IDs follow the documented 16-slot
free-pool contract. Internal bus capture is instead witnessed by the actual
elastic-register output. SID obligations end on the caller's response, while
the load finishes only after observed s1 and s2 bypass windows.
"""
from dataclasses import asdict, dataclass, replace
from functools import cmp_to_key

from suites.memblock.lsq.testbenches.uncache_entry.model import is_younger
from suites.memblock.lsq.testbenches.uncache_entry.transactions import RobPtr
from suites.memblock.lsq.testbenches.load_uncache.transactions import LoadRequest, Observation, SampledInputs


@dataclass(frozen=True)
class LoadOwner:
    uid: int
    slot: int
    lane: int
    load: LoadRequest
    phase: str = "holding"
    deferred: bool = False
    data: int = 0
    error: bool = False
    nderr: bool = False


class LoadOwnership:
    def __init__(self):
        self.sequence = 0
        self.owners = {}
        self.completed, self.canceled = set(), set()
        self.reset()

    def reset(self):
        self.owners.clear()
        self.saved = ()
        self.redirect_previous = None
        self.available = list(range(16))
        self.advertised = 16
        self.waiting = [set() for _ in range(4)]
        self.selected = ()
        self.pipe = None
        self.jobs = {}
        self.pending_previous = RobPtr()
        self.bypass_s1 = (None,) * 3
        self.completed.clear()
        self.canceled.clear()

    def advance(self, inp: SampledInputs, pre: Observation, post: Observation):
        if inp.reset:
            self.reset()
            return {"reset": True, "allocated": [], "external_accept": None}
        red = inp.redirect if inp.redirect.valid else None

        def canceled(load, redirect):
            return redirect is not None and (is_younger(load.entry.rob, redirect.rob) or
                                            redirect.flush_self and load.entry.rob == redirect.rob)

        # A prior observed s1 must reach s2, with bytes from its own bus job.
        for lane, owner in enumerate(self.bypass_s1):
            if owner is not None:
                observed = post.bypass[lane]
                assert observed.s2_valid, ("owned bypass omitted its s2", lane, owner.uid)
                assert (observed.s2_data, observed.s2_derr, observed.s2_nderr) == (
                    owner.data * ((1 << 64) + 1), owner.error, owner.nderr), ("owned bypass s2 payload", lane, owner.uid)
                self.completed.add(owner.uid)

        before = dict(self.owners)
        matches, consumed = [], set()
        for lane, query in enumerate(inp.bypass):
            found = []
            if query is not None:
                for owner in before.values():
                    q = owner.load.entry
                    if owner.phase == "output" and q.lq == query.lq and (query.nc if q.nc else query.mmio):
                        found.append(owner)
            owner = min(found, key=lambda item: (not item.load.entry.nc, item.slot), default=None)
            if owner is not None:
                assert post.bypass[lane].s1_valid and post.bypass[lane].s1_paddr == owner.load.entry.paddr, (
                    "owned bypass omitted its s1", lane, owner.uid)
                consumed.update(item.slot for item in found)
            matches.append(owner)
        self.bypass_s1 = tuple(matches)

        # Both cases of a full elastic register preserve the same generation.
        fire = pre.request is not None and inp.bus_ready
        accepted = None
        if fire:
            assert self.pipe is not None and self.pipe.slot == pre.request.mid, "bus fire without a registered offer"
            accepted = self.pipe
            assert accepted.slot not in self.jobs, "duplicate external acceptance"
            self.jobs[accepted.slot] = {"uid": accepted.uid, "load": accepted.load, "sid": None}
        if pre.request is not None and not inp.bus_ready:
            assert pre.request == post.request, "elastic backpressure changed the pending offer"

        # Route by obligations that existed before this edge's ID ack. An old
        # returned SID no longer names this generation and cannot change data.
        received = {}
        if inp.returned is not None:
            received = {slot: job for slot, job in self.jobs.items() if job["sid"] == inp.returned.sid}
        if inp.ack.valid and inp.ack.mid in before:
            assert inp.ack.mid in self.jobs, "ID ack before external bus acceptance"
            self.jobs[inp.ack.mid]["sid"] = inp.ack.sid

        capture = None
        if (pre.request is None or inp.bus_ready) and post.request is not None:
            capture = before.get(post.request.mid)
            assert capture is not None and capture.phase == "request", ("unowned internal bus capture", post.request)
            q = capture.load.entry
            assert (post.request.addr, post.request.vaddr, post.request.nc,
                    post.request.rob.value, post.request.rob.flag, post.request.rob.former) == (
                        q.paddr, q.vaddr, q.nc, q.rob.value, q.rob.flag, q.rob.former), "captured bus identity mismatch"
        if pre.request is None or inp.bus_ready:
            self.pipe = capture

        free, entry_changes = [], []
        for slot in range(16):
            owner = before.get(slot)
            retired = False
            if owner is not None:
                cancel = canceled(owner.load, red)
                take = slot in consumed
                retired = ((owner.phase in ("holding", "request") and cancel) or
                           (owner.phase == "response" and slot in received and (cancel or owner.deferred)) or
                           (owner.phase == "wakeup" and (cancel or owner.deferred)) or
                           (owner.phase == "output" and (cancel or take)))
                if retired:
                    del self.owners[slot]
                    free.append(slot)
                    if not take:
                        self.canceled.add(owner.uid)
                else:
                    phase = owner.phase
                    if phase == "holding" and (owner.load.entry.nc or not is_younger(owner.load.entry.rob, self.pending_previous)):
                        phase = "request"
                    elif capture is not None and capture.slot == slot:
                        phase = "response"
                    elif slot in received:
                        phase = "wakeup"
                    elif phase == "wakeup":
                        wake = pre.nc_wakeup if owner.load.entry.nc else pre.mmio_wakeup
                        if wake is not None and (wake.flag, wake.value) == (owner.load.entry.lq.flag, owner.load.entry.lq.value):
                            phase = "output"
                    owner = replace(owner, phase=phase, deferred=owner.deferred or cancel)
                    if slot in received:
                        owner = replace(owner, data=inp.returned.data, error=inp.returned.error, nderr=inp.returned.nderr)
                    self.owners[slot] = owner
            entry_changes.append({"consumed": slot in consumed, "retired": retired,
                                  "phase_after": self.owners[slot].phase if slot in self.owners else "empty"})
        for slot in received:
            del self.jobs[slot]

        eligible, filtered = [], []
        for lane, load in self.saved:
            reason = ("redirect" if any(canceled(load, r) for r in (red, self.redirect_previous)) else
                      "exception" if load.entry.exceptions else "replay" if load.need_replay and not load.uncache_cause else
                      "type" if not (load.entry.nc or load.entry.mmio) else None)
            (filtered if reason else eligible).append((lane, load, reason) if reason else (lane, load))
        count = min(len(eligible), self.advertised, 3)
        allocations = []
        for lane, load in eligible[:count]:
            slot = self.available.pop(0)
            assert slot not in self.owners, "allocation overwrites an owned generation"
            self.sequence += 1
            owner = LoadOwner(self.sequence, slot, lane, load)
            self.owners[slot] = owner
            allocations.append({"uid": owner.uid, "slot": slot, "lane": lane, "load": asdict(load)})
        self.advertised = len(self.available)
        self.available.extend(self.selected)
        selected = []
        for bank in self.waiting:
            if bank:
                slot = min(bank)
                bank.remove(slot)
                selected.append(slot)
        self.selected = tuple(selected)
        for slot in free:
            self.waiting[slot % 4].add(slot)
        current = [(lane, load) for lane, load in enumerate(inp.requests) if load is not None]
        def by_age(a, b):
            left, right = a[1].entry.rob, b[1].entry.rob
            return 0 if left == right else 1 if is_younger(left, right) else -1
        self.saved = tuple(sorted(current, key=cmp_to_key(by_age)))
        self.redirect_previous = red
        self.pending_previous = inp.pending
        return {"reset": False, "allocated": allocations, "free": free, "entry_changes": entry_changes,
                "filtered": [{"lane": lane, "load": asdict(load), "reason": reason} for lane, load, reason in filtered],
                "rejected": [asdict(load) for _, load in eligible[count:]],
                "internal_slot": capture.slot if capture else None,
                "external_accept": accepted.uid if accepted else None}
