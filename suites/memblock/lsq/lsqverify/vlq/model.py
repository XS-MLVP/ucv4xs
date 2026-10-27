"""Independent transaction ledger with explicit externally visible time contracts."""
from collections import deque

from .types import Change, Item, Outputs, QueuePtr, Recovery


class RobTimeline:
    """Unwrap encoded ROB slots into a nearby logical timeline, never a raw-ID sort."""
    def __init__(self, size):
        self.size, self.anchor = size, None

    def decode(self, pointer, *, observe=False):
        if not 0 <= pointer.value < self.size:
            raise ValueError("ROB value outside actual configured entries")
        raw = 2 * (int(pointer.flag) * self.size + pointer.value) + int(not pointer.former)
        period = 4 * self.size
        if self.anchor is None:
            value = raw
        else:
            base = (self.anchor - raw) // period
            choices = [raw + period * n for n in (base, base + 1)]
            distance = min(abs(v - self.anchor) for v in choices)
            closest = [v for v in choices if abs(v - self.anchor) == distance]
            if len(closest) != 1:
                raise ValueError("ambiguous ROB half-ring age outside legal domain")
            value = closest[0]
        if observe:
            self.anchor = value if self.anchor is None else max(self.anchor, value)
        return value


class VirtualLoadQueueModel:
    def __init__(self, spec):
        self.spec = spec
        self.uid_sequence = self.recovery_sequence = self.edge = 0
        self.reset_kind = None
        self.restart()

    def restart(self):
        self.head = self.tail = 0
        self.entries = {}
        self.prepared = ()
        self.recoveries = deque((None, None))
        self.rob = RobTimeline(self.spec["rob_entries"])
        self.outputs = Outputs()

    @property
    def capacity(self):
        return self.spec["size"] - (self.tail - self.head)

    def advance(self, inp):
        self.edge += 1
        old_head, old_tail = self.head, self.tail
        if inp.reset:
            if any(d.valid for d in inp.dispatch) or any(w.valid for w in inp.writebacks) or inp.redirect.valid:
                raise ValueError("VLQ reset requires idle transactions")
            self.reset_kind = self.reset_kind or ("recovering" if self.outputs.recovery_stall else
                                                   "active" if old_head != old_tail else "initial")
            self.restart()
            return Change(old_head, old_tail, reset_kind=self.reset_kind)
        self.reset_kind = None
        active_dispatch = [(i, d) for i, d in enumerate(inp.dispatch) if d.valid]
        if active_dispatch and self.outputs.recovery_stall:
            raise ValueError("dispatch while externally observed recover-stall is illegal")
        total_flows = sum(d.flows for _, d in active_dispatch)
        if total_flows > self.capacity:
            raise ValueError("dispatch exceeds externally constrained VLQ capacity")
        requests = []
        offset = 0
        previous_rob = max((item.rob_order for item in self.entries.values()), default=None)
        for lane, request in active_dispatch:
            if not 0 <= request.flows <= self.spec["max_flows_per_request"]:
                raise ValueError("flow count outside the configured single-request domain")
            if request.start != QueuePtr.encode(old_tail + offset, self.spec["size"]):
                raise ValueError(f"dispatch lane {lane} does not describe the compact next interval")
            rob_order = self.rob.decode(request.rob, observe=True)
            if previous_rob is not None and rob_order < previous_rob:
                raise ValueError("dispatch ROB slots must preserve program order")
            previous_rob = rob_order
            requests.append((request, old_tail + offset, rob_order))
            offset += request.flows
        cutoff = self.rob.decode(inp.redirect.rob) if inp.redirect.valid else None

        def canceled(order):
            return cutoff is not None and (order > cutoff or inp.redirect.flush_self and order == cutoff)

        old_entries = dict(self.entries)
        canceled_items = tuple(item for item in old_entries.values() if canceled(item.rob_order))
        canceled_ids = {item.uid for item in canceled_items}
        enabled_wb = [w for w in inp.writebacks if w.valid]
        if len({w.index for w in enabled_wb}) != len(enabled_wb):
            raise ValueError("multiple writebacks to the same live slot")
        by_index = {item.position % self.spec["size"]: item for item in old_entries.values()}
        for wb in enabled_wb:
            if wb.index not in by_index or by_index[wb.index].completed:
                raise ValueError("writeback must target a live, not-yet-completed lifecycle")

        prepared = []
        for position in range(old_head, min(old_head + self.spec["release_width"], old_tail)):
            item = old_entries.get(position)
            if item is None or not item.completed or item.uid in canceled_ids:
                break
            prepared.append(item)
        blocked = old_entries.get(old_head)
        head_blocked_by = blocked.uid if blocked is not None and not blocked.completed and blocked.uid not in canceled_ids else None
        younger_completed = tuple(item.uid for pos, item in old_entries.items()
                                  if pos > old_head and item.completed and item.uid not in canceled_ids)
        reported = self.prepared
        new_head = old_head + len(reported)
        due = self.recoveries.popleft()
        proposed_tail = old_tail - due.cancel_count if due is not None else old_tail + total_flows
        new_tail = max(new_head, proposed_tail)
        stall = inp.redirect.valid or due is not None or any(r is not None for r in self.recoveries)

        for item in (*prepared, *canceled_items):
            self.entries.pop(item.position, None)
        completed, suppressed = [], []
        for wb in enabled_wb:
            item = by_index[wb.index]
            if not wb.replay and wb.update_address:
                item.completed = True
                completed.append(item.uid)
            else:
                label = "both_block" if wb.replay and not wb.update_address else "replay_blocks" if wb.replay else "invalid_addr_blocks"
                suppressed.append((item.uid, label))

        allocated = []
        canceled_dispatch = 0
        canceled_dispatch_indices = []
        for request, start, rob_order in requests:
            if canceled(rob_order):
                canceled_dispatch += request.flows
                canceled_dispatch_indices.extend(position % self.spec["size"] for position in range(start, start + request.flows))
                continue
            for position in range(start, start + request.flows):
                if position in old_entries:
                    raise ValueError("dispatch overwrites an existing lifecycle")
                self.uid_sequence += 1
                item = Item(self.uid_sequence, position, rob_order, request.rob)
                self.entries[position] = item
                allocated.append(item)

        recovery = None
        if inp.redirect.valid:
            self.recovery_sequence += 1
            count = len(canceled_items) + canceled_dispatch
            categories = ["VLQ-REDIRECT.flush_self" if inp.redirect.flush_self else "VLQ-REDIRECT.flush_after",
                          "VLQ-REDIRECT.none" if not count else "VLQ-REDIRECT.all" if count == len(old_entries) + total_flows else "VLQ-REDIRECT.partial",
                          "VLQ-RECOVER.response", "VLQ-RECOVER.stall_window"]
            observed_robs = [item.rob for item in old_entries.values()] + [d.rob for _, d in active_dispatch]
            if any(p.flag == inp.redirect.rob.flag and p.value == inp.redirect.rob.value and p.former != inp.redirect.rob.former for p in observed_robs):
                categories.append("VLQ-REDIRECT.former_latter")
            if any(p.flag != inp.redirect.rob.flag for p in observed_robs):
                categories.append("VLQ-REDIRECT.rob_flag")
            if stall and (due is not None or any(self.recoveries)):
                categories.append("VLQ-RECOVER.adjacent")
            if total_flows:
                categories.append("VLQ-RACE.dispatch_redirect")
            if enabled_wb:
                categories.append("VLQ-RACE.wb_redirect")
            recovery = Recovery(self.recovery_sequence, self.edge, count, tuple(sorted(canceled_ids)),
                                tuple(item.uid for item in self.entries.values()),
                                (*tuple(item.position % self.spec["size"] for item in canceled_items), *canceled_dispatch_indices), tuple(categories))
        self.recoveries.append(recovery)
        self.head, self.tail = new_head, new_tail
        self.prepared = tuple(prepared)
        self.outputs = Outputs(QueuePtr.encode(new_head, self.spec["size"]), old_head == old_tail,
                               bool(reported), len(reported), due is not None,
                               QueuePtr.encode(new_tail, self.spec["size"]) if due else self.outputs.recovery_ptr, bool(stall))
        assert 0 <= self.tail - self.head <= self.spec["size"]
        assert len({item.position % self.spec["size"] for item in self.entries.values()}) == len(self.entries)
        return Change(old_head, old_tail, tuple(allocated), tuple(completed), tuple(suppressed), tuple(canceled_ids),
                      tuple(prepared), reported, recovery, due, due is not None and proposed_tail <= new_head,
                      head_blocked_by, younger_completed)
