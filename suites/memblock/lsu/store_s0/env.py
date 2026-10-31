"""Environment and independent model for StoreUnitS0.

S0 is a *fixed-latency* stage: the generated RTL has no ``pipeOut_ready`` port,
``io_stin_ready`` is simply ``~unalignTail_valid``, and ``pipeOutValid`` is
``arb.valid && !kill``. A beat therefore occupies the output for exactly one
cycle. The model mirrors that relation without copying the RTL expressions:

* arbitration: unalign tail (priority 0) over scalar issue (priority 1);
* scalar field synthesis: ``vaddr = src0 + sext(imm)``, ``size = fuOpType[3:1]``,
  ``mask = genVWmask128(vaddr, size)`` unless the opcode is a CBO (full line);
* ``illegalIssue``: ``!sqIdx.withInPhysicalQueue(sqDeqPtr)``;
* ``align`` / ``unalignHead`` / ``cross4KPage``: byte-offset arithmetic in the
  page, with CBO and prefetch forced aligned and a tail inheriting the head's
  page-crossing verdict;
* ``isAddrReadyHead``: full 8-bit SqPtr equality against ``sqAddrReadyPtr``;
* TLB request: driven combinationally by the arbitration result, not by the
  pipeline register and not gated by ``kill``.

Contract: docs/contracts/store-s0.md
"""
from __future__ import annotations

import random

from suites.memblock.lsu.pointers import (
    LEVEL_FLUSH,
    LEVEL_FLUSH_AFTER,
    rob_need_flush,
    sq_in_physical_queue,
)

INSTR_TYPE_SCALAR = 1
INSTR_TYPE_PREFETCH = 4

ENTRANCE_UNALIGN_TAIL = 0x1
ENTRANCE_PREFETCH = 0x2
ENTRANCE_SCALAR_ISSUE = 0x8

PIPE_FIELDS = {
    "entrance": 4,
    "accessType_instrType": 3,
    "accessType_isCbo": 1,
    "accessType_isCboNoZero": 1,
    "uop_exceptionVec_19": 1,
    "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_fuOpType": 12,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1,
    "uop_sqIdx_value": 6,
    "vaddr": 50,
    "fullva": 64,
    "size": 3,
    "mask": 16,
    "illegalIssue": 1,
    "ssid": 6,
    "storeSetHit": 1,
    "align": 1,
    "unalignHead": 1,
    "cross4KPage": 1,
    "isAddrReadyHead": 1,
}

# Fields supplied directly by the unalign-tail source (everything but the four
# derived flags, which S0 computes or inherits separately).
TAIL_FIELDS = (
    "accessType_instrType", "accessType_isCbo", "accessType_isCboNoZero",
    "uop_exceptionVec_19", "uop_isRVC", "uop_ftqPtr_flag", "uop_ftqPtr_value",
    "uop_ftqOffset", "uop_fuOpType", "uop_robIdx_flag", "uop_robIdx_value",
    "uop_robIdx_isFormer", "uop_sqIdx_first_flag", "uop_sqIdx_second_flag",
    "uop_sqIdx_value", "vaddr", "fullva", "size", "mask",
)

STIN_FIELDS = {
    "fuOpType": 12,
    "src_0": 64,
    "imm": 64,
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "isRVC": 1,
    "ftqIdx_flag": 1,
    "ftqIdx_value": 6,
    "ftqOffset": 5,
    "storeSetHit": 1,
    "ssid": 6,
    "sqIdx_first_flag": 1,
    "sqIdx_second_flag": 1,
    "sqIdx_value": 6,
}

TLB_FIELDS = ("vaddr", "fullva", "checkfullva", "cmd", "hyperinst", "isPrefetch",
              "debug_robIdx_flag", "debug_robIdx_value", "debug_robIdx_isFormer")

# MemorySize.ByteOffset: B=0, H=1, W=3, D=7, and Q ("b1??") = 15.
BYTE_OFFSET = {0: 0, 1: 1, 2: 3, 3: 7, 4: 15, 5: 15, 6: 15, 7: 15}
# genVWmask128: B=0x1, H=0x3, W=0xF, D=0xFF, Q ("b1??") = 0xFFFF.
MASK_BASE = {0: 0x1, 1: 0x3, 2: 0xF, 3: 0xFF,
             4: 0xFFFF, 5: 0xFFFF, 6: 0xFFFF, 7: 0xFFFF}


def sign_extend(value: int, bits: int, target_bits: int) -> int:
    sign = 1 << (bits - 1)
    value &= (1 << bits) - 1
    return (value - (1 << bits)) if (value & sign) else value


def gen_vwmask128(vaddr: int, size: int) -> int:
    """``genVWmask128``: size base shifted by the 16B offset, truncated to 16 bits."""
    base = MASK_BASE[size]
    return (base << (vaddr & 0xF)) & 0xFFFF


def aligned_for_size(vaddr: int, size: int) -> bool:
    """B always aligned; H/W/D need ``vaddr & (2**size - 1) == 0``; Q needs vaddr[3:0]==0."""
    if size == 0:
        return True
    if size >= 4:
        return (vaddr & 0xF) == 0
    return (vaddr & ((1 << size) - 1)) == 0


def scalar_stage_fields(stin: dict) -> dict:
    fu = stin["fuOpType"]
    size = (fu >> 1) & 0x7
    vaddr = (stin["src_0"] + sign_extend(stin["imm"], 12, 64)) & ((1 << 50) - 1)
    fullva = (stin["src_0"] + sign_extend(stin["imm"], 12, 64)) & ((1 << 64) - 1)
    is_cbo = fu & 0x1
    is_cbo_no_zero = is_cbo & (1 if ((fu >> 1) & 0x7) != 3 else 0)
    return {
        "entrance": ENTRANCE_SCALAR_ISSUE,
        "accessType_instrType": INSTR_TYPE_SCALAR,
        "accessType_isCbo": is_cbo,
        "accessType_isCboNoZero": is_cbo_no_zero,
        "uop_exceptionVec_19": 0,   # no port on the scalar arbitration input
        "uop_isRVC": stin["isRVC"],
        "uop_ftqPtr_flag": stin["ftqIdx_flag"],
        "uop_ftqPtr_value": stin["ftqIdx_value"],
        "uop_ftqOffset": stin["ftqOffset"],
        "uop_fuOpType": fu,
        "uop_robIdx_flag": stin["robIdx_flag"],
        "uop_robIdx_value": stin["robIdx_value"],
        "uop_robIdx_isFormer": stin["robIdx_isFormer"],
        "uop_sqIdx_first_flag": stin["sqIdx_first_flag"],
        "uop_sqIdx_second_flag": stin["sqIdx_second_flag"],
        "uop_sqIdx_value": stin["sqIdx_value"],
        "vaddr": vaddr,
        "fullva": fullva,
        "size": size,
        "mask": 0xFFFF if is_cbo else gen_vwmask128(vaddr, size),
        "ssid": stin["ssid"],
        "storeSetHit": stin["storeSetHit"],
    }


def tail_stage_fields(tail: dict) -> dict:
    fields = {name: tail[name] for name in TAIL_FIELDS}
    fields["entrance"] = ENTRANCE_UNALIGN_TAIL
    fields["ssid"] = 0        # no ssid port on the tail source
    fields["storeSetHit"] = 0  # no storeSetHit port on the tail source
    return fields


def derive_stage_flags(fields: dict, tail_cross4kpage: int, deq: tuple, addr_ready: tuple) -> dict:
    vaddr = fields["vaddr"]
    size = fields["size"]
    instr_type = fields["accessType_instrType"]
    is_cbo = fields["accessType_isCbo"]
    is_prefetch = bool((instr_type >> 2) & 1)
    is_tail = fields["entrance"] == ENTRANCE_UNALIGN_TAIL
    force_aligned = bool(is_cbo or is_prefetch)

    in_page = (vaddr & 0xFFF) + BYTE_OFFSET[size]
    cross16 = ((in_page >> 4) & 1) != ((vaddr >> 4) & 1)
    cross4k_from_addr = bool((in_page >> 12) & 1)

    if force_aligned:
        align = 1
    elif is_tail:
        align = 0
    else:
        align = 1 if aligned_for_size(vaddr, size) else 0
    unalign_head = 0 if force_aligned or is_tail else (1 if cross16 else 0)
    cross4k = 0 if force_aligned else (tail_cross4kpage if is_tail else int(cross4k_from_addr))

    sq = (fields["uop_sqIdx_first_flag"], fields["uop_sqIdx_second_flag"],
          fields["uop_sqIdx_value"])
    is_addr_ready_head = 1 if sq == addr_ready else 0
    in_queue = sq_in_physical_queue(*sq, *deq)
    return {
        "illegalIssue": 0 if in_queue else 1,
        "align": align,
        "unalignHead": unalign_head,
        "cross4KPage": cross4k,
        "isAddrReadyHead": is_addr_ready_head,
    }


def derive_tlb_request(fields: dict) -> dict:
    fu = fields["uop_fuOpType"]
    instr_type = fields["accessType_instrType"]
    is_cbo_no_zero = fields["accessType_isCboNoZero"]
    return {
        "vaddr": fields["vaddr"],
        "fullva": fields["fullva"],
        "checkfullva": 1 if ((instr_type >> 1) & 1) | (instr_type & 1) else 0,
        "cmd": (0 << 1) | (0 if is_cbo_no_zero else 1),
        "hyperinst": 1 if ((fu >> 6) & 1) and not (fu & 1) else 0,
        "isPrefetch": (instr_type >> 2) & 1,
        "debug_robIdx_flag": fields["uop_robIdx_flag"],
        "debug_robIdx_value": fields["uop_robIdx_value"],
        "debug_robIdx_isFormer": fields["uop_robIdx_isFormer"],
    }


class StoreS0Model:
    def __init__(self) -> None:
        self.valid = 0
        self.bits: dict[str, int] | None = None

    def arb(self, stin_valid: int, stin: dict, tail_valid: int, tail: dict,
            tail_cross4kpage: int, deq: tuple, addr_ready: tuple) -> dict:
        stin = mask_fields(stin, STIN_FIELDS)
        tail = mask_fields(tail, {name: PIPE_FIELDS[name] for name in TAIL_FIELDS})
        deq = (deq[0] & 1, deq[1] & 1, deq[2] & 0x3F)
        addr_ready = (addr_ready[0] & 1, addr_ready[1] & 1, addr_ready[2] & 0x3F)
        if tail_valid:
            fields = tail_stage_fields(tail)
        elif stin_valid:
            fields = scalar_stage_fields(stin)
        else:
            fields = None
        if fields is None:
            return {"arb_valid": 0, "fields": None, "stin_ready": 0 if tail_valid else 1}
        derived = derive_stage_flags(fields, tail_cross4kpage, deq, addr_ready)
        stage = dict(fields)
        stage.update(derived)
        return {"arb_valid": 1, "fields": stage,
                "stin_ready": 0 if tail_valid else 1}

class StoreS0Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.stin_valid = dut.io_stin_valid
        self.stin = {name: getattr(dut, f"io_stin_bits_{name}") for name in STIN_FIELDS}
        self.stin_ready = dut.io_stin_ready
        self.tail_valid = dut.io_unalignTail_valid
        self.tail = {name: getattr(dut, f"io_unalignTail_bits_{name}") for name in TAIL_FIELDS}
        self.tail_cross4kpage = dut.io_unalignTail_bits_cross4KPage
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_level = dut.io_redirect_bits_level
        self.redirect_flag = dut.io_redirect_bits_robIdx_flag
        self.redirect_value = dut.io_redirect_bits_robIdx_value
        self.redirect_former = dut.io_redirect_bits_robIdx_isFormer
        self.deq = (dut.io_sqDeqPtr_first_flag, dut.io_sqDeqPtr_second_flag,
                    dut.io_sqDeqPtr_value)
        self.addr_ready = (dut.io_sqAddrReadyPtr_first_flag,
                           dut.io_sqAddrReadyPtr_second_flag,
                           dut.io_sqAddrReadyPtr_value)
        self.out_valid = dut.io_pipeOut_valid
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}") for name in PIPE_FIELDS}
        self.tlb_valid = dut.io_tlbReq_valid
        self.tlb = {name: getattr(dut, f"io_tlbReq_bits_{name}") for name in TLB_FIELDS}
        self.model = StoreS0Model()
        self.cycles = 0
        self.last_inputs = None

    # ------------------------------------------------------------------ reset
    def reset(self, cycles: int = 4) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model = StoreS0Model()
        self.drive(0, blank(STIN_FIELDS), 0, blank(TAIL_FIELDS), 0, (0, 0, 0), (0, 0, 0),
                   {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0})
        self.dut.Step(1)

    # ------------------------------------------------------------------ drive
    def drive(self, stin_valid: int, stin: dict, tail_valid: int, tail: dict,
              tail_cross4kpage: int, deq: tuple, addr_ready: tuple,
              redirect: dict) -> None:
        self.stin_valid.Set(1 if stin_valid else 0)
        for name, signal in self.stin.items():
            signal.Set(int(stin.get(name, 0)))
        self.tail_valid.Set(1 if tail_valid else 0)
        for name, signal in self.tail.items():
            signal.Set(int(tail.get(name, 0)))
        self.tail_cross4kpage.Set(int(tail_cross4kpage))
        self.deq[0].Set(int(deq[0]))
        self.deq[1].Set(int(deq[1]))
        self.deq[2].Set(int(deq[2]))
        self.addr_ready[0].Set(int(addr_ready[0]))
        self.addr_ready[1].Set(int(addr_ready[1]))
        self.addr_ready[2].Set(int(addr_ready[2]))
        self.redirect_valid.Set(1 if redirect["valid"] else 0)
        self.redirect_level.Set(int(redirect["level"]))
        self.redirect_flag.Set(int(redirect["flag"]))
        self.redirect_value.Set(int(redirect["value"]))
        self.redirect_former.Set(int(redirect["former"]))
        self.last_inputs = (stin_valid, dict(stin), tail_valid, dict(tail),
                            tail_cross4kpage, deq, addr_ready, redirect)

    # -------------------------------------------------------------- one cycle
    def cycle(self, stin_valid: int, stin: dict, tail_valid: int, tail: dict,
              tail_cross4kpage: int, deq: tuple, addr_ready: tuple,
              redirect: dict, context: str = "cycle") -> dict:
        """Drive one cycle, clock it, then check both output classes.

        Picker only re-evaluates combinational logic inside ``Step``, so the
        order is: drive -> Step -> read. After the edge the combinational
        outputs reflect this cycle's inputs, and the registered outputs reflect
        the state produced by this cycle's edge.
        """
        arb = self.model.arb(stin_valid, stin, tail_valid, tail, tail_cross4kpage,
                             deq, addr_ready)
        # Predicted post-edge state.
        next_valid = 0
        next_bits = None
        if arb["arb_valid"]:
            fields = arb["fields"]
            killed = rob_need_flush(fields["uop_robIdx_flag"],
                                    fields["uop_robIdx_value"],
                                    fields["uop_robIdx_isFormer"], redirect)
            if not killed:
                next_valid = 1
                next_bits = fields

        self.drive(stin_valid, stin, tail_valid, tail, tail_cross4kpage, deq,
                   addr_ready, redirect)
        self.dut.Step(1)

        got_ready = int(self.stin_ready.value)
        if got_ready != arb["stin_ready"]:
            raise AssertionError(
                f"{context}: stin.ready {got_ready} != {arb['stin_ready']} "
                f"(tail_valid={tail_valid})")
        got_tlb_valid = int(self.tlb_valid.value)
        if got_tlb_valid != arb["arb_valid"]:
            raise AssertionError(
                f"{context}: tlbReq.valid {got_tlb_valid} != {arb['arb_valid']}")
        if arb["arb_valid"]:
            want_tlb = derive_tlb_request(arb["fields"])
            for name, signal in self.tlb.items():
                got = int(signal.value)
                if got != want_tlb[name]:
                    raise AssertionError(
                        f"{context}: tlbReq.bits.{name} {got:#x} != {want_tlb[name]:#x}")

        got_valid = int(self.out_valid.value)
        if got_valid != next_valid:
            raise AssertionError(
                f"{context}: pipeOut.valid {got_valid} != {next_valid}")
        got_bits = {name: int(signal.value) for name, signal in self.out.items()}
        if next_valid:
            for name, got in got_bits.items():
                if got != next_bits[name]:
                    raise AssertionError(
                        f"{context}: pipeOut.bits.{name} {got:#x} != {next_bits[name]:#x}")

        if self.coverage is not None and next_valid:
            self.coverage.observe(out_valid=got_valid, out_bits=got_bits,
                                  arb=arb, redirect=redirect)

        self.model.valid = next_valid
        self.model.bits = next_bits
        self.cycles += 1
        return {"valid": got_valid, "bits": got_bits if got_valid else None,
                "stin_ready": got_ready, "tlb_valid": got_tlb_valid}


def mask_fields(values: dict, widths: dict) -> dict:
    """Clamp every field to its declared port width (the DUT cannot see more)."""
    return {name: int(values.get(name, 0)) & ((1 << width) - 1)
            for name, width in widths.items()}


def blank(fields) -> dict[str, int]:
    return {name: 0 for name in fields}


def random_stin(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in STIN_FIELDS.items()}
    values.update(overrides)
    return values


def random_tail(rng: random.Random, **overrides) -> dict:
    values = {}
    for name in TAIL_FIELDS:
        width = PIPE_FIELDS[name]
        values[name] = rng.randrange(1 << width)
    values.update(overrides)
    return values
