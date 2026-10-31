"""Staged public producer history and semantic child-reference composition.

The real DUT retains its real children. This reference records STA/S2/STD
events and scalar circular positions, never reads internal registers/arrays.
Byte safety and a separate UID actor remain independent completion obligations.
"""
from dataclasses import asdict, dataclass, replace

from suites.memblock.lsq.deq.model import DeqModel
from suites.memblock.lsq.deq.types import DeqControl, Inputs as DeqInputs, SecondPage as DeqPage, Store as DeqStore
from suites.memblock.lsq.forward.model import ForwardModel
from suites.memblock.lsq.forward.types import Inputs as ForwardInputs, SecondPage as ForwardPage, Store as ForwardStore
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.unalign.model import UnalignModel
from suites.memblock.lsq.unalign.types import Inputs as UqInputs, Recovery, Request, serial


def before(left, right):
    return 0 < (right - left) % 256 < 128


@dataclass
class Entry:
    vaddr: int = 0
    page: int = 0
    size: int = 0
    mask: int = 0
    data: int = 0
    memory: int = 0
    cbo: int = 0
    hyper: bool = False
    address_ready: bool = False
    data_ready: bool = False
    cross: bool = False
    cache_operation: bool = False
    waiting_s2: bool = False
    exception: bool = False
    committed: bool = False
    finished: bool = False

    def reset_control(self):
        return replace(self, address_ready=False, data_ready=False, cross=False, cache_operation=False,
                       waiting_s2=False, exception=False, committed=False, finished=False)

    def deq(self):
        return DeqStore(self.vaddr, self.page, self.mask, self.data, self.memory, self.cbo, self.hyper, self.data_ready,
                        self.address_ready, False, self.cross, self.exception, self.committed, self.cache_operation)

    def forward(self):
        return ForwardStore(self.size, self.vaddr, self.page, self.mask, self.data, self.cbo, self.data_ready, self.address_ready, self.cross, self.cache_operation)


class PsqModel:
    def __init__(self):
        self.entries = [Entry() for _ in range(64)]
        self.head = self.read = self.commit = self.address_ready = self.data_ready = 0
        self.upper = self.virtual_count = self.credit = None
        self.address_vector = self.data_vector = (False,) * 64
        self.retired = self.precommit = self.redirect = 0
        self.precommit_valid = self.redirect_valid = False
        self.pending_s2 = (None, None)
        self.deq, self.forward, self.uq = DeqModel(), ForwardModel(), UnalignModel()
        self.edges = 0

    def state(self, inp):
        bank = [entry.reset_control() for entry in self.entries] if inp.reset else self.entries
        head, read = (0, 0) if inp.reset else (self.head, self.read)
        uq_head = self.uq.order[0].request if self.uq.order and not inp.reset else None
        page = DeqPage(True, uq_head.paddr & ~4095, uq_head.sq) if uq_head else DeqPage()
        din = DeqInputs(stores=tuple(bank[(read + lane) % 64].deq() for lane in range(2)),
                        dequeue_controls=tuple(DeqControl(False, bank[(head + lane) % 64].committed, bank[(head + lane) % 64].finished) for lane in range(2)),
                        sbuffer_ready=inp.sbuffer_ready, read_ptr=SqPtr.encode(read), dequeue_ptrs=(SqPtr.encode(head), SqPtr.encode(head + 1)),
                        rob=inp.rob, valid_count=(serial(inp.enqueue) - head) % 256, uncache_ready=inp.uncache_ready,
                        uncache_ack_valid=inp.uncache_ack_valid, uncache_ack_to_load=inp.uncache_ack_to_load, uncache_response=inp.uncache_response,
                        cache_ready=inp.cache_ready, cache_response=inp.cache_response, cache_denied=inp.cache_denied, cache_corrupt=inp.cache_corrupt,
                        writeback_ready=inp.writeback_ready, sbuffer_empty=inp.sbuffer_empty, second_page=page, reset=inp.reset)
        pages = [ForwardPage() for _ in range(2)]
        if not inp.reset:
            for owner in self.uq.order:
                pages[owner.slot] = ForwardPage(True, owner.request.paddr & ~4095, owner.request.sq)
        fin = ForwardInputs(inp.queries, inp.translations, tuple(entry.forward() for entry in bank), tuple(pages), SqPtr.encode(head), SqPtr.encode(self.upper if self.upper is not None else 64))
        uin = UqInputs(tuple(Request(req.valid, req.sq, req.paddr) for req in inp.second_pages), SqPtr.encode(0 if inp.reset else self.address_ready),
                       bool(self.deq.expected(din)[0]["io_fromUnalignQueue_ready"]), Recovery(inp.redirect_valid and not inp.reset, inp.redirect), inp.reset)
        return bank, head, read, din, fin, uin

    def expected(self, inp):
        bank, head, read, din, fin, uin = self.state(inp)
        deq_values, masks = self.deq.expected(din)
        # These are internal-to-parent interfaces, not PSQ public observations.
        private = {"io_rdataPtrMoveCnt", "io_sqDeqCnt", "io_fromUnalignQueue_ready"}
        values = {key: value for key, value in deq_values.items() if key not in private and not key.startswith("io_deqPtrExtNext_")}
        for key, value in self.forward.expected(fin).items():
            values[key.replace("io_query_", "io_forward_", 1)] = value
        uq_values = self.uq.expected(uin)
        for lane in range(2):
            values[f"io_fromStoreUnit_unalignQueueReq_{lane}_ready"] = uq_values[f"io_fromStaS1_{lane}_ready"] if not inp.reset else int(inp.second_pages[lane].sq == SqPtr())
        def pointer(prefix, position):
            ptr = SqPtr.encode(position)
            values.update({prefix + "first_flag": int(ptr.first), prefix + "second_flag": int(ptr.second), prefix + "value": ptr.value})
        pointer("io_sqDeqPtr_", head)
        pointer("io_toLoadQueue_stAddrReadySqPtr_", 0 if inp.reset else self.address_ready)
        pointer("io_toLoadQueue_stDataReadySqPtr_", 0 if inp.reset else self.data_ready)
        if self.upper is not None:
            pointer("io_physicalUpperSqIdx_", self.upper)
        for slot in range(64):
            values[f"io_toLoadQueue_stAddrReadyVec_{slot}"] = int(not inp.reset and self.address_vector[slot])
            values[f"io_toLoadQueue_stDataReadyVec_{slot}"] = int(not inp.reset and self.data_vector[slot])
        commit = 0 if inp.reset else self.commit
        values["io_empty"] = int(head == commit == (0 if inp.reset else self.retired))
        if self.virtual_count is not None:
            values["io_full"] = int(self.virtual_count > 128)
        if self.credit is not None:
            values["io_sqDeq_valid"] = int(bool(self.credit))
            if self.credit:
                values["io_sqDeq_bits"] = self.credit
        return values, masks

    def safety(self, inp, observed):
        fin = self.state(inp)[4]
        renamed = {key.replace("io_forward_", "io_query_", 1): value for key, value in observed.items() if key.startswith("io_forward_")}
        return self.forward.check_physical_safety(fin, renamed)

    def advance(self, inp):
        bank, head, read, din, fin, uin = self.state(inp)
        plan = self.deq.plan(din)
        upper = self.upper if self.upper is not None else 64
        redirect = self.redirect
        clean = self.redirect_valid and before(redirect, upper)
        def canceled(slot):
            # A scalar slot represents exactly one current physical generation.
            offset = (slot - head) % 64
            position = (head + offset) % 256
            return clean and not before(position, redirect)
        def next_ready(position, field):
            if self.redirect_valid and not before(position, self.redirect):
                return self.redirect
            count = 0
            for offset in range(4):
                pos = (position + offset) % 256
                entry = bank[pos % 64]
                if pos == upper or not getattr(entry, field) or clean and not entry.committed:
                    break
                count += 1
            return (position + count) % 256
        new_addr = next_ready(0 if inp.reset else self.address_ready, "address_ready")
        new_data = next_ready(0 if inp.reset else self.data_ready, "data_ready")
        commit = 0 if inp.reset else self.commit
        permitted = []
        for offset in range(4):
            pos = (commit + offset) % 256
            entry = bank[pos % 64]
            allowed = self.precommit_valid and before(pos, self.precommit) or before(pos, self.retired)
            if pos == upper or not allowed or entry.exception or entry.waiting_s2 or not (entry.address_ready and entry.data_ready):
                break
            permitted.append(pos)
        credit_was_known = self.deq.credit_known
        change = self.deq.advance(din)
        uq_change = self.uq.advance(uin)
        forward_change = self.forward.advance(fin)
        updated = [replace(entry) for entry in bank]
        sta, std, s2 = {}, {}, {}
        for lane, address in enumerate(inp.addresses):
            if address.valid:
                assert address.slot not in sta, "two STA lanes cannot update the same physical owner"
                if not canceled(address.slot):
                    sta[address.slot] = (lane, address)
        for lane, data in enumerate(inp.data):
            if data.valid:
                assert data.slot not in std, "two STD lanes cannot update the same physical owner"
                if not canceled(data.slot):
                    std[data.slot] = (lane, data)
        for lane, slot in enumerate(self.pending_s2):
            if slot is not None and not canceled(slot):
                s2.setdefault(slot, []).append(inp.attributes[lane])
        retired_slots = {(head + offset) % 64 for offset in range(plan["deq_move"])}
        for slot, entry in enumerate(updated):
            if slot in sta:
                _, address = sta[slot]
                entry.address_ready = address.last and not address.tlb_miss
                entry.cross, entry.cache_operation = address.unaligned and address.cross_word, bool(address.fu_op & 1)
                entry.waiting_s2, entry.finished, entry.hyper = True, False, address.hyper
                if entry.cache_operation:
                    entry.cbo = address.fu_op >> 1 & 7
            elif slot in retired_slots or canceled(slot):
                entry.address_ready = False
            if slot in std:
                entry.data_ready = True
            elif slot in retired_slots or canceled(slot):
                entry.data_ready = False
            if slot in s2:
                entry.exception = bank[slot].exception or any(attr.exception for attr in s2[slot])
                last = next((attr for attr in s2[slot] if attr.last), None)
                if last is not None:
                    entry.memory = (int(not last.memory) << 2) | (int(last.mmio) << 1) | int(last.nc or not last.memory)
                    if slot not in sta:
                        entry.waiting_s2 = False
            elif slot in retired_slots or canceled(slot):
                entry.exception = False
            if slot == read % 64 and slot not in sta:
                nc_finish = inp.uncache_ack_valid and not inp.uncache_ack_to_load and bank[slot].memory in (1, 5)
                if change["wb_fire"] or nc_finish:
                    entry.finished = True
        # Data/address payload writes are unconditional valid-only events in
        # the fixed producer interface; validity and cancel are separate.
        for address in inp.addresses:
            if address.valid and (not address.last or not address.cross_word):
                entry = updated[address.slot]
                entry.vaddr, entry.page, entry.size = address.vaddr, address.paddr // 4096, address.size
                entry.mask = (1 << (1 << min(address.size, 4))) - 1
        for data in inp.data:
            if data.valid:
                updated[data.slot].data = 0 if data.fu_op & 1 and data.fu_op >> 1 & 7 == 3 else data.data
        for pos in permitted:
            updated[pos % 64].committed = True
        for slot in retired_slots:
            updated[slot].committed = False
        self.entries = [entry.reset_control() for entry in updated] if inp.reset else updated
        self.address_vector = tuple(entry.address_ready for entry in bank) if not inp.reset else (False,) * 64
        self.data_vector = tuple(entry.data_ready for entry in bank) if not inp.reset else (False,) * 64
        self.head = 0 if inp.reset else (head + plan["deq_move"]) % 256
        self.read = 0 if inp.reset else (read + plan["read_move"]) % 256
        self.commit = 0 if inp.reset else (commit + len(permitted)) % 256
        self.address_ready, self.data_ready = (0, 0) if inp.reset else (new_addr, new_data)
        # The child's no-reset credit is unknown before its first empty
        # clock. Parent RegNext(credit/nextPtr) sees that OLD unknown once;
        # it is not a real completion or a reason to skip later checks.
        self.upper = (head + plan["deq_move"] + 64) % 256 if credit_was_known else None
        self.virtual_count = (serial(inp.enqueue) - head) % 256
        self.credit = plan["deq_move"] if credit_was_known else None
        self.pending_s2 = tuple(address.slot if lane in [item[0] for item in sta.values()] and not address.tlb_miss else None for lane, address in enumerate(inp.addresses))
        self.retired, self.precommit, self.redirect = serial(inp.retired), serial(inp.precommit), serial(inp.redirect)
        self.precommit_valid, self.redirect_valid = inp.precommit_valid, inp.redirect_valid
        self.edges += 1
        return {"reset": inp.reset, "writeout": change, "uq": uq_change, "forward": forward_change,
                "sta_slots": sorted(sta), "std_slots": sorted(std), "s2_slots": sorted(s2), "permitted": permitted,
                "cancelled_slots": [slot for slot in range(64) if canceled(slot)] if not inp.reset else [],
                "head_before": head, "head_after": self.head, "read_before": read, "read_after": self.read}
