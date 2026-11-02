"""Bind redundant oracle descriptors to the byte stream driven at the boundary.

This admission check is not another pipeline oracle. It walks source bytes,
without build_window, Boundary.predict, DUT observations or expected enqueue
data. The agent separately binds an alleged carry low half to its issued input
history; no stateless schema can prove that preceding transaction existed.
"""
from suites.frontend.ifu.model.fetch import Inst, PC_MASK, branch_info
from suites.frontend.ifu.model.rvc import expand


def check_window_description(window):
    w = window
    total = w.size0 + w.size1
    first = w.instructions[0]
    carry = first.pc != w.start0_pc
    if carry and first.pc != (w.start0_pc - 2) & PC_MASK:
        raise ValueError('instruction descriptor carry PC must precede the actual high half by two bytes')
    starts, ends = [], [0] if carry else []
    cursor = int(carry)
    while cursor < total:
        block = int(cursor >= w.size0)
        offset = cursor - (w.size0 if block else 0)
        line = w.line1 if block else w.line0
        at = ((w.line_offset1 if block else w.line_offset0) + offset) & 31
        rvc = int((line[at] & 3) != 3)
        starts.append((cursor, block, offset, at, rvc))
        if cursor + 1 - rvc < total:
            ends.append(cursor + 1 - rvc)
        cursor += 2 - rvc
    start_slots = {slot for slot, *_ in starts}
    half0 = int(w.size0 - 1 in start_slots and not ((w.map >> (w.size0 - 1)) & 1))
    half1 = int(total - 1 in start_slots and not ((w.map >> (total - 1)) & 1))
    derived = dict(half0=half0, half1=half1, spec_count=len(ends),
                   spec_count0=sum(slot < w.size0 for slot in ends))
    for field, expected in derived.items():
        if getattr(w, field) != expected:
            raise ValueError(f'derived window {field} disagrees with the driven byte stream')
    expected_instructions = []
    if carry:
        # Only the low half is a declaration here. _check_carry must prove its
        # input UID/PC. The high half is always this request's actual first byte pair.
        low = first.raw_data & 0xffff
        if low & 3 != 3:
            raise ValueError('instruction descriptor carry must complete a full-width instruction')
        raw = low | (w.line0[w.line_offset0] << 16)
        branch, ras, jump = branch_info(raw, 0)
        expected_instructions.append(Inst(word=raw, is_rvc=0, pc=(w.start0_pc - 2) & PC_MASK,
            slot=0, block=0, start_offset=0, end_offset=0, cross=0,
            pred_taken=int(bool(w.taken0_valid and w.size0 == 1)),
            ftq_flag=w.ftq0[0], ftq_value=w.ftq0[1], raw_data=raw, out_data=raw,
            branch_type=branch, ras_action=ras, jump_offset=jump & PC_MASK))
    last = {block: max((slot for slot, owner, *_ in starts if owner == block), default=None)
            for block in (0, 1)}
    for slot, block, offset, at, rvc in starts:
        line = w.line1 if block else w.line0
        cross = int(not block and not rvc and slot == w.size0 - 1
                    and w.block1_valid and not w.taken0_valid)
        # Even an RVC descriptor keeps the adjacent raw halfword. On a taken
        # low-half boundary that adjacent value is not a completed instruction;
        # it remains the block0 physical line, not speculative block1 bytes.
        high = w.line1[w.line_offset1] if cross else line[(at + 1) & 31]
        raw = line[at] | (high << 16)
        decoded = expand(raw & 0xffff if rvc else raw, fs_is_off=False)
        branch, ras, jump = branch_info(raw & 0xffff if rvc else raw, rvc)
        taken = int(bool((w.taken1_valid if block else w.taken0_valid) and slot == last[block]))
        invalid = int(bool(taken and (slot == total - 1 and half1 if block
                                     else slot == w.size0 - 1 and half0)))
        ptr = w.ftq1 if block or cross else w.ftq0
        pc = ((w.start1_pc if block else w.start0_pc) + 2 * offset) & PC_MASK
        expected_instructions.append(Inst(word=raw, is_rvc=rvc, pc=pc, slot=slot, block=block,
            start_offset=offset, end_offset=0 if cross else (offset + 1 - rvc) & 31,
            cross=cross, pred_taken=taken, invalid_taken=invalid, ftq_flag=ptr[0], ftq_value=ptr[1],
            raw_data=raw, out_data=raw if not rvc or decoded.ill else decoded.bits, ill=int(decoded.ill),
            branch_type=branch, ras_action=ras, jump_offset=jump & PC_MASK,
            truncated=int(not rvc and slot == total - 1)))
    if len(w.instructions) != len(expected_instructions):
        raise ValueError('instruction descriptor count disagrees with the driven byte stream')
    for index, (declared, expected) in enumerate(zip(w.instructions, expected_instructions)):
        if declared != expected:
            fields = tuple(name for name in Inst.__dataclass_fields__
                           if getattr(declared, name) != getattr(expected, name))
            raise ValueError(f'instruction descriptor {index} disagrees with the driven byte stream: {fields}')
