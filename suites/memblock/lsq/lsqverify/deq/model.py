"""Public-input staged writeout reference; no DUT internal reads.

Sbuffer words are built from scalar byte addresses, with an ordered two-place
ledger and credit on actual consumption. Cache errors are retained until WB
fire, deliberately NOT following the fixed RTL's known early-clear behavior.
"""
from dataclasses import asdict, dataclass

from lsqverify.raw.types import SqPtr


def serial(ptr):
    return 128 * int(ptr.first) + 64 * int(ptr.second) + ptr.value


@dataclass(frozen=True)
class Segment:
    sq: int
    part: int
    vaddr: int
    paddr: int
    data: int
    mask: int
    wline: bool
    credit: bool


def word(store, sq, part, second_page=None, *, credit=True):
    va = store.vaddr // 16 * 16 + part * 16
    pa = store.paddr // 16 * 16 + part * 16 if second_page is None else second_page
    data = mask = 0
    for source_byte in range(16):
        address = store.vaddr + source_byte
        if store.byte_mask >> source_byte & 1 and va <= address < va + 16:
            byte = address - va
            mask |= 1 << byte
            data |= (store.data >> (8 * source_byte) & 255) << (8 * byte)
    return Segment(sq % 256, part, va, pa, data, mask, store.cache_operation and store.cbo == 3, credit)


class DeqModel:
    def __init__(self):
        self.words = []
        self.uncache = self.cbo = "idle"
        self.denied = self.corrupt = self.force_write = False
        self.completed_sq = set()
        self.credit_known = False
        self.credit_lanes = (None, None)

    def plan(self, inp):
        queue = [] if inp.reset else self.words
        cbo = "idle" if inp.reset else self.cbo
        uncache = "idle" if inp.reset else self.uncache
        head, second = inp.stores
        fires = tuple(lane < len(queue) and inp.sbuffer_ready[lane] for lane in range(2))
        capacity = 2 - len(queue) + sum(fires)
        zero = head.cache_operation and head.cbo == 3
        cacheable = head.memory_type & 3 == 0
        first_valid = cacheable and head.committed and not head.inactive and (not head.cache_operation or cbo == "zero" and not queue) and (not head.cross_word or not queue)
        offers = []
        sq = serial(inp.read_ptr)
        if first_valid:
            if head.cross_word:
                page = inp.second_page.paddr if inp.second_page.valid and inp.second_page.sq == inp.read_ptr else None
                offers = [word(head, sq, 0, credit=False), word(head, sq, 1, page)]
            else:
                offers = [word(head, sq, 0, credit=not zero)]
                if not head.cache_operation and second.memory_type & 3 == 0 and not second.cache_operation and second.committed and not second.inactive and not second.cross_word:
                    offers.append(word(second, sq + 1, 0))
        accepted = offers[:capacity]
        pipeline = 0 if zero else (int(bool(accepted)) if head.cross_word else len(accepted))
        # A trailing inactive item may wait rather than get optimal throughput.
        # The inactive prefix is based on SQ-read positions, not Sbuffer
        # segments: a split uses both segments but advances only the first SQ
        # read position. Its following inactive entry waits for a later cycle.
        inactive = [store.committed and store.inactive and not queue for store in inp.stores]
        inactive_moves = int(inactive[0]) + int(inactive[1] and (inactive[0] or len(accepted) == 2 and not head.cross_word))
        wb = cbo == "wb" or uncache == "wb"
        nc_ack = uncache == "ack" and inp.uncache_ack_valid and not inp.uncache_ack_to_load
        read_move = pipeline + inactive_moves + int(nc_ack or wb and inp.writeback_ready)
        # Completion is an AGE PREFIX, not a sum of untagged credits and
        # both heads' finish bits. A later NC/IO finish cannot free an old
        # normal word still stalled at Sbuffer, nor borrow its credit.
        base = serial(inp.dequeue_ptrs[0])
        controls = {serial(ptr): ctrl for ptr, ctrl in zip(inp.dequeue_ptrs, inp.dequeue_controls)}
        deq_move = 0
        first_inactive = False
        for lane in range(2):
            identity = (base + lane) % 256
            ctrl = controls.get(identity)
            inactive = bool(ctrl and ctrl.committed and ctrl.inactive)
            # An inactive follower can join a lane-0 normal credit, but a
            # split tail in Sbuffer lane 1 leaves it for the next head cycle.
            # This is a permitted one-cycle wait, not an ownership failure.
            inactive_ready = inactive and (not lane or first_inactive or self.credit_lanes[0] == base)
            complete = identity in self.completed_sq or bool(ctrl and ctrl.committed and ctrl.finished)
            if not (inactive_ready or complete):
                break
            deq_move += 1
            first_inactive = inactive
        return {"queue": queue, "cbo": cbo, "uncache": uncache, "fires": fires, "accepted": accepted,
                "read_move": read_move, "deq_move": deq_move, "wb": wb, "nc_ack": nc_ack}

    def expected(self, inp, *, after=False):
        p = self.plan(inp)
        values, masks = {}, {}
        def rob(prefix):
            values.update({prefix + "flag": int(inp.rob.flag), prefix + "value": inp.rob.value, prefix + "isFormer": int(inp.rob.former)})
        for lane in range(2):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            values[prefix + "valid"] = int(lane < len(p["queue"]))
            if lane < len(p["queue"]):
                seg = p["queue"][lane]
                values.update({prefix + "bits_" + key: int(value) for key, value in (("vaddr", seg.vaddr), ("addr", seg.paddr), ("data", seg.data), ("mask", seg.mask), ("wline", seg.wline))})
                masks[prefix + "bits_data"] = sum(255 << (8 * byte) for byte in range(16) if seg.mask >> byte & 1)
        head = inp.stores[0]
        values.update({"io_toUncacheBuffer_req_valid": int(p["uncache"] == "req"), "io_toDCache_req_valid": int(p["cbo"] == "req"),
                       "io_toDCache_resp_ready": int(p["cbo"] == "resp"), "io_toRob_mmioBusy": int(p["uncache"] != "idle"),
                       "io_writeBack_valid": int(p["wb"]), "io_exceptionInfo_valid": int(p["wb"]),
                       "io_sbufferCtrl_req_flush": int(p["cbo"] == "flush"), "io_sbufferCtrl_req_forceWrite": int(self.force_write and not inp.reset),
                       "io_fromUnalignQueue_ready": int(inp.second_page.sq == inp.read_ptr and bool(p["accepted"])), "io_rdataPtrMoveCnt": p["read_move"]})
        if self.credit_known:
            move = p["deq_move"]
            if after:
                # Post-edge leaf pins still describe the OLD external deq
                # window. Its combinational finished/inactive controls stay
                # asserted while the registered Sbuffer pulse has changed.
                # Check this transient waveform separately, NOT as permission
                # to retire an owner. The next pre-edge (and parent advance)
                # always uses the independent identity-prefix plan above.
                inactive = tuple(c.committed and c.inactive for c in inp.dequeue_controls)
                move = sum(identity is not None for identity in self.credit_lanes)
                move += int(inactive[0]) + int(inactive[1] and (inactive[0] or self.credit_lanes[0] is not None))
                move += sum(c.committed and c.finished and not c.inactive for c in inp.dequeue_controls)
            values["io_sqDeqCnt"] = move
            for lane, ptr in enumerate(inp.dequeue_ptrs):
                nxt = SqPtr.encode(serial(ptr) + move)
                prefix = f"io_deqPtrExtNext_{lane}_"
                values.update({prefix + "first_flag": int(nxt.first), prefix + "second_flag": int(nxt.second), prefix + "value": nxt.value})
        if p["uncache"] == "req":
            prefix = "io_toUncacheBuffer_req_bits_"
            # Little-endian bytes in the addressed 64-bit bus word.
            bus_data = bus_mask = 0
            for byte in range(16):
                address = head.vaddr + byte
                if head.byte_mask >> byte & 1 and address // 8 == head.vaddr // 8:
                    bus_mask |= 1 << (address % 8)
                    bus_data |= (head.data >> (8 * byte) & 255) << (8 * (address % 8))
            values.update({prefix + "addr": head.paddr, prefix + "vaddr": head.vaddr, prefix + "data": bus_data, prefix + "mask": bus_mask,
                           prefix + "id": inp.read_ptr.value, prefix + "nc": int(head.memory_type in (1, 5)), prefix + "memBackTypeMM": int(not head.memory_type & 4)})
            masks[prefix + "data"] = sum(255 << (8 * byte) for byte in range(8) if bus_mask >> byte & 1)
            rob(prefix + "robIdx_")
        if p["cbo"] == "req":
            values.update({"io_toDCache_req_bits_address": head.paddr, "io_toDCache_req_bits_opcode": head.cbo})
        if p["wb"]:
            for prefix in ("io_writeBack_bits_", "io_exceptionInfo_bits_"):
                rob(prefix + "robIdx_")
                values.update({prefix + "exceptionVec_7": int(self.denied), prefix + "exceptionVec_19": int(self.corrupt)})
            values.update({"io_writeBack_bits_debugInfo_isMMIO": int(bool(head.memory_type & 2)), "io_writeBack_bits_debugInfo_isNCIO": int(head.memory_type in (1, 5)),
                           "io_exceptionInfo_bits_vaddr": head.vaddr, "io_exceptionInfo_bits_isHyper": int(head.hyper)})
        return values, masks

    def advance(self, inp):
        p = self.plan(inp)
        if inp.reset:
            aborted = [asdict(seg) for seg in self.words]
            self.__init__()
            self.credit_known = True
            return {"accepted": [], "consumed": [], "reset_aborted_segments": aborted, "read_move": 0, "deq_move": 0, "wb_fire": False, "nc_ack": False}
        consumed = [p["queue"][lane] for lane, fire in enumerate(p["fires"]) if fire]
        head = inp.stores[0]
        can_handle = head.committed and head.address_valid and head.data_valid and not head.exception
        if self.uncache == "idle" and can_handle and head.memory_type & 3 and not head.cache_operation:
            self.uncache = "req"
        elif self.uncache == "req" and inp.uncache_ready:
            self.uncache = "ack" if head.memory_type in (1, 5) else "resp"
        elif p["nc_ack"]:
            self.uncache = "idle"
        elif self.uncache == "resp" and inp.uncache_response:
            self.uncache, self.denied, self.corrupt = "wb", False, False
        elif self.uncache == "wb" and inp.writeback_ready:
            self.uncache = "idle"
        if self.cbo == "idle" and can_handle and head.cache_operation:
            self.cbo = "zero" if head.cbo == 3 else "flush"
        elif self.cbo == "zero" and any(seg.wline and seg.sq == serial(inp.read_ptr) for seg in consumed):
            self.cbo = "flush"
        elif self.cbo == "flush" and inp.sbuffer_empty and not self.words:
            self.cbo = "wb" if head.cbo == 3 else "req"
        elif self.cbo == "req" and inp.cache_ready:
            self.cbo = "resp"
        elif self.cbo == "resp" and inp.cache_response:
            self.cbo, self.denied, self.corrupt = "wb", inp.cache_denied, inp.cache_corrupt
        elif self.cbo == "wb" and inp.writeback_ready:
            self.cbo = "idle"
        if p["wb"] and inp.writeback_ready:
            self.denied = self.corrupt = False
        self.force_write = inp.valid_count >= 60 or inp.valid_count >= 55 and self.force_write
        self.completed_sq.difference_update(serial(ptr) for ptr in inp.dequeue_ptrs[:p["deq_move"]])
        self.completed_sq.update(seg.sq for seg in consumed if seg.credit)
        self.credit_lanes = tuple(p["queue"][lane].sq if p["fires"][lane] and p["queue"][lane].credit else None for lane in range(2))
        self.credit_known = True
        self.words = self.words[len(consumed):] + p["accepted"]
        assert len(self.words) <= 2
        return {"accepted": [asdict(seg) for seg in p["accepted"]], "consumed": [asdict(seg) for seg in consumed], "reset_aborted_segments": [],
                "read_move": p["read_move"], "deq_move": p["deq_move"], "wb_fire": bool(p["wb"] and inp.writeback_ready), "nc_ack": bool(p["nc_ack"])}
