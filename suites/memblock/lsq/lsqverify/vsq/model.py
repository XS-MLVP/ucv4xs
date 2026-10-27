"""Ordered uop/end-snapshot ledger plus explicit externally timed events.

No DUT internal flags, slot memories, virtual pointers or selection vectors
are read. Absolute logical positions distinguish reuse from old identities.
"""
from dataclasses import asdict, dataclass

from lsqverify.raw.types import SqPtr
from lsqverify.vlq.model import RobTimeline
from lsqverify.vlq.types import Redirect, RobPtr
from .types import sq_number


@dataclass(frozen=True)
class Item:
    uid: int
    position: int
    lane: int
    rob: RobPtr
    order: int
    flows: int
    end: int


class VsqModel:
    def __init__(self):
        self.sequence = self.edge = self.reset_count = 0
        self.restart()
        self.initialized = False

    def restart(self):
        self.head = self.tail = self.precommit = self.physical_tail = self.allocated_end = 0
        self.retired_base = self.retired_due = 0
        self.records, self.active, self.outstanding = {}, set(), set()
        self.retire_pending = ()
        self.cancel_pending = self.last_pending = None
        self.redirect_valid, self.redirect_payload = False, 0
        self.external_redirect = Redirect()
        self.rob_head, self.rob = RobPtr(), RobTimeline(160)
        self.state, self.allow = "idle", True
        self.precommit_valid = self.precommit_known = False
        self.precommit_payload, self.head_rob = 0, RobPtr()

    def effective_redirect(self):
        return self.state == "walk" or self.state == "idle" and self.external_redirect.valid

    def expected(self):
        if not self.initialized:
            return {}
        want = {"io_empty": int(self.head == self.tail), "io_sqRecoverStall": int(self.state != "idle" or self.cancel_pending is not None or self.last_pending is not None or self.redirect_valid),
                "io_toPhysicalQueue_redirectPtr_valid": int(self.redirect_valid),
                "io_toPhysicalQueue_preCommitPtr_valid": int(self.precommit_valid and not self.effective_redirect())}
        def sq(prefix, number):
            ptr = SqPtr.encode(number)
            want.update({prefix + "first_flag": int(ptr.first), prefix + "second_flag": int(ptr.second), prefix + "value": ptr.value})
        sq("io_toPhysicalQueue_physicalQueueEnqPtr_", self.physical_tail)
        sq("io_toPhysicalQueue_retiredPtr_", self.retired_base + self.retired_due)
        if self.redirect_valid:
            sq("io_toPhysicalQueue_redirectPtr_bits_", self.redirect_payload)
        if want["io_toPhysicalQueue_preCommitPtr_valid"]:
            assert self.precommit_known
            sq("io_toPhysicalQueue_preCommitPtr_bits_", self.precommit_payload)
            want.update({"io_toPhysicalQueue_headRobIdx_flag": int(self.head_rob.flag), "io_toPhysicalQueue_headRobIdx_value": self.head_rob.value,
                         "io_toPhysicalQueue_headRobIdx_isFormer": int(self.head_rob.former)})
        return want

    def expected_before(self, inp):
        if not inp.reset:
            return self.expected()
        # The pinned SV resets queue/control registers on posedge reset,
        # before DriveStable. Non-reset payload/ROB/retire-sum flops settle
        # at clock edges; do not invent an asynchronous reset for them.
        return {"io_empty": 1, "io_sqRecoverStall": 0, "io_toPhysicalQueue_redirectPtr_valid": 0,
                "io_toPhysicalQueue_physicalQueueEnqPtr_first_flag": 0, "io_toPhysicalQueue_physicalQueueEnqPtr_second_flag": 0,
                "io_toPhysicalQueue_physicalQueueEnqPtr_value": 0}

    def advance(self, inp):
        self.edge += 1
        if inp.reset:
            aborted = sorted(self.outstanding)
            self.restart()
            self.reset_count += 1
            self.initialized = self.reset_count >= 3
            self.rob_head = inp.rob_head
            return {"accepted": [], "retired": [], "canceled": [], "precommitted": [], "reset_aborted": aborted, "recovery": None, "state": "idle"}
        self.reset_count = 0
        if not self.initialized:
            raise ValueError("VSQ requires three idle reset edges before traffic")
        enabled = [(lane, req) for lane, req in enumerate(inp.dispatch) if req.valid and req.need_alloc]
        if enabled and (self.state != "idle" or not self.allow or self.cancel_pending is not None or self.last_pending is not None or self.redirect_valid):
            raise ValueError("dispatch during the documented recovery/hidden-ready window")
        if self.tail - self.head + len(enabled) > 128:
            raise ValueError("external dispatch exceeds actual 128-uop virtual capacity")
        old_head, old_tail = self.head, self.tail
        head_order = self.rob.decode(self.rob_head)
        cutoff = self.rob.decode(self.external_redirect.rob) if self.effective_redirect() else None
        canceled = tuple(self.records[pos] for pos in sorted(self.active) if cutoff is not None and
                         (self.records[pos].order > cutoff or self.external_redirect.flush_self and self.records[pos].order == cutoff))
        retiring = []
        for offset in range(8):
            pos = old_head + offset
            if pos not in self.active:
                break
            item = self.records[pos]
            retired_by_rob = item.order < head_order
            deq_distance = (sq_number(inp.physical_deq) - item.end) % 256
            released = offset < 2 and inp.consumed and deq_distance < 128
            if not (retired_by_rob or released):
                break
            retiring.append(item)
        head_retired = old_head in self.active and self.records[old_head].order < head_order
        next_state = ("release" if inp.redirect.valid and head_retired else "idle") if self.state == "idle" else (
            "walk" if not head_retired else "release") if self.state == "release" else "idle"
        pre_item = self.records.get(self.precommit) if self.precommit in self.active else None
        pre_move = pre_item is not None and pre_item.order == head_order
        next_head = old_head + len(self.retire_pending)
        next_precommit = next_head if self.effective_redirect() else self.precommit + 1 if pre_move and self.precommit != old_tail else (
            next_head if self.precommit <= old_head else self.precommit)
        visible_retired = self.retire_pending
        accepted = []
        if not inp.redirect.valid:
            end = self.allocated_end
            previous_order = max((self.records[pos].order for pos in self.active), default=None)
            for lane, req in enabled:
                if not 0 <= req.flows <= 16:
                    raise ValueError("flow count outside producer domain")
                end += req.flows
                if req.end != SqPtr.encode(end):
                    raise ValueError("dispatch end snapshot is not the compact exclusive physical interval")
                order = self.rob.decode(req.rob, observe=True)
                if previous_order is not None and order < previous_order:
                    raise ValueError("dispatch ROB slots are not in program order")
                previous_order = order
                self.sequence += 1
                accepted.append(Item(self.sequence, old_tail + len(accepted), lane, req.rob, order, req.flows, end))
        next_tail = old_tail - len(self.cancel_pending["items"]) if self.cancel_pending is not None else old_tail + len(accepted)
        next_last = {**self.cancel_pending, "last": next_tail - 1} if self.cancel_pending is not None else None
        next_payload = self.redirect_payload
        if self.last_pending is not None:
            next_payload = self.records[self.last_pending["last"]].end if old_head != old_tail else self.retired_base + self.retired_due
        next_physical_tail = self.redirect_payload if self.redirect_valid else accepted[-1].end if accepted else self.physical_tail
        recovery = None
        if self.last_pending is not None:
            recovery = {"end": next_payload, "canceled_uids": [item.uid for item in self.last_pending["items"]]}
        if self.redirect_valid:
            self.allocated_end = self.redirect_payload
        elif accepted:
            self.allocated_end = accepted[-1].end
        self.precommit_valid = self.precommit > old_head or pre_move
        if pre_move:
            self.precommit_payload, self.head_rob, self.precommit_known = pre_item.end, pre_item.rob, True
        new_cancel = {"items": canceled, "cutoff": cutoff} if self.effective_redirect() else None
        self.active.difference_update(item.position for item in (*retiring, *canceled))
        self.outstanding.difference_update(item.uid for item in (*visible_retired, *canceled))
        for item in accepted:
            self.records[item.position] = item
            self.active.add(item.position)
            self.outstanding.add(item.uid)
        self.retired_base += self.retired_due
        self.retired_due = sum(item.flows for item in visible_retired)
        self.retire_pending = tuple(retiring)
        self.cancel_pending, self.last_pending = new_cancel, next_last
        self.redirect_valid, self.redirect_payload = recovery is not None, next_payload
        if self.state == "idle":
            self.rob_head = inp.rob_head
        self.external_redirect = inp.redirect if inp.redirect.valid else Redirect(False, self.external_redirect.rob, self.external_redirect.flush_self)
        self.allow = old_tail >= old_head and self.state == "idle"
        self.head, self.tail, self.precommit, self.physical_tail, self.state = next_head, next_tail, next_precommit, next_physical_tail, next_state
        assert self.head <= self.tail and self.tail - self.head <= 128
        return {"accepted": [asdict(item) for item in accepted], "retired": [asdict(item) for item in visible_retired],
                "canceled": [asdict(item) for item in canceled], "precommitted": [asdict(pre_item)] if pre_move else [],
                "reset_aborted": [], "recovery": recovery, "state": self.state}
