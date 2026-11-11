"""Independent DefaultConfig logical widths, including DCE metadata omissions."""
from toffee.data import iter_data_leaves, signal_width


def expected_schema():
    values = {'reset': 1, 'read.valid': 1, 'read.waymask': 4, 'write.valid': 1,
        'write.setIdx': 8, 'write.waymask': 4, 'write.data': 64, 'write.code': 1,
        'read_ready.ready': 1, 'write_ready.ready': 1,
        'mbist_response.ack': 1, 'mbist_response.outdata': 66}
    for way in range(4):
        values[f'read.setIdx[{way}]'] = 8
        values[f'response[{way}].data'] = 64
        values[f'response[{way}].code'] = 1
        for name in ('hold', 'bypass', 'bp_clken', 'aux_clk', 'aux_ckbp', 'mcp_hold', 'cgen'):
            values[f'sram_control.ways[{way}].{name}'] = 1
    for name, width in dict(req=1, all=1, array=3, readen=1, writeen=1, be=1,
                            addr=9, addr_rd=9, indata=66).items():
        values[f'mbist.{name}'] = width
    return values


def validate_schema(actual):
    expected = expected_schema()
    if actual != expected or any(type(value) is not int for value in actual.values()):
        raise ValueError(f'ICacheDataBank DefaultConfig ABI differs: expected={expected}, actual={actual}')


def validate_binding(ports, dut):
    actual = {'reset': signal_width(dut.reset)}
    for role in ('read', 'read_ready', 'write', 'write_ready', 'mbist', 'mbist_response', 'sram_control'):
        actual.update({name: signal_width(leaf) for name, leaf in iter_data_leaves(getattr(ports, role).bits, role)})
    actual.update({name: signal_width(leaf) for name, leaf in iter_data_leaves(ports.response, 'response')})
    validate_schema(actual)
