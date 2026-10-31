"""Parent protocol ledger built from public inputs, never from DUT registers.

The independent FreeList and entry specifications are composed here. External
SID obligations end on response, whereas LDU ownership ends on consumption.
That distinction deliberately does NOT reproduce the RTL's stale SID routing.
"""
from dataclasses import asdict, dataclass, replace
from functools import cmp_to_key

from suites.memblock.lsq.freelist.model import FreeListModel
from suites.memblock.lsq.freelist.types import Observation
from suites.memblock.lsq.uncache_entry.model import UncacheEntryModel, is_younger
from suites.memblock.lsq.uncache_entry.types import IdResponse, Inputs, QueuePtr, Redirect, Request, Response, RobPtr, SOURCE_EXCEPTION_BITS
from suites.memblock.lsq.raw.types import FtqPtr
from .probe import LoadRequest

ALL_EXCEPTIONS = (*SOURCE_EXCEPTION_BITS, 19, 5)


def pointer(values, prefix):
    return RobPtr(bool(values[prefix + "flag"]), values[prefix + "value"], bool(values[prefix + "isFormer"]))


def redirect(values):
    return Redirect(bool(values["io_redirect_valid"]), pointer(values, "io_redirect_bits_robIdx_"), bool(values["io_redirect_bits_level"]))


def canceled(q, red):
    return red.valid and (is_younger(q.rob, red.rob) or red.flush_self and q.rob == red.rob)


def decode_load(values, lane):
    prefix = f"io_req_{lane}_"
    get = lambda name: values[prefix + name]
    q = Request(bool(get("valid")), pointer(values, prefix + "bits_uop_robIdx_"),
                QueuePtr(bool(get("bits_uop_lqIdx_flag")), get("bits_uop_lqIdx_value")),
                *(get("bits_" + name) for name in ("vaddr", "fullva", "paddr", "gpaddr", "mask")),
                *(bool(get("bits_" + name)) for name in ("nc", "mmio", "memBackTypeMM", "isHyper", "isForVSnonLeafPTE")),
                sum(get(f"bits_uop_exceptionVec_{bit}") << bit for bit in ALL_EXCEPTIONS))
    return LoadRequest(q, FtqPtr(bool(get("bits_uop_ftqPtr_flag")), get("bits_uop_ftqPtr_value")),
                       get("bits_uop_ftqOffset"), bool(get("bits_uop_isRVC")), get("bits_uop_perfDebugInfo_runahead_checkpoint_id"),
                       bool(get("bits_rep_info_need_rep")), bool(get("bits_rep_info_cause_0")))


@dataclass(frozen=True)
class Transaction:
    uid: int
    load: LoadRequest
    lane: int
    slot: int


class GroupArbiter:
    """Remembered waiters after last acceptance, with candidate withdrawal."""
    def __init__(self):
        self.waiters = []
        self.after_index = -1

    def choose(self, active):
        candidates = [index for index in self.waiters if index > self.after_index]
        candidate = min(candidates) if candidates else None
        return candidate if candidate in active else min(active, default=None)

    def accept(self, active, chosen):
        self.waiters = sorted(set(active) - {chosen})
        self.after_index = chosen


class LoadUncacheModel:
    def __init__(self):
        self.sequence = self.edge = 0
        self.restart()

    def restart(self):
        self.pool = FreeListModel(16, True)
        self.entries = [UncacheEntryModel({"entry_id": i, "wakeup_backpressure": i != 0, "lq_entries": 120}) for i in range(16)]
        self.owners = {}
        self.saved = ()
        self.red_history = [Redirect(), Redirect()]
        self.groups = [GroupArbiter(), GroupArbiter()]
        self.prefer_low = False
        self.pipe = None
        self.external = {}
        self.s1 = [None] * 3
        self.s2 = [None] * 3
        self.rollback = None

    def connections(self, values):
        red, pending = redirect(values), pointer(values, "io_rob_pendingPtr_")
        ack = IdResponse(bool(values["io_uncache_idResp_valid"]), values["io_uncache_idResp_bits_mid"], values["io_uncache_idResp_bits_sid"])
        response = Response(bool(values["io_uncache_resp_valid"]), values["io_uncache_resp_bits_data"], bool(values["io_uncache_resp_bits_error"]), bool(values["io_uncache_resp_bits_nderr"]))
        local = []
        for slot, entry in enumerate(self.entries):
            # Only an outstanding external obligation can receive a new packet.
            job = self.external.get(slot)
            receives = response.valid and job is not None and job["sid"] == values["io_uncache_resp_bits_id"]
            local.append(Inputs(pending=pending, redirect=red, id_response=ack if slot == ack.mid else IdResponse(),
                                response=response if receives else Response(), reset=bool(values["reset"])))
        outputs = [entry.outputs_for(inp) for entry, inp in zip(self.entries, local, strict=True)]
        mmio = [i for i, out in enumerate(outputs) if out.mmio_select]
        active = [[i for i in range(group * 8, (group + 1) * 8) if outputs[i].bus.valid and i not in mmio] for group in range(2)]
        low, high = (self.groups[g].choose(active[g]) for g in range(2))
        group = 0 if low is not None and (high is None or self.prefer_low) else 1
        chosen = max(mmio) if mmio else (low if group == 0 else high)
        accept = chosen is not None and outputs[chosen].bus.valid and (self.pipe is None or values["io_uncache_req_ready"])
        wake_slots = {}
        for kind in ("nc", "mmio"):
            wake_slots[kind] = next((i for i, out in enumerate(outputs) if getattr(out, kind + "_wakeup").valid), None)
        matches, consumed = [], set()
        for lane in range(3):
            prefix = f"io_bypass_{lane}_s0Req_"
            found = []
            if values[prefix + "valid"]:
                lq = QueuePtr(bool(values[prefix + "bits_lqIdx_flag"]), values[prefix + "bits_lqIdx_value"])
                for kind in ("nc", "mmio"):
                    if values[prefix + ("bits_isNCReplay" if kind == "nc" else "bits_isMMIOReplay")]:
                        for i, out in enumerate(outputs):
                            data = getattr(out, kind)
                            if data.valid and data.lq == lq:
                                found.append((i, kind, data))
            # Unique live LQ identities; NC wins if both replay kinds requested.
            if found:
                slot, kind, data = min(found, key=lambda item: (item[1] != "nc", item[0]))
                matches.append({"uid": self.owners[slot].uid, "slot": slot, "paddr": data.paddr,
                                "data": data.data, "error": data.error, "nderr": data.nderr})
                consumed.update(item[0] for item in found)
            else:
                matches.append(None)
        for slot, inp in enumerate(local):
            local[slot] = replace(inp, bus_ready=bool(accept and chosen == slot), mmio_wake_ready=wake_slots["mmio"] == slot,
                                  nc_wake_ready=wake_slots["nc"] == slot, mmio_ready=slot in consumed, nc_ready=slot in consumed)
        # Entry0's deleted ready is always true; no higher-priority competitor.
        local[0] = replace(local[0], mmio_wake_ready=True, nc_wake_ready=True)
        return local, outputs, chosen, bool(accept), active, group, wake_slots, matches

    def expected(self, values):
        _, outs, _, _, _, _, wakes, _ = self.connections(values)
        reset = bool(values["reset"])
        # Entry control, elastic-valid and rollback-valid are asynchronous
        # reset registers. Bypass s1/s2 and entry exception are NOT: preserve
        # their actual pre-edge history rather than masking an active reset.
        if reset:
            wakes = dict(nc=None, mmio=None)
        want = {"io_rob_mmioBusy": int(not reset and any(out.mmio_select for out in outs)),
                "io_uncache_req_valid": int(not reset and self.pipe is not None),
                "io_rollback_valid": int(not reset and self.rollback is not None)}
        if self.pipe and not reset:
            slot, uid, bus = self.pipe
            payload = {"robIdx_flag": bus.rob.flag, "robIdx_value": bus.rob.value, "robIdx_isFormer": bus.rob.former,
                       "cmd": 0, "addr": bus.paddr, "vaddr": bus.vaddr, "mask": bus.mask, "id": slot,
                       "nc": bus.nc, "memBackTypeMM": bus.memory_backed}
            want.update({"io_uncache_req_bits_" + key: int(value) for key, value in payload.items()})
        for kind, slot in wakes.items():
            want[f"io_{kind}Wakeup_valid"] = int(slot is not None)
            if slot is not None:
                lq = getattr(outs[slot], kind + "_wakeup").lq
                want.update({f"io_{kind}Wakeup_bits_flag": int(lq.flag), f"io_{kind}Wakeup_bits_value": lq.value})
        for lane in range(3):
            for stage, item in ((1, self.s1[lane]), (2, self.s2[lane])):
                prefix = f"io_bypass_{lane}_s{stage}Resp_"
                want[prefix + "valid"] = int(item is not None)
                if item:
                    payload = {"paddr": item["paddr"]} if stage == 1 else {"data": item["data"] * ((1 << 64) + 1), "derr": int(item["error"]), "nderr": int(item["nderr"])}
                    want.update({prefix + "bits_" + key: value for key, value in payload.items()})
        fault = next((out.exception for out in outs if out.exception.valid), None)
        want["io_exceptionInfo_valid"] = int(fault is not None)
        if fault:
            payload = {"robIdx_flag": int(fault.rob.flag), "robIdx_value": fault.rob.value, "robIdx_isFormer": int(fault.rob.former),
                       "vaddr": fault.fullva, "gpaddr": fault.gpaddr & ((1 << 50) - 1), "isHyper": int(fault.hyper), "isForVSnonLeafPTE": int(fault.nonleaf),
                       **{f"exceptionVec_{bit}": fault.exceptions >> bit & 1 for bit in ALL_EXCEPTIONS}}
            want.update({"io_exceptionInfo_bits_" + key: value for key, value in payload.items()})
        if self.rollback and not reset:
            q = self.rollback
            payload = {"robIdx_flag": int(q.entry.rob.flag), "robIdx_value": q.entry.rob.value, "robIdx_isFormer": int(q.entry.rob.former),
                       "ftqIdx_flag": int(q.ftq.flag), "ftqIdx_value": q.ftq.value, "ftqOffset": q.offset,
                       "isRVC": int(q.rvc), "level": 1, "debug_runahead_checkpoint_id": q.checkpoint}
            want.update({"io_rollback_bits_" + key: value for key, value in payload.items()})
        return want

    def advance(self, values):
        self.edge += 1
        if values["reset"]:
            lost = list(self.owners.values())
            old_s1 = self.s1
            self.restart()
            # RegNext(s1Valid) is a resetless, still-clocked data pipeline;
            # the old captured bytes/errors must emerge at s2 on this edge.
            self.s2 = old_s1
            return {"reset": True, "reset_owners": [asdict(tx) for tx in lost]}
        local, outs, chosen, accept, active, group, wakes, matches = self.connections(values)
        red = redirect(values)
        eligible, filtered = [], []
        for lane, load in self.saved:
            q = load.entry
            reason = ("redirect" if any(canceled(q, r) for r in (red, self.red_history[0])) else
                      "exception" if q.exceptions else "replay" if load.need_replay and not load.uncache_cause else
                      "type" if not (q.nc or q.mmio) else None)
            (filtered if reason else eligible).append((lane, load, reason) if reason else (lane, load))
        offers = self.pool.expected()
        accepted, rejected = eligible[:offers.offered], eligible[offers.offered:]
        allocations = []
        for slot, (lane, load) in zip(offers.slots, accepted, strict=False):
            self.sequence += 1
            tx = Transaction(self.sequence, load, lane, slot)
            allocations.append(tx)
            local[slot] = replace(local[slot], request=load.entry)
        before = dict(self.owners)
        external_fire = self.pipe is not None and bool(values["io_uncache_req_ready"])
        if external_fire:
            slot, uid, bus = self.pipe
            assert slot not in self.external, "duplicate external request for same generation"
            self.external[slot] = {"uid": uid, "sid": None, "paddr": bus.paddr}
        ack_mid = values["io_uncache_idResp_bits_mid"]
        if values["io_uncache_idResp_valid"] and ack_mid in self.owners:
            assert ack_mid in self.external, "ID response without external bus acceptance"
            self.external[ack_mid]["sid"] = values["io_uncache_idResp_bits_sid"]
        response_uids = []
        if values["io_uncache_resp_valid"]:
            sid = values["io_uncache_resp_bits_id"]
            for slot, job in list(self.external.items()):
                if job["sid"] == sid:
                    response_uids.append(job["uid"])
                    del self.external[slot]
        old_pipe = self.pipe
        if accept:
            self.pipe = (chosen, self.owners[chosen].uid, outs[chosen].bus)
            if not any(out.mmio_select for out in outs):
                self.groups[group].accept(active[group], chosen)
                self.prefer_low = bool(active[0]) if group else not bool(active[1])
        elif external_fire:
            self.pipe = None
        changes, free = [], []
        for slot, (entry, inp) in enumerate(zip(self.entries, local, strict=True)):
            change = entry.advance(inp)
            if change.retired:
                free.append(slot)
                del self.owners[slot]
            changes.append(asdict(change))
        for tx in allocations:
            assert tx.slot not in self.owners
            self.owners[tx.slot] = tx
        self.pool.advance(Observation(False, (1 << len(accepted)) - 1, sum(1 << slot for slot in free), offers.slots, None, None, None))
        assert self.pool.owned == set(self.owners)
        self.rollback = next((load for _, load in rejected if not any(canceled(load.entry, r) for r in (red, *self.red_history))), None)
        current = [(lane, decode_load(values, lane)) for lane in range(3) if values[f"io_req_{lane}_valid"]]
        def order(left, right):
            a, b = left[1].entry.rob, right[1].entry.rob
            return 0 if a == b else (1 if is_younger(a, b) else -1)
        self.saved = tuple(sorted(current, key=cmp_to_key(order)))
        self.red_history = [red, self.red_history[0]]
        self.s2, self.s1 = self.s1, matches
        return {"reset": False, "before": [asdict(tx) for tx in before.values()], "allocated": [asdict(tx) for tx in allocations],
                "filtered": [{"lane": lane, "load": asdict(load), "reason": why} for lane, load, why in filtered],
                "rejected": [asdict(load) for _, load in rejected], "offered": offers.offered, "free": free,
                "entry_changes": changes, "internal_accept": before[chosen].uid if accept else None,
                "internal_slot": chosen if accept else None, "external_accept": old_pipe[1] if external_fire else None,
                "response_uids": response_uids, "wakes": {kind: before[slot].uid for kind, slot in wakes.items() if slot is not None},
                "matches": matches, "pipe_before": old_pipe[1] if old_pipe else None, "pipe_after": self.pipe[1] if self.pipe else None,
                "rollback": asdict(self.rollback) if self.rollback else None}
