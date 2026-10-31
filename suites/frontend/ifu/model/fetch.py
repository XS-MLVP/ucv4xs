"""Architecture-level fetch-window model for the IFU top level.

The model builds the byte stream the ICache would deliver for a small program,
reconstructs the instructions the IFU should enqueue (including RVC expansion,
cross-block assembly and RVC-map boundaries), aligns them to the IBuffer write
banks, and asks the PredChecker model which lanes are enqueued and whether the
FTQ must be redirected.  It deliberately does not reproduce pipeline timing;
the test driver owns handshakes and compares the eventual enqueue beat.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

from suites.frontend.ifu.model.boundary import SLOTS as BOUNDARY_SLOTS
from suites.frontend.ifu.model.boundary import BoundaryInput
from suites.frontend.ifu.model.boundary import predict as boundary_predict
from suites.frontend.ifu.model.pred_checker import CONDITIONAL
from suites.frontend.ifu.model.pred_checker import DIRECT
from suites.frontend.ifu.model.pred_checker import INDIRECT
from suites.frontend.ifu.model.pred_checker import NONE
from suites.frontend.ifu.model.pred_checker import POP
from suites.frontend.ifu.model.pred_checker import PUSH
from suites.frontend.ifu.model.pred_checker import Instr as CheckInstr
from suites.frontend.ifu.model.pred_checker import Request as CheckRequest
from suites.frontend.ifu.model.pred_checker import predict as pred_predict
from suites.frontend.ifu.model.rvc import expand
from suites.frontend.ifu.model.isa import is_compressed

LANES = 36
PC_BITS = 51  # GuardedPc: byte address plus overflow/guard bit
PC_MASK = (1 << PC_BITS) - 1


@dataclass
class Inst:
    word: int
    is_rvc: int
    pc: int
    slot: int
    block: int
    start_offset: int
    end_offset: int
    cross: int
    pred_taken: int = 0
    invalid_taken: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    raw_data: int = 0
    out_data: int = 0
    ill: int = 0
    branch_type: int = NONE
    ras_action: int = 0
    jump_offset: int = 0
    truncated: int = 0


@dataclass
class Window:
    instructions: list[Inst]
    size0: int
    size1: int
    split: int
    block1_valid: int
    half0: int
    half1: int
    spec_count: int
    spec_count0: int
    map: int
    line0: list[int]
    line1: list[int]
    line_offset0: int
    line_offset1: int
    ftq0: tuple[int, int]
    ftq1: tuple[int, int]
    exc0: int = 0
    exc1: int = 0
    gp0: int = 0
    gp1: int = 0
    vs0: int = 0
    vs1: int = 0
    pmp0: int = 0
    pbmt0: int = 0
    satp0: int = 0
    backend_exc0: int = 0
    paddr0: int = 0
    taken0_valid: int = 0
    taken1_valid: int = 0
    start0_pc: int = 0
    start1_pc: int = 0


def xor_fold(value: int, width: int) -> int:
    """XOR all ``width``-bit chunks of a zero-extended value (MemPredPCWidth)."""

    chunks = (value.bit_length() + width - 1) // width
    chunks = max(1, chunks)
    folded = 0
    for index in range(chunks):
        folded ^= (value >> (index * width)) & ((1 << width) - 1)
    return folded


def _sext(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def branch_info(word: int, is_rvc: int) -> tuple[int, int, int]:
    """Return (branch type, ras action, byte jump displacement)."""

    if is_rvc:
        quadrant = word & 3
        f3 = (word >> 13) & 7
        bit12 = (word >> 12) & 1
        rd = (word >> 7) & 31
        rs2 = (word >> 2) & 31
        if quadrant == 1 and f3 == 5:  # c.j
            offset = (bit12 << 11) | (((word >> 8) & 1) << 10) | (((word >> 9) & 3) << 8) \
                | (((word >> 6) & 1) << 7) | (((word >> 7) & 1) << 6) \
                | (((word >> 2) & 1) << 5) | (((word >> 11) & 1) << 4) \
                | (((word >> 3) & 7) << 1)
            return DIRECT, 0, _sext(offset, 12)
        if quadrant == 1 and f3 in (6, 7):  # c.beqz / c.bnez
            offset = (bit12 << 8) | (((word >> 5) & 3) << 6) | (((word >> 2) & 1) << 5) \
                | (((word >> 10) & 3) << 3) | (((word >> 3) & 3) << 1)
            return CONDITIONAL, 0, _sext(offset, 9)
        if quadrant == 2 and f3 == 4:
            if bit12 == 1 and rs2 == 0 and rd != 0:
                return INDIRECT, PUSH, 0
            if bit12 == 0 and rs2 == 0 and rd != 0:
                pop = POP if rd in (1, 5) else 0
                return INDIRECT, pop, 0
        return NONE, 0, 0
    opcode = word & 0x7F
    rd = (word >> 7) & 31
    rs1 = (word >> 15) & 31
    if opcode == 0x6F:
        imm = ((word >> 31) & 1) << 20 | ((word >> 12) & 0xFF) << 12 \
            | ((word >> 20) & 1) << 11 | ((word >> 21) & 0x3FF) << 1
        push = PUSH if rd in (1, 5) else 0
        return DIRECT, push, _sext(imm, 21)
    if opcode == 0x67:
        pop = POP if rs1 in (1, 5) and rd != rs1 else 0
        push = PUSH if rd in (1, 5) else 0
        return INDIRECT, pop | push, 0
    if opcode == 0x63:
        imm = ((word >> 31) & 1) << 12 | ((word >> 7) & 1) << 11 \
            | ((word >> 25) & 0x3F) << 5 | ((word >> 8) & 0xF) << 1
        return CONDITIONAL, 0, _sext(imm, 13)
    return NONE, 0, 0


def build_window(program: list[tuple[int, int]], base_pc: int, *,
                 split: int | None = None, taken0: int = 0, taken1: int = 0,
                 ftq0: tuple[int, int] = (0, 0), ftq1: tuple[int, int] = (0, 1),
                 line_offset0: int | None = None, line_offset1: int | None = None,
                 exc0: int = 0, exc1: int = 0, gp0: int = 0, gp1: int = 0,
                 vs0: int = 0, vs1: int = 0, pmp0: int = 0, pbmt0: int = 0,
                 satp0: int = 0, backend_exc0: int = 0, paddr0: int = 0,
                 truncate: int = 0, carry_word: int = 0) -> Window:
    """Build one 32-slot fetch window from architectural instructions.

    ``program`` is a list of ``(word, is_rvc)`` in execution order.  ``split``
    is the number of halfword slots owned by the first fetch block; ``None``
    means a single block.  ``taken0/taken1`` mark a predicted-taken last
    instruction of the respective block (the block's size still ends at that
    instruction's last halfword).
    """

    if base_pc % 2:
        raise ValueError("fetch base PC must be 2-byte aligned")
    if not program:
        raise ValueError("fetch window needs at least one instruction")
    for name, value in (("taken0", taken0), ("taken1", taken1)):
        if value not in (0, 1):
            raise ValueError(f"{name} must be 0 or 1")
    if carry_word and (carry_word & 3) != 3:
        raise ValueError("carry_word must be a full-width instruction (low bits 11)")
    if carry_word and len(program) + 1 > 32:
        raise ValueError("a carry-in occupies slot 0, leaving 31 slots")
    for name, value in (("exc0", exc0), ("exc1", exc1), ("pmp0", pmp0), ("pbmt0", pbmt0)):
        if value not in (0, 1, 2, 3, 4, 5) and name.startswith("exc"):
            raise ValueError(f"{name} must be a 3-bit exception code")
        if value not in (0, 1, 2, 3) and not name.startswith("exc"):
            raise ValueError(f"{name} must fit two bits")
    if base_pc < 0 or base_pc >= (1 << PC_BITS):
        raise ValueError("base PC must fit the guarded PC width")
    carry_in = int(carry_word != 0)
    if line_offset0 is None:
        line_offset0 = (base_pc >> 1) & 31
    starts: list[tuple[int, int, int]] = []  # slot, word, is_rvc
    slot = 1 if carry_in else 0
    truncated = False
    for word, rvc in program:
        if rvc and not is_compressed(word):
            raise ValueError(f"{word:#x} is not compressed")
        if not rvc and is_compressed(word):
            raise ValueError(f"{word:#x} is compressed")
        starts.append((slot, word & (0xFFFF if rvc else 0xFFFFFFFF), int(rvc)))
        slot += 1 if rvc else 2
        if slot > 32:
            if not truncate:
                raise ValueError("fetch window exceeds 32 halfword slots")
            # The window ends after the first half of this full-width
            # instruction; the second half belongs to the next fetch block.
            truncated = True
            slot = 32
            break
    total = slot
    if split is None:
        split = total
    if not 1 <= split <= total or total > 32:
        raise ValueError("invalid split for the 32-slot window")
    if truncated and split != total:
        raise ValueError("a truncated window cannot own a second block")
    block1_valid = int(split < total)
    size0 = split
    size1 = total - split
    if line_offset1 is None:
        line_offset1 = ((base_pc >> 1) + split) & 31

    map_bits = 0
    for start, _, rvc in starts:
        if rvc:
            map_bits |= 1 << start
    line0 = [0] * 32
    line1 = [0] * 32
    raw_slots = [0] * total
    if carry_in:
        raw_slots[0] = (carry_word >> 16) & 0xFFFF
    for start, word, rvc in starts:
        raw_slots[start] = word & 0xFFFF
        if not rvc and start + 1 < total:
            raw_slots[start + 1] = (word >> 16) & 0xFFFF
    for index in range(size0):
        line0[(line_offset0 + index) & 31] = raw_slots[index]
    for index in range(size1):
        line1[(line_offset1 + index) & 31] = raw_slots[split + index]

    # The first instruction of each block starts at slot 0 of that block, or
    # block 1 starts with the second half of a cross-block RVI.
    boundary_input = BoundaryInput(
        block0_size=size0,
        taken_valid=taken0,
        taken_offset=size0 - 1,
        block1_valid=block1_valid,
        maybe_rvc=map_bits,
        block_sel=(((1 << BOUNDARY_SLOTS) - 1) ^ ((1 << size0) - 1)) if block1_valid else 0,
        first_instr_is_half_rvi=carry_in,
        total_end_pos=(total - 1) & 0x1F,
    )
    boundary = boundary_predict(boundary_input)
    half0 = int(bool(boundary.first_end_is_half_rvi))

    last_start0 = max((start for start, _, _ in starts if start < split), default=None)
    last_start1 = max((start for start, _, _ in starts if start >= split), default=None)
    offsets = {0: 0} if carry_in else {}
    instructions: list[Inst] = []
    if carry_in:
        raw = carry_word & 0xFFFFFFFF
        instructions.append(Inst(
            word=raw, is_rvc=0, pc=(base_pc - 2) & PC_MASK, slot=0, block=0,
            start_offset=0, end_offset=0, cross=0, pred_taken=0, invalid_taken=0,
            ftq_flag=ftq0[0], ftq_value=ftq0[1], raw_data=raw, out_data=raw, ill=0,
            branch_type=NONE, ras_action=0, jump_offset=0))
    for index, (start, word, rvc) in enumerate(starts):
        block = 0 if start < split else 1
        start_offset = start if block == 0 else start - split
        cross = int(block == 0 and not rvc and start == split - 1 and block1_valid
                    and not taken0)
        if cross:
            lo = line0[(line_offset0 + start_offset) & 31]
            hi = line1[line_offset1]
            raw = lo | (hi << 16)
        elif block == 0:
            at = (line_offset0 + start_offset) & 31
            lo = line0[at]
            hi = line0[(at + 1) & 31]
            raw = lo | (hi << 16)
        else:
            at = (line_offset1 + start_offset) & 31
            lo = line1[at]
            hi = line1[(at + 1) & 31]
            raw = lo | (hi << 16)
        word16 = raw & 0xFFFF
        expansion = expand(word16 if rvc else raw, fs_is_off=False)
        out = raw if (rvc and expansion.ill) else (expansion.bits if rvc else raw)
        pred_taken = int((taken0 and start == last_start0) or (taken1 and start == last_start1))
        invalid_taken = int(pred_taken and (
            (block == 0 and taken0 and start == split - 1 and half0) or
            (block == 1 and taken1 and start == total - 1 and boundary.total_end_is_half_rvi)))
        btype, ras, jump = branch_info(word16 if rvc else raw, rvc)
        end_offset = 0 if cross else ((start_offset + (0 if rvc else 1)) & 0x1F)
        lane = start if not carry_in else start + 0
        instructions.append(Inst(
            word=raw, is_rvc=rvc, pc=(base_pc + 2 * start) & PC_MASK, slot=start,
            block=block, start_offset=start_offset, end_offset=end_offset, cross=cross,
            pred_taken=pred_taken, invalid_taken=invalid_taken,
            ftq_flag=(ftq1 if (block or cross) else ftq0)[0],
            ftq_value=(ftq1 if (block or cross) else ftq0)[1],
            raw_data=raw, out_data=out, ill=int(expansion.ill),
            branch_type=btype, ras_action=ras,
            jump_offset=jump & PC_MASK,
        ))
    end_mask = boundary.instr_end_mask
    total_range = (1 << total) - 1
    first_range = (1 << size0) - 1
    spec_count = sum(end_mask[slot] & ((total_range >> slot) & 1) for slot in range(32))
    spec_count0 = sum(end_mask[slot] & ((first_range >> slot) & 1) for slot in range(32))
    if truncated:
        instructions[-1] = replace(instructions[-1], truncated=1)
    return Window(instructions=instructions, size0=size0, size1=size1, split=split,
                  block1_valid=block1_valid, half0=half0,
                  half1=int(boundary.total_end_is_half_rvi),
                  taken0_valid=taken0, taken1_valid=taken1,
                  start0_pc=base_pc, start1_pc=base_pc + 2 * split,
                  spec_count=spec_count,
                  spec_count0=spec_count0, map=map_bits, line0=line0, line1=line1,
                  line_offset0=line_offset0, line_offset1=line_offset1,
                  ftq0=ftq0, ftq1=ftq1, exc0=exc0, exc1=exc1,
                  gp0=gp0, gp1=gp1, vs0=vs0, vs1=vs1,
                  pmp0=pmp0, pbmt0=pbmt0, satp0=satp0,
                  backend_exc0=backend_exc0, paddr0=paddr0)


@dataclass
class Beat:
    valid: int
    enq: int
    valid_mask: int
    instrs: list[int]
    is_rvc: list[int]
    pcs: list[int]
    ftq: list[tuple[int, int]]
    end_offsets: list[int]
    pred_taken: list[int]
    foldpc: list[int]
    is_last: list[int]
    prev_count: int
    exception_type: int
    exception_mask: int
    exception_cross_page: int
    is_backend_exception: int
    has_satp_flush: int
    triggered: list[int] = field(default_factory=lambda: [15] * LANES)
    gp_addr_wen: int = 0
    gp_addr: int = 0
    gp_ftq: int = 0
    gp_for_vs: int = 0


def aligned_lanes(window: Window, shift: int) -> tuple[Beat, object, dict, list, list]:
    lanes: list[CheckInstr] = [CheckInstr() for _ in range(LANES)]
    mapping: dict[int, Inst] = {}
    # A cache-reported exception ends the fetch at the faulting instruction:
    # a first-block exception keeps one instruction; a second-block exception
    # keeps all of block 0 plus the first instruction that consumes block 1.
    if window.exc0:
        limit = 1
    elif window.exc1:
        limit = window.spec_count0 + 1
    else:
        limit = len(window.instructions)
    for order, inst in enumerate(window.instructions[:limit]):
        lane = shift + order
        if lane >= LANES - 1:
            raise ValueError("aligned instruction exceeds the enqueue lanes")
        mapping[lane] = inst
        lanes[lane] = CheckInstr(
            # A window that ends inside a full-width instruction cannot enqueue
            # that instruction: its upper half belongs to the next fetch.
            valid=0 if inst.truncated else 1, is_rvc=inst.is_rvc, is_pred_taken=inst.pred_taken,
            invalid_taken=inst.invalid_taken, block_sel=inst.block,
            end_offset=inst.end_offset, is_cross_block=inst.cross,
            branch_type=inst.branch_type, ras_action=inst.ras_action,
            pc=inst.pc, jump_offset=inst.jump_offset,
        )
    prediction = pred_predict(CheckRequest(valid=1, instrs=lanes))
    enq = list(prediction.fixed_instr_valid)
    enq[LANES - 1] = 0
    select = [(lanes[i].block_sel or lanes[i].is_cross_block) for i in range(LANES)]
    is_last = []
    for index in range(LANES):
        if index == LANES - 1:
            is_last.append(enq[index])
        else:
            is_last.append(int(enq[index] ^ ((select[index] == select[index + 1]) & enq[index + 1])))
    instrs = [0] * LANES
    is_rvc = [0] * LANES
    pcs = [0] * LANES
    ftq = [(0, 0)] * LANES
    end_offsets = [0] * LANES
    pred_taken = [0] * LANES
    foldpc = [0] * LANES
    valid_mask = 0
    for lane, inst in mapping.items():
        if not inst.truncated:
            valid_mask |= 1 << lane
    for lane, inst in mapping.items():
        instrs[lane] = inst.out_data
        is_rvc[lane] = inst.is_rvc
        pcs[lane] = inst.pc
        ftq[lane] = (inst.ftq_flag, inst.ftq_value)
        end_offsets[lane] = inst.end_offset
        pred_taken[lane] = inst.pred_taken
        foldpc[lane] = xor_fold(inst.pc >> 1, 10)
    ill_mask = 0
    for lane, inst in mapping.items():
        if inst.ill:
            ill_mask |= 1 << lane
    rvc_mask = sum((enq[i] & 1) << i for i in range(LANES)) & ill_mask
    first_has_ill = any((rvc_mask >> i) & 1 for i, inst in mapping.items()
                        if not (inst.block or inst.cross))
    if window.exc0:
        exception_type = window.exc0
        exception_mask = 1 << shift
    elif first_has_ill:
        exception_type = 4  # illegal instruction
        exception_mask = rvc_mask
    elif window.exc1:
        exception_type = window.exc1
        exception_mask = 1 << (shift + window.spec_count0)
    elif rvc_mask:
        exception_type = 4
        exception_mask = rvc_mask
    else:
        exception_type = 0
        exception_mask = 0
    exception_cross_page = int(
        (window.exc0 and False) or
        (not window.exc0 and bool(window.exc1) and bool(window.half0)))
    gp_wen, gp_addr, gp_ftq, gp_for_vs = 0, 0, 0, 0
    if window.exc0 == 2:
        gp_wen, gp_addr, gp_ftq, gp_for_vs = 1, window.gp0, window.ftq0[1], window.vs0
    elif window.exc1 == 2:
        gp_wen, gp_addr, gp_ftq, gp_for_vs = 1, window.gp1, window.ftq1[1], window.vs1
    beat = Beat(
        valid=int(any(lanes[i].valid for i in range(LANES))),
        enq=sum((enq[i] & 1) << i for i in range(LANES)),
        valid_mask=valid_mask,
        instrs=instrs, is_rvc=is_rvc, pcs=pcs, ftq=ftq, end_offsets=end_offsets,
        pred_taken=pred_taken,
        foldpc=foldpc, is_last=is_last,
        prev_count=(limit if (window.exc0 or window.exc1) else window.spec_count),
        exception_type=exception_type, exception_mask=exception_mask,
        exception_cross_page=exception_cross_page,
        # Both markers belong to the first instruction: ICacheMeta only
        # carries them for block 0, and the IFU must forward them unchanged
        # so the backend can classify the trap correctly.
        is_backend_exception=int(window.backend_exc0),
        has_satp_flush=int(window.satp0),
        gp_addr_wen=gp_wen, gp_addr=gp_addr, gp_ftq=gp_ftq, gp_for_vs=gp_for_vs,
    )
    return beat, prediction, mapping, enq, lanes
