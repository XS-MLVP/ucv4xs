"""Clockless MaskGen binding; it only encodes a domain request and samples outputs."""
from toffee import Bundle

from .reference import MaskRequest


def bind_maskgen(dut):
    inputs = Bundle(**{name: getattr(dut, name) for name in (
        'in_v0ByteMask', 'in_deew', 'in_ieew', 'in_emul', 'in_vl',
        'in_vstart', 'in_vma', 'in_vta', 'in_uopIdx', 'in_nf')})
    result = Bundle(**{name: getattr(dut, 'out_' + name) for name in (
        'elemValidMask', 'elemActiveMask', 'elemAgnosticMask', 'mergeWriteMask',
        'elemBase', 'startFieldOffset', 'startByteOffset', 'skipMerge')}).compile_sampler()

    def observe(request: MaskRequest):
        inputs.drive({
            'in_v0ByteMask': request.v0_mask,
            'in_deew': request.deew,
            'in_ieew': request.ieew,
            'in_emul': request.emul,
            'in_vl': request.vl,
            'in_vstart': request.vstart,
            'in_vma': request.vma,
            'in_vta': request.vta,
            'in_uopIdx': request.uop_idx,
            'in_nf': request.nf,
        })
        dut.RefreshComb()
        value = result()
        observed = {name: getattr(value, name).as_int() for name in (
            'elemValidMask', 'elemActiveMask', 'elemAgnosticMask', 'mergeWriteMask',
            'elemBase', 'startFieldOffset', 'startByteOffset', 'skipMerge')}
        dut.GetXClock().RefreshCombT()
        return observed

    return observe
