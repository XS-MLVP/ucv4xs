"""Synchronous external driver for the clocked picker VAGQ root."""
from dataclasses import replace

from .probe import encode
from .types import Beat


class Driver:
    def __init__(self, dut, ports):
        self.dut = dut
        self.clock = ports.clock
        self.reset = ports.reset
        self.ports = ports
        self.reset.AsImmWrite()
        for signal in ports.inputs.values():
            signal.AsImmWrite()

    def drive(self, beat: Beat):
        self.ports.inputs.drive(encode(beat))

    def reset_dut(self):
        self.drive(Beat())
        self.reset.Set(1)
        self.dut.Step(2)
        self.reset.Set(0)
        self.dut.Step(1)

    def tick(self):
        self.dut.Step(1)


def response_beat(outputs, *, base=None, data=0):
    """Build next-cycle legal LSU/STA/empty/VRF responses from public outputs."""
    from .probe import output, valid
    from .types import EmptyResponse, Response, VrfResponse

    if base is None:
        base = Beat()
    ldu = []
    for lane in range(3):
        prefix = f'io_lduReq_{lane}_'
        if valid(outputs, prefix + 'valid') and valid(outputs, prefix + 'bits_meta_valid'):
            ldu.append(Response(
                valid=True,
                entry_idx=output(outputs, prefix + 'bits_meta_entryIdx'),
                issue_mask=1 << output(outputs, prefix + 'bits_meta_byteOffset'),
            ))
        else:
            ldu.append(Response())
    sta = []
    for lane in range(2):
        prefix = f'io_staReq_{lane}_'
        if valid(outputs, prefix + 'valid') and valid(outputs, prefix + 'bits_meta_valid'):
            sta.append(Response(
                valid=True,
                entry_idx=output(outputs, prefix + 'bits_meta_entryIdx'),
                issue_mask=1 << output(outputs, prefix + 'bits_meta_byteOffset'),
            ))
        else:
            sta.append(Response())
    empty = []
    for lane in range(2):
        prefix = f'io_lsqEmptyReq_{lane}_'
        if valid(outputs, prefix + 'valid'):
            empty.append(EmptyResponse(
                valid=True,
                entry_idx=output(outputs, prefix + 'bits_entryIdx'),
                issue_mask=output(outputs, prefix + 'bits_issueMask'),
            ))
        else:
            empty.append(EmptyResponse())

    vrf = VrfResponse()
    if valid(outputs, 'io_vrfReadReq_valid'):
        vrf = VrfResponse(
            valid=True,
            entry_idx=output(outputs, 'io_vrfReadReq_bits_entryIdx'),
            rob_flag=output(outputs, 'io_vrfReadReq_bits_robIdx_flag'),
            rob_value=output(outputs, 'io_vrfReadReq_bits_robIdx_value'),
            data=data,
        )
    return replace(base, ldu_resp=tuple(ldu), sta_resp=tuple(sta),
                   empty_resp=tuple(empty), vrf_resp=vrf)
