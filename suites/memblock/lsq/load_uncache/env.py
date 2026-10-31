"""Continuous pre/post checking, including fixture transition idle edges."""
from dataclasses import asdict
import json

from .model import LoadUncacheModel
from .probe import ProbeEnv


class LoadUncacheEnv(ProbeEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, coverage_scope="general_continuous_pre_post_reference", **kwargs)
        self.model = LoadUncacheModel()
        self.changes = []
        self.completed = set()
        self.pending_consumed = set()
        self.canceled = set()
        self.transaction_by_uid = {}
        self.proofs = []
        self.last_change = None

    def arm(self, scene, uids=(), *, reuse=False):
        self.reach(scene)
        self.proofs.append((scene, set(uids), bool(reuse), self.model.sequence))
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
                owner_loads = {owner.uid: owner.load for owner in self.model.owners.values()}
                change = self.model.advance(inp)
                self.last_change = change
                record["change"] = change
                record["expected_after"] = self.model.expected(inp)
                if not inp["reset"]:
                    self.compare(post.value[1], record["expected_after"], post.event.tick, "after")
                    record["checked"] = True
                    for tx in change["allocated"]:
                        self.transaction_by_uid[tx["uid"]] = tx
                    if change["external_accept"] is not None:
                        uid = change["external_accept"]
                        tx = self.transaction_by_uid[uid]
                        self.mid_requests[tx["slot"]] = owner_loads[uid]
                    for tx in change["before"]:
                        entry_change = change["entry_changes"][tx["slot"]]
                        if entry_change["consumed"]:
                            self.pending_consumed.add(tx["uid"])
                        elif entry_change["retired"]:
                            self.canceled.add(tx["uid"])
                    # A consumption/exception at s1 is not enough: the full
                    # data payload must also be successfully compared at s2.
                    returned_uids = {item["uid"] for item in self.model.s2 if item is not None}
                    finished = self.pending_consumed & returned_uids
                    self.completed.update(finished)
                    self.pending_consumed.difference_update(finished)
                    self.confirm_proofs()
                else:
                    self.proofs.clear()
                    self.completed.clear()
                    self.pending_consumed.clear()
                    self.canceled.clear()
                self.changes.append(change)
                for kind in ("nc", "mmio"):
                    if before[f"io_{kind}Wakeup_valid"]:
                        self.wakeups.append((kind, before[f"io_{kind}Wakeup_bits_flag"], before[f"io_{kind}Wakeup_bits_value"]))
                self.observed = post.value[1]
            except BaseException as error:
                record["error"] = repr(error)
                raise
            finally:
                self.journal.write(json.dumps(record) + "\n")
                self.journal.flush()
            if edge.tick == post.event.tick:
                return change

    async def reset(self):
        active = bool(self.model.owners or self.model.pipe or self.model.saved)
        await super().reset()
        self.arm("LQU-RESET.active" if active else "LQU-RESET.initial", reuse=True)

    async def settle(self, cycles=4):
        await self.idle(cycles)

    def uid(self, request):
        return next(tx.uid for tx in self.model.owners.values() if tx.load == request)

    def slot(self, request):
        return next(tx.slot for tx in self.model.owners.values() if tx.load == request)

    async def accept_all(self, *, stall=0):
        """Accept a bounded set, checking exact arbitration with the model."""
        await self.idle(stall)
        accepted = []
        for _ in range(160):
            if not self.model.saved and self.model.pipe is None and all(entry.phase not in ("holding", "request") for entry in self.model.entries if entry.owner):
                return accepted
            change = await self.cycle({"io_uncache_req_ready": 1})
            if change["external_accept"]:
                uid = change["external_accept"]
                tx = self.transaction_by_uid[uid]
                self.mid_requests[tx["slot"]] = next(owner.load for owner in self.model.owners.values() if owner.uid == uid)
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
            occupied_sids = {job["sid"] for job in self.model.external.values() if job["sid"] is not None}
            await self.bind(slot, next(sid for sid in range(16) if sid not in occupied_sids))
        if self.model.external:
            # Caller may have already accepted/bound a subset.
            for slot, job in list(self.model.external.items()):
                if job["sid"] is None:
                    occupied_sids = {item["sid"] for item in self.model.external.values() if item["sid"] is not None}
                    await self.bind(slot, next(sid for sid in range(16) if sid not in occupied_sids))
            for current_sid in sorted({job["sid"] for job in self.model.external.values()}):
                await self.respond(current_sid, data, error=error, nderr=nderr)
        await self.idle(20)
        for slot in sorted(list(self.model.owners)):
            owner = self.model.owners.get(slot)
            if owner:
                await self.bypass({slot % 3: owner.load})
        await self.idle(5)
        assert not self.model.owners and not self.model.external and self.model.pipe is None
