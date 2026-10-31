"""MaskGen DUT scenarios follow semantic mask/window obligations."""
from itertools import product

import pytest

from toffee import Bin, CheckContext, CoverGroupDef, CoverPointDef, Scoreboard, ScoreboardMode

from suites.vector.vagq.maskgen.probe import bind_maskgen
from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate_protocol, mop_info


def _layout(request):
    return (
        'special_segment' if request.nf == 6 and request.deew == 0 and request.ieew == 2
        else 'segment' if request.nf else 'non_segment'
    )


def _window(request):
    info = mop_info(request)
    if request.vstart > info.last:
        return 'all_prestart'
    if request.vl <= info.first:
        return 'empty_body'
    if request.vstart > info.first:
        return 'prestart_body'
    if request.vl > info.last:
        return 'complete_body'
    return 'partial_body'


def _mask_policy(request):
    if request.vma and request.vta:
        return 'mask_and_tail_agnostic'
    if request.vma:
        return 'mask_agnostic'
    if request.vta:
        return 'tail_agnostic'
    return 'undisturbed'


def _source_mask(request):
    if request.v0_mask == 0:
        return 'none'
    if request.v0_mask == 0xffff:
        return 'all'
    return 'sparse'


def _destination(request):
    return 'skip_merge' if mop_info(request).skip_merge else 'merge'


def _width(request):
    return str(8 << request.deew)


def checked_observer(dut):
    sample = bind_maskgen(dut)
    board = Scoreboard('maskgen.outputs')
    coverage = CoverGroupDef('vagq_maskgen_contract_v1', (
        CoverPointDef('layout', {
            name: Bin.values(name) for name in ('non_segment', 'segment', 'special_segment')
        }),
        CoverPointDef('window', {
            name: Bin.values(name) for name in
            ('empty_body', 'prestart_body', 'all_prestart', 'partial_body', 'complete_body')
        }),
        CoverPointDef('mask_policy', {
            name: Bin.values(name) for name in
            ('undisturbed', 'mask_agnostic', 'tail_agnostic', 'mask_and_tail_agnostic')
        }),
        CoverPointDef('source_mask', {
            name: Bin.values(name) for name in ('none', 'sparse', 'all')
        }),
        CoverPointDef('destination', {
            name: Bin.values(name) for name in ('merge', 'skip_merge')
        }),
        CoverPointDef('data_width', {str(8 << width): Bin.values(str(8 << width)) for width in range(4)}),
        CoverPointDef('index_width', {str(8 << width): Bin.values(str(8 << width)) for width in range(4)}),
        CoverPointDef('field_offset', {
            'zero': Bin.values('zero'), 'nonzero': Bin.values('nonzero'),
        }),
    )).instantiate('vagq.maskgen.checked', contract='vector mask/window semantics/v1')

    def check(request):
        expected = evaluate_protocol(request)
        actual = sample(request)
        board.check(expected=expected, actual=actual,
                    context=CheckContext(board.name, ScoreboardMode.DIRECT, request=request))
        coverage.sample(dict(
            layout=_layout(request), window=_window(request), mask_policy=_mask_policy(request),
            source_mask=_source_mask(request), destination=_destination(request),
            data_width=_width(request), index_width=str(8 << request.ieew),
            field_offset='nonzero' if expected['startFieldOffset'] else 'zero',
        ))

    return check, board, coverage


def _legal_configs():
    for emul, ieew, deew, nf in product(range(8), range(4), range(4), range(8)):
        seed = MaskRequest(0xffff, deew, ieew, emul, 16, 0, 0, 0, 0, nf)
        if seed.legal:
            yield emul, ieew, deew, nf


def _requests():
    """One full-window case per legal MOP table row plus semantic boundary cases."""
    for emul, ieew, deew, nf in _legal_configs():
        base = MaskRequest(0xffff, deew, ieew, emul, 255, 0, 0, 0, 0, nf)
        yield base
        info = mop_info(base)
        if info.first or info.last:
            yield MaskRequest(0x5a5a, deew, ieew, emul, max(0, info.last),
                              min(127, info.first + 1), 1, 1, 0, nf)

    # Explicitly exercise each semantic policy and destination/window boundary.
    for request in (
        MaskRequest(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        MaskRequest(0xaaaa, 0, 0, 0, 4, 0, 1, 0, 0, 0),
        MaskRequest(0xffff, 0, 0, 0, 5, 2, 0, 1, 0, 0),
        MaskRequest(0x5555, 0, 0, 0, 4, 1, 1, 1, 0, 0),
        # vstart beyond the whole segment window takes both prestart branches:
        # element-MOP and destination-field masking.
        MaskRequest(0xffff, 0, 0, 0, 255, 127, 0, 0, 0, 1),
        MaskRequest(0xffff, 0, 2, 0, 16, 0, 0, 0, 2, 1),
        MaskRequest(0xffff, 0, 2, 0, 16, 0, 0, 0, 0, 6),
        # A later segment destination starts at a non-zero field offset.
        MaskRequest(0xffff, 2, 0, 0, 16, 0, 0, 0, 1, 4),
        MaskRequest(0xffff, 3, 0, 0, 255, 0, 0, 0, 0, 2),
    ):
        if request.legal:
            yield request


def test_maskgen_contract(maskgen_dut):
    check, board, coverage = checked_observer(maskgen_dut)
    for request in _requests():
        check(request)
    assert board.status.failed == 0
    assert board.status.checked > 0
    coverage.assert_coverage(100)


@pytest.mark.parametrize('emul,vl', ((5, 2), (6, 4), (7, 8)))
def test_fractional_allocated_mask_is_not_an_active_memory_mask(maskgen_dut, emul, vl):
    check, board, _ = checked_observer(maskgen_dut)
    # All mask bits are set: vl, not a convenient zeroed mask, must prevent
    # the padding slots from becoming active memory elements.
    check(MaskRequest(0xffff, 0, 0, emul, vl, 0, 0, 0, 0, 0))
    assert board.status.failed == 0 and board.status.checked == 1
