"""Fixed DefaultConfig ABI, not the obsolete zero-width/single-macro report."""
from toffee.data import iter_data_leaves, signal_width


def expected_schema():
    values = {'reset': 1, 'read.valid': 1, 'read.setIdx': 7, 'read_ready.ready': 1,
        'write.valid': 1, 'write.setIdx': 7, 'write.waymask': 4, 'write.phyTag': 36,
        'write.maybeRvcMap': 32, 'write.code': 1, 'write_ready.ready': 1, 'flush_all.flushAll': 1,
        'mbist_response.ack': 1, 'mbist_response.outdata': 138}
    for name, width in dict(req=1, all=1, array=1, readen=1, writeen=1, be=2, addr=8, addr_rd=8, indata=138).items():
        values[f'mbist.{name}'] = width
    for way in range(4):
        values[f'response[{way}].valid'] = 1
        for name, width in {'meta.phyTag': 36, 'meta.maybeRvcMap': 32, 'code': 1}.items():
            values[f'response[{way}].bits.{name}'] = width
    for group in range(2):
        for name in ('hold', 'bypass', 'bp_clken', 'aux_clk', 'aux_ckbp', 'mcp_hold', 'cgen'):
            values[f'sram_control.ways[{group}].{name}'] = 1
    return values


def validate_schema(actual):
    if actual != expected_schema() or any(type(value) is not int for value in actual.values()):
        raise ValueError('ICacheMetaBank DefaultConfig ABI requires two138-bit macros, four69-bit ways and exact physical ports')


def validate_binding(ports, dut):
    actual = {'reset': signal_width(dut.reset)}
    for role in ('read', 'read_ready', 'write', 'write_ready', 'flush_all', 'mbist', 'mbist_response', 'sram_control'):
        actual.update({name: signal_width(leaf) for name, leaf in iter_data_leaves(getattr(ports, role).bits, role)})
    actual.update({name: signal_width(leaf) for name, leaf in iter_data_leaves(ports.response, 'response')})
    validate_schema(actual)
