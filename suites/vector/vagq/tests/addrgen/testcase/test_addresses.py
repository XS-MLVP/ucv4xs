"""Combinational scenarios use a probe/function pair, not a clocked agent."""
from itertools import product

from toffee import Bin, CheckContext, CoverGroupDef, CoverPointDef, Scoreboard, ScoreboardMode

from suites.vector.vagq.addrgen.probe import bind_addrgen
from suites.vector.vagq.addrgen.reference import AddressContext, IndexedAddress, StridedAddress, address


def checked_observer(dut):
    sample = bind_addrgen(dut)
    board = Scoreboard('addrgen.address')
    coverage = CoverGroupDef('vagq_addrgen_contract_v2', (
        CoverPointDef('path', {'stride': Bin.values('stride'), 'indexed': Bin.values('indexed')}),
        CoverPointDef('stride_sign', {
            'zero': Bin.values('zero'), 'positive': Bin.values('positive'),
            'negative': Bin.values('negative'), 'na': Bin.values('na'),
        }),
        CoverPointDef('data_bytes', {str(size): Bin.values(size) for size in (1, 2, 4, 8)}),
        CoverPointDef('index_bytes', {str(size): Bin.values(size) for size in (1, 2, 4, 8)}),
        CoverPointDef('index_bank', {
            'lower': Bin.values('lower'), 'upper': Bin.values('upper'), 'na': Bin.values('na'),
        }),
        CoverPointDef('index_wrap', {
            'wrap': Bin.values('wrap'), 'no_wrap': Bin.values('no_wrap'), 'na': Bin.values('na'),
        }),
        CoverPointDef('address_boundary', {
            'wrap': Bin.values('wrap'), 'no_wrap': Bin.values('no_wrap'),
        }),
        CoverPointDef('field', {
            'first_zero': Bin.values('first_zero'),
            'first_nonzero': Bin.values('first_nonzero'),
            'later_ignored': Bin.values('later_ignored'),
        }),
    )).instantiate('vagq.addrgen.checked', contract='domain address -> stable 64-bit address/v2')

    def check(request, **encoding):
        expected = address(request)  # Frozen before any DUT observation.
        actual = sample(request, **encoding)
        board.check(expected=expected, actual=actual,
                    context=CheckContext(board.name, ScoreboardMode.DIRECT, request=request))
        indexed = isinstance(request, IndexedAddress)
        context = request.context
        if indexed:
            selected = (context.element + context.offset) % len(request.indices)
            index_bank = 'upper' if selected >= len(request.indices) // 2 else 'lower'
            index_wrap = 'wrap' if context.element + context.offset >= len(request.indices) else 'no_wrap'
            stride_sign = 'na'
        else:
            index_bank = index_wrap = 'na'
            stride_sign = (
                'zero' if request.stride == 0 else
                'positive' if request.stride > 0 else 'negative'
            )
        if isinstance(request, StridedAddress):
            displacement = request.stride * (context.element + context.offset)
        else:
            displacement = request.indices[(context.element + context.offset) % len(request.indices)]
        field = context.first_field * context.data_bytes if context.offset == 0 else 0
        raw = context.base + displacement + field
        coverage.sample(dict(path='indexed' if indexed else 'stride',
            stride_sign=stride_sign,
            data_bytes=context.data_bytes,
            index_bytes=16 // len(request.indices) if indexed else 1,
            index_bank=index_bank,
            index_wrap=index_wrap,
            address_boundary='wrap' if not 0 <= raw <= (1 << 64) - 1 else 'no_wrap',
            field=(
                'later_ignored' if context.offset != 0 else
                'first_nonzero' if context.first_field else 'first_zero')))

    return check, board, coverage


def test_strided_and_indexed_address_contract(addrgen_dut):
    check, board, coverage = checked_observer(addrgen_dut)
    fixed = (
        (StridedAddress(AddressContext(0x1000, 2, 1), 3), 0x1009),
        (StridedAddress(AddressContext(0x1000, 64, 0, 8, 3), 4), 0x1118),
        (StridedAddress(AddressContext(2, 1, 0), -4), (1 << 64) - 2),
        (StridedAddress(AddressContext(0, 1, 0), -(1 << 63)), 1 << 63),
        (StridedAddress(AddressContext(0x1000, 0, 0, 1, 0), 0), 0x1000),
        (IndexedAddress(AddressContext(0x1000, 3, 0, 2, 3), tuple(range(16))), 0x1009),
        (IndexedAddress(AddressContext(0, 1, 1), (0x8000000000000000, 7)), 1 << 63),
    )
    for transaction, known_address in fixed:
        assert address(transaction) == known_address
        check(transaction)
    for code, size, element, offset, stride in product(
        (0, 1), (1, 2, 4, 8), (0, 1, 15, 16, 63, 127), (0, 1, 3, 15),
        (0, 3, -4, (1 << 63) - 1)
    ):
        context = AddressContext(0xFFFFFFFFFFFFFF00, element, offset, size, 5)
        check(StridedAddress(context, stride), uop_code=code, upper_noise=0xDEADBEEF01234567)
    for code, index_bytes, size, element, offset in product(
        range(2, 8), (1, 2, 4, 8), (1, 2, 4, 8), (0, 1, 7, 15, 16, 127), range(16)
    ):
        width = 8 * index_bytes
        indices = tuple((1 << (width - 1)) + lane * 3 + 1 for lane in range(16 // index_bytes))
        context = AddressContext(0xFFFFFFFFFFFFFF00, element, offset, size, 7)
        check(IndexedAddress(context, indices), uop_code=code)
    assert board.status.checked == len(fixed) + 768 + 9216
    coverage.assert_coverage(100)
