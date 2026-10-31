"""Clockless stable-sampling adapter. No model, checker or scheduled protocol."""
from toffee import Bundle

from .reference import IndexedAddress, StridedAddress, U64


def bind_addrgen(dut):
    inputs = Bundle(**{name: getattr(dut, name) for name in (
        'in_uopType', 'in_baseAddr', 'in_op2Data', 'in_deew', 'in_ieew',
        'in_startFieldOffset', 'in_elemBase', 'in_idxOffset')})
    result = Bundle(address=dut.out_vaddr).compile_sampler()

    def observe(request, *, uop_code=None, upper_noise=0):
        ctx = request.context
        if isinstance(request, StridedAddress):
            code = 0 if uop_code is None else uop_code
            if code not in (0, 1):
                raise ValueError('stride path requires uop code 0/1')
            if not 0 <= upper_noise <= U64:
                raise ValueError('upper noise does not fit 64 bits')
            data = (upper_noise << 64) | (request.stride & U64)
            index_bytes = 1
        elif isinstance(request, IndexedAddress):
            code = 2 if uop_code is None else uop_code
            if code not in range(2, 8):
                raise ValueError('indexed path requires uop code 2..7')
            index_bytes = 16 // len(request.indices)
            data = sum(index << (8 * index_bytes * lane)
                       for lane, index in enumerate(request.indices))
        else:
            raise TypeError('not an address transaction')
        inputs.drive(dict(in_uopType=code, in_baseAddr=ctx.base, in_op2Data=data,
            in_deew=ctx.data_bytes.bit_length() - 1, in_ieew=index_bytes.bit_length() - 1,
            in_startFieldOffset=ctx.first_field, in_elemBase=ctx.element, in_idxOffset=ctx.offset))
        dut.RefreshComb()
        sampled = result().address.as_int()
        dut.GetXClock().RefreshCombT()
        return sampled

    return observe
