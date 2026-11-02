"""Independent instruction-stream/peer answers and consumed-field comparisons."""
from toffee import Scoreboard

from dataclasses import replace

from suites.frontend.ifu.model.fetch import PC_MASK, aligned_lanes, branch_info, xor_fold
from suites.frontend.ifu.model.pred_checker import DIRECT, POP
from suites.frontend.ifu.model.rvc import expand

from .types import Enqueue, GpaWrite, Redirect


def cached_expectation(request, shift, *, fs_is_off=0):
    expected, prediction, mapping, enq, lanes = aligned_lanes(request.window, shift)
    w = request.window
    # MemPredPC uses virtual address bits; GuardedPc's overflow bookkeeping bit
    # is not part of that address. This does not waive R-08's lossy redirect PC.
    folded = list(expected.foldpc)
    for lane, inst in mapping.items():
        folded[lane] = xor_fold((inst.pc & ((1 << 50) - 1)) >> 1, 10)
    expected = replace(expected, foldpc=folded)
    # A predicted block ending on a low half contains only its preceding
    # complete instructions. The redirect oracle still sees the faulty start.
    if not w.exc0 and w.taken0_valid and w.half0:
        count = w.spec_count0
        mapping = dict(list(mapping.items())[:count])
        mask = sum(1 << lane for lane in mapping if lanes[lane].valid)
        expected = replace(expected, valid_mask=mask, enq=expected.enq & mask, prev_count=count)
    if fs_is_off:
        instructions = list(expected.instrs)
        illegal = 0
        for lane, inst in mapping.items():
            decoded = expand(inst.raw_data, fs_is_off=True)
            instructions[lane] = inst.raw_data if decoded.ill else decoded.bits
            if decoded.ill and (expected.enq >> lane) & 1:
                illegal |= 1 << lane
        if illegal and not w.exc0 and (not w.exc1 or any(
                (illegal >> lane) & 1 and not (inst.block or inst.cross) for lane, inst in mapping.items())):
            expected = replace(expected, exception_type=4, exception_mask=illegal)
        expected = replace(expected, instrs=instructions)
    return expected, prediction, mapping, enq, lanes


def check_enqueue(observed, request, shift, *, trigger_actions=None, prev_count=None, fs_is_off=0):
    if not isinstance(observed, Enqueue):
        raise TypeError('IFU requires a complete immutable Enqueue snapshot')
    expected, prediction, mapping, _, _ = cached_expectation(request, shift, fs_is_off=fs_is_off)
    wanted = dict(valid=expected.valid_mask, enq=expected.enq,
        prev_count=expected.prev_count if prev_count is None else prev_count,
        exception_type=expected.exception_type, exception_mask=expected.exception_mask,
        exception_cross=expected.exception_cross_page, is_backend_exception=expected.is_backend_exception,
        has_satp_flush=expected.has_satp_flush)
    actual = {field: getattr(observed, field) for field in wanted}
    for field, model_field in [('instrs', 'instrs'), ('is_rvc', 'is_rvc'), ('foldpc', 'foldpc'),
                               ('ftq', 'ftq'), ('end_off', 'end_offsets'), ('pred', 'pred_taken')]:
        valid_lanes = tuple(lane for lane in mapping if (expected.valid_mask >> lane) & 1)
        wanted[field] = tuple(getattr(expected, model_field)[lane] for lane in valid_lanes)
        actual[field] = tuple(getattr(observed, field)[lane] for lane in valid_lanes)
    actions = tuple(trigger_actions) if trigger_actions is not None else (15,) * 36
    valid_lanes = tuple(lane for lane in range(36) if (expected.valid_mask >> lane) & 1)
    wanted['triggered'] = tuple(actions[lane] for lane in valid_lanes)
    actual['triggered'] = tuple(observed.triggered[lane] for lane in valid_lanes)
    # This padding lane is a proven constant, not arbitrary invalid metadata.
    wanted['padding'] = (0, 0)
    actual['padding'] = (observed.instrs[35], observed.pred[35])
    Scoreboard('ifu.top.enqueue').check(expected=wanted, actual=actual)
    return expected, prediction


def expected_redirect(request, shift):
    _, prediction, _, _, _ = cached_expectation(request, shift)
    redirect = prediction.redirect
    if not redirect.valid:
        return None
    block = int(bool(redirect.block_sel or redirect.is_cross_block))
    w = request.window
    ptr, pc = (w.ftq1, w.start1_pc) if block else (w.ftq0, w.start0_pc)
    trainable = int(redirect.branch_type == DIRECT or bool(redirect.ras_action & POP)
                    or redirect.invalid_taken or redirect.not_cfi_taken)
    return Redirect(ptr, trainable, pc & ((1 << 50) - 1), redirect.taken, redirect.end_offset,
                    redirect.is_rvc, redirect.branch_type, redirect.ras_action, redirect.target)


def check_redirect(observed, request, shift):
    if not isinstance(observed, Redirect):
        raise TypeError('IFU requires a complete immutable Redirect snapshot')
    wanted = expected_redirect(request, shift)
    if wanted is None:
        raise AssertionError('unexpected IFU redirect for an independently legal prediction')
    Scoreboard('ifu.top.redirect').check(expected=wanted, actual=observed)


def check_gpa(observed, request, shift):
    expected = cached_expectation(request, shift)[0]
    wanted = GpaWrite(expected.gp_ftq, expected.gp_addr, expected.gp_for_vs) if expected.gp_addr_wen else None
    Scoreboard('ifu.top.gpa-write').check(expected=wanted, actual=observed)


def uncached_word(response, carry):
    """The bus owns returned bytes; a saved low half owns the original PC."""
    return response.resp_data if carry is None else carry.low | ((response.resp_data & 0xffff) << 16)


def uncached_redirect(request, response, carry):
    word = uncached_word(response, carry)
    rvc = int((word & 3) != 3)
    branch, ras, _ = branch_info(word, rvc)
    # Uncached fetch asks FTQ to resume sequentially after exactly this read,
    # even for a jump. Its branch attribute is still the ISA-decoded one.
    short = rvc or carry is not None or response.resp_need_resend
    w = request.window
    return Redirect(w.ftq0, 0, w.start0_pc & ((1 << 50) - 1), 0, 0 if short else 1,
                    rvc, branch, ras, (w.start0_pc + (2 if short else 4)) & PC_MASK)


def check_uncached_enqueue(observed, request, shift, response, carry, *, prev_count=1,
                           trigger_actions=(15,) * 36, fs_is_off=0):
    if not isinstance(observed, Enqueue):
        raise TypeError('IFU requires a complete immutable Enqueue snapshot')
    word = uncached_word(response, carry)
    decoded = expand(word, fs_is_off=bool(fs_is_off))
    w = request.window
    pc = w.start0_pc if carry is None else carry.pc
    mask = 1 << shift
    wanted = dict(valid=mask, enq=mask, prev_count=prev_count,
        instr=word if decoded.ill else decoded.bits, is_rvc=int((word & 3) != 3),
        ftq=w.ftq0, end_offset=0 if (word & 3) != 3 or carry is not None else 1, pred_taken=0,
        folded_pc=xor_fold((pc & ((1 << 50) - 1)) >> 1, 10),
        exception_type=w.exc0 or response.resp_exception or (4 if decoded.ill else 0),
        exception_mask=mask, exception_cross=int(carry is not None and bool(w.exc0 or response.resp_exception)),
        is_backend_exception=w.backend_exc0, has_satp_flush=w.satp0, trigger=trigger_actions[shift], padding=(0, 0))
    actual = dict(valid=observed.valid, enq=observed.enq, prev_count=observed.prev_count,
        instr=observed.instrs[shift], is_rvc=observed.is_rvc[shift], ftq=observed.ftq[shift],
        end_offset=observed.end_off[shift], pred_taken=observed.pred[shift], folded_pc=observed.foldpc[shift],
        exception_type=observed.exception_type, exception_mask=observed.exception_mask,
        exception_cross=observed.exception_cross, is_backend_exception=observed.is_backend_exception,
        has_satp_flush=observed.has_satp_flush, trigger=observed.triggered[shift],
        padding=(observed.instrs[35], observed.pred[35]))
    Scoreboard('ifu.top.uncached-enqueue').check(expected=wanted, actual=actual)
