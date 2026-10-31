"""Scalar SQ order, semantic byte records and staged public-input snapshots.

No internal masks/registers are read. In addition to detailed timing checks,
physical-byte safety is checked independently of the virtual overlap domain.
"""
from dataclasses import asdict, dataclass

from suites.memblock.lsq.raw.types import SqPtr
from .types import byte_count, sq_serial


def after(left, right):
    delta = (sq_serial(left) - sq_serial(right)) % 256
    if delta == 128:
        raise ValueError("ambiguous SQ half-ring comparison")
    return 0 < delta < 128


@dataclass(frozen=True)
class Job:
    uid: int
    lane: int
    query: object
    older: tuple
    outside: bool


@dataclass(frozen=True)
class Result:
    job: Job
    virtual: frozenset
    potential: frozenset
    selected: object
    source: object
    source_sq: object
    strict_wait: bool
    page_hazard: bool
    paddr: int
    bank: tuple


class ForwardModel:
    def __init__(self):
        self.sequence = self.edges = 0
        self.stage1, self.stage2 = [None] * 3, [None] * 3

    def new_job(self, query, lane, inp):
        if not query.valid:
            return None
        age = (sq_serial(query.sq) - sq_serial(inp.dequeue)) % 256
        limit = (sq_serial(inp.upper) - sq_serial(inp.dequeue)) % 256
        # This is an EXCLUSIVE Load boundary anchored to the real dequeue,
        # not an arbitrary two-pointer comparison. A full128-flow SQ may
        # precede the Load (Dispatch.scala719 uses end>head, including full).
        # Keep after()'s general half-ring ambiguity rejection unchanged.
        if not 0 <= age <= 128 or not 0 <= limit <= 64:
            raise ValueError("query and physical window outside documented SQ age domain")
        older = tuple(((sq_serial(inp.dequeue) + offset) % 64, SqPtr.encode(sq_serial(inp.dequeue) + offset)) for offset in range(min(age, limit)))
        self.sequence += 1
        return Job(self.sequence, lane, query, older, age > limit)

    def select(self, job, inp):
        if job is None or inp.translations[job.lane].kill:
            return None
        query = job.query
        paddr = inp.translations[job.lane].paddr
        if query.vaddr % 4096 != paddr % 4096:
            raise ValueError("non-killed translation must retain its query's page offset")
        virtual, potential = [], []
        start, end = query.vaddr % 16, query.vaddr % 16 + byte_count(query.size) - 1
        for slot, ptr in job.older:
            store = inp.stores[slot]
            same = store.vaddr // 16 == query.vaddr // 16
            following = store.cross_word and store.vaddr // 4096 == query.vaddr // 4096 and store.vaddr // 16 + 1 == query.vaddr // 16
            line = store.cache_operation and store.vaddr // 64 == query.vaddr // 64
            relative_start = start + (16 if following else 0)
            relative_end = end + (16 if following else 0)
            overlaps = store.vaddr % 16 <= relative_end and store.vaddr % 16 + store.length - 1 >= relative_start
            if store.address_ready and overlaps:
                potential.append(slot)
                if same or following or line:
                    virtual.append(slot)
        chosen = virtual[-1] if virtual else None
        selected = inp.stores[chosen] if chosen is not None else None
        identity = next((ptr for slot, ptr in job.older if slot == chosen), None)
        hazard = any(page.valid and after(query.sq, page.sq) and page.paddr // 16 == paddr // 16 for page in inp.second_pages)
        strict_wait = job.outside or any(not inp.stores[slot].address_ready for slot, _ in job.older)
        return Result(job, frozenset(virtual), frozenset(potential), chosen, selected, identity, strict_wait, hazard, paddr, inp.stores)

    def expected(self, inp):
        if self.edges < 2:
            return {}
        result = {}
        for lane, answer in enumerate(self.stage2):
            prefix = f"io_query_{lane}_s2Resp_"
            result[prefix + "valid"] = int(answer is not None)
            if answer is None:
                continue
            query, store = answer.job.query, answer.source
            start = query.vaddr % 16
            end = start + byte_count(query.size) - 1
            full = store is not None and store.vaddr % 16 <= start and store.vaddr % 16 + store.length - 1 >= end
            safe = len(answer.virtual) <= 1 or full
            bad_cbo = store is not None and store.cache_operation and store.cbo != 3
            data_invalid = store is not None and (not store.data_ready or bad_cbo)
            physical = {slot for slot in answer.potential if
                        inp.stores[slot].paddr // 16 == answer.paddr // 16 or
                        inp.stores[slot].cross_word and inp.stores[slot].paddr // 16 + 1 == answer.paddr // 16 or
                        inp.stores[slot].cache_operation and inp.stores[slot].paddr // 64 == answer.paddr // 64}
            precise_wait = query.wait and not after(inp.dequeue, query.wait_sq) and (
                not after(inp.upper, query.wait_sq) or not inp.stores[query.wait_sq.value].address_ready)
            address_invalid = answer.strict_wait if query.strict else precise_wait
            result.update({prefix + "bits_forwardInvalid": int(not safe or bad_cbo or answer.page_hazard),
                           prefix + "bits_matchInvalid": int(physical != answer.virtual and safe),
                           prefix + "bits_addrInvalid_valid": int(address_invalid), prefix + "bits_dataInvalid_valid": int(data_invalid)})
            def pointer(suffix, ptr):
                result.update({prefix + suffix + "first_flag": int(ptr.first), prefix + suffix + "second_flag": int(ptr.second), prefix + suffix + "value": ptr.value})
            if address_invalid:
                pointer("bits_addrInvalid_bits_", SqPtr.encode(sq_serial(query.sq) - 1) if query.strict else query.wait_sq)
            if data_invalid:
                pointer("bits_dataInvalid_bits_", answer.source_sq)
            for byte in range(16):
                relative = (byte - (store.vaddr % 16 if store else 0)) % 16
                forwarded = store is not None and start <= byte <= end and bool(store.mask >> relative & 1)
                result[prefix + f"bits_forwardMask_{byte}"] = int(forwarded)
                if forwarded and not data_invalid:
                    result[prefix + f"bits_forwardData_{byte}"] = store.data >> (8 * relative) & 255
        return result

    def check_physical_safety(self, inp, observed):
        """Never accept stale bytes just because a VA-relative mask excluded PA aliases.

Applies the architectural byte-origin property to a stable store bank. Live
bank changes still receive detailed staged checks, not an invented atomicity
guarantee. Returning unused data under a replay/dependency is not a success.
"""
        checked = []
        for lane, answer in enumerate(self.stage2):
            if answer is None or answer.bank != inp.stores:
                continue
            prefix = f"io_query_{lane}_s2Resp_"
            blocked = any(observed[prefix + suffix] for suffix in ("bits_forwardInvalid", "bits_matchInvalid", "bits_addrInvalid_valid", "bits_dataInvalid_valid"))
            if blocked:
                continue
            for byte in range(16):
                if not observed[prefix + f"bits_forwardMask_{byte}"]:
                    continue
                address = answer.paddr // 16 * 16 + byte
                sources = []
                for slot, ptr in answer.job.older:
                    store = answer.bank[slot]
                    if not store.address_ready:
                        continue
                    offset = address - store.paddr
                    if store.cache_operation:
                        hit = address // 64 == store.paddr // 64
                    else:
                        hit = 0 <= offset < store.length and bool(store.mask >> offset & 1)
                    if hit:
                        sources.append((slot, store, offset))
                assert sources, ("forward-physical-byte-safety", answer.job.uid, lane, byte, "no physical producer")
                slot, newest, offset = sources[-1]
                assert slot == answer.selected and newest.data_ready and (not newest.cache_operation or newest.cbo == 3), (
                    "forward-physical-byte-safety", answer.job.uid, lane, byte, "selected", answer.selected, "newest physical", slot)
                expected_byte = newest.data >> ((offset % 16) * 8) & 255
                assert observed[prefix + f"bits_forwardData_{byte}"] == expected_byte, (
                    "forward-physical-byte-safety", answer.job.uid, lane, byte, "expected", expected_byte)
                checked.append((answer.job.uid, byte, slot))
        return checked

    def advance(self, inp):
        old = self.stage1
        self.stage2 = [self.select(job, inp) for job in old]
        self.stage1 = [self.new_job(query, lane, inp) for lane, query in enumerate(inp.queries)]
        self.edges += 1
        return {"accepted": [asdict(job) for job in self.stage1 if job],
                "killed": [asdict(job) for lane, job in enumerate(old) if job and inp.translations[lane].kill],
                "responses": [{"uid": answer.job.uid, "lane": answer.job.lane, "selected": answer.selected,
                               "virtual": sorted(answer.virtual), "potential": sorted(answer.potential), "strict_wait": answer.strict_wait,
                               "page_hazard": answer.page_hazard, "paddr": answer.paddr,
                               "source": asdict(answer.source) if answer.source is not None else None} for answer in self.stage2 if answer]}
