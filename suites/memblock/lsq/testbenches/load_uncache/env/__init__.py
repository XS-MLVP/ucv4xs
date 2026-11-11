"""Continuous pre/post checking, including fixture transition idle edges."""
import json

from suites.memblock.lsq.testbenches.load_uncache.model import LoadUncacheModel
from suites.memblock.lsq.testbenches.load_uncache.env.probe import ProbeEnv
from suites.memblock.lsq.testbenches.load_uncache.env.owners import LoadOwnership


class LoadUncacheEnv(ProbeEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, coverage_scope="general_continuous_pre_post_reference", **kwargs)
        self.model = LoadUncacheModel()
        self.ownership = LoadOwnership()
        self.owners = self.ownership.owners
        self.changes = []
        self.completed = self.ownership.completed
        self.canceled = self.ownership.canceled
        self.transaction_by_uid = {}
        self.proofs = []
        self.last_change = None

    def arm(self, scene, uids=(), *, reuse=False):
        self.reach(scene)
        self.proofs.append((scene, set(uids), bool(reuse), self.ownership.sequence))
        self.confirm_proofs()

    def confirm_proofs(self):
        remaining = []
        for scene, uids, reuse, since in self.proofs:
            done = uids <= (self.canceled if reuse else self.completed)
            if reuse:
                done &= any(uid > since for uid in self.completed)
            if done:
                self.prove(scene)
            else:
                remaining.append((scene, uids, reuse, since))
        self.proofs = remaining

    @staticmethod
    def compare(actual, expected, tick, phase):
        for name, want in expected.items():
            assert actual[name] == want, ("parent-cycle", tick, phase, name, actual[name], want)

    async def cycle(self, values=None, *, pending=None):
        if pending is not None:
            self.pending = pending
        drive = dict.fromkeys(self.ports.inputs, 0)
        drive.update(io_rob_pendingPtr_flag=int(self.pending.flag), io_rob_pendingPtr_value=self.pending.value,
                     io_rob_pendingPtr_isFormer=int(self.pending.former))
        for name, value in (values or {}).items():
            if name not in drive:
                raise ValueError(f"not an actual parent input: {name}")
            drive[name] = int(value)
        edge = await self.driver.send(drive)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= edge.tick and pre.event.tick + 1 == post.event.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "omitted passive cycle"
            self.last_tick = post.event.tick
            inp, before = pre.value
            assert inp == post.value[0]
            if edge.tick == post.event.tick:
                assert inp == drive
            record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": inp, "post_input": post.value[0],
                      "before": before, "after": post.value[1], "checked": False, "scope": "general_public_pin_reference"}
            try:
                expected = self.model.expected(inp)
                record["expected_before"] = expected
                if not inp["reset"]:
                    self.compare(before, expected, pre.event.tick, "before")
                change = self.model.advance(inp)
                record["change"] = change
                record["expected_after"] = self.model.expected(inp)
                if not inp["reset"]:
                    self.compare(post.value[1], record["expected_after"], post.event.tick, "after")
                    record["checked"] = True
                else:
                    self.proofs.clear()
                sampled = self.ports.observe_inputs(inp)
                observed_before = self.ports.observe(before)
                observed_after = self.ports.observe(post.value[1])
                self.last_change = self.ownership.advance(sampled, observed_before, observed_after)
                self.external = {job["uid"] for job in self.ownership.jobs.values()}
                self.pipe_uid = self.ownership.pipe.uid if self.ownership.pipe is not None else None
                self.pool_available = len(self.ownership.available)
                for tx in self.last_change["allocated"]:
                    self.transaction_by_uid[tx["uid"]] = tx
                if not sampled.reset and observed_before.request is not None and sampled.bus_ready:
                    mid = observed_before.request.mid
                    self.mid_requests[mid] = self.ownership.jobs[mid]["load"]
                if sampled.reset:
                    self.transaction_by_uid.clear()
                    self.mid_requests.clear()
                else:
                    self.confirm_proofs()
                self.changes.append(change)
                for kind in ("nc", "mmio"):
                    if before[f"io_{kind}Wakeup_valid"]:
                        self.wakeups.append((kind, before[f"io_{kind}Wakeup_bits_flag"], before[f"io_{kind}Wakeup_bits_value"]))
                self.observed = post.value[1]
                self.response = observed_after
            except BaseException as error:
                record["error"] = repr(error)
                raise
            finally:
                self.journal.write(json.dumps(record) + "\n")
                self.journal.flush()
            if edge.tick == post.event.tick:
                return self.last_change

    async def reset(self):
        active = bool(self.owners or self.pipe_uid is not None or self.ownership.saved)
        await super().reset()
        self.arm("LQU-RESET.active" if active else "LQU-RESET.initial", reuse=True)

    async def settle(self, cycles=4):
        await self.idle(cycles)

    @property
    def pipe_slot(self):
        if self.pipe_uid is None:
            return None
        return next((owner.slot for owner in self.owners.values() if owner.uid == self.pipe_uid), None)

    def uid(self, request):
        return next(owner.uid for owner in self.owners.values() if owner.load == request)

    def slot(self, request):
        return next(owner.slot for owner in self.owners.values() if owner.load == request)

    async def accept_all(self, *, stall=0):
        """Accept a bounded set, checking exact arbitration with the model."""
        await self.idle(stall)
        accepted = []
        for _ in range(160):
            if not self.ownership.saved and self.pipe_uid is None and all(owner.phase not in ("holding", "request") for owner in self.owners.values()):
                return accepted
            change = await self.cycle({"io_uncache_req_ready": 1})
            if change["external_accept"]:
                uid = change["external_accept"]
                tx = self.transaction_by_uid[uid]
                accepted.append((tx["slot"], uid))
        raise AssertionError("parent arbitration did not drain in bounded time")

    async def bypass(self, requests):
        values = {}
        for lane, req in requests.items():
            q = req.entry
            prefix = f"io_bypass_{lane}_s0Req_"
            values.update({prefix + "valid": 1, prefix + "bits_lqIdx_flag": q.lq.flag, prefix + "bits_lqIdx_value": q.lq.value,
                           prefix + "bits_isNCReplay": q.nc, prefix + "bits_isMMIOReplay": q.mmio})
        return await self.cycle(values)

    async def drain(self, *, data=0x123456789ABCDEF0, error=False, nderr=False):
        accepted = await self.accept_all()
        for slot, uid in accepted:
            occupied_sids = {job["sid"] for job in self.ownership.jobs.values() if job["sid"] is not None}
            await self.bind(slot, next(sid for sid in range(16) if sid not in occupied_sids))
        if self.ownership.jobs:
            # Caller may have already accepted/bound a subset.
            for slot, job in list(self.ownership.jobs.items()):
                if job["sid"] is None:
                    occupied_sids = {item["sid"] for item in self.ownership.jobs.values() if item["sid"] is not None}
                    await self.bind(slot, next(sid for sid in range(16) if sid not in occupied_sids))
            for current_sid in sorted({job["sid"] for job in self.ownership.jobs.values()}):
                await self.respond(current_sid, data, error=error, nderr=nderr)
        await self.idle(20)
        for slot in sorted(list(self.owners)):
            owner = self.owners.get(slot)
            if owner:
                await self.bypass({slot % 3: owner.load})
        await self.idle(5)
        assert not self.owners and not self.external and self.pipe_uid is None
