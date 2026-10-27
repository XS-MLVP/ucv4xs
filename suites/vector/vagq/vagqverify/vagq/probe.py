"""Schema-driven VAGQ public binding and packet encoder."""
from dataclasses import dataclass

from toffee import Bundle

from .schema import INPUT_NAMES, OUTPUT_NAMES
from .types import Beat, DataPacket, NativePacket, Response


@dataclass(frozen=True, slots=True)
class Ports:
    clock: object
    reset: object
    inputs: Bundle
    outputs: Bundle


def bind(dut):
    ports = Ports(
        dut.clock,
        dut.reset,
        Bundle(**{name: getattr(dut, name) for name in INPUT_NAMES}),
        Bundle(**{name: getattr(dut, name) for name in OUTPUT_NAMES}),
    )
    sampler = ports.outputs.compile_sampler()

    def sample():
        dut.RefreshComb()
        value = sampler()
        return {name: getattr(value, name).as_int() for name in OUTPUT_NAMES}

    return ports, sample


def _set(values, name, value):
    if name in values:
        values[name] = int(value)


def _set_packet(values, prefix, fields):
    for suffix, value in fields.items():
        _set(values, prefix + suffix, value)


def _addr_fields(packet):
    return {
        'bits_meta_ftqPtr_flag': packet.ftq_flag,
        'bits_meta_ftqPtr_value': packet.ftq_value,
        'bits_meta_ftqOffset': packet.ftq_offset,
        'bits_meta_lqIdx_flag': packet.lq_flag,
        'bits_meta_lqIdx_value': packet.lq_value,
        'bits_meta_sqIdx_first_flag': packet.sq_first_flag,
        'bits_meta_sqIdx_second_flag': packet.sq_second_flag,
        'bits_meta_sqIdx_value': packet.sq_value,
        'bits_meta_vsew': packet.vsew,
        'bits_meta_vlmul': packet.vlmul,
        'bits_entryIdx': packet.entry_idx,
        'bits_uopType': packet.uop_type,
        'bits_robIdx_flag': packet.rob_flag,
        'bits_robIdx_value': packet.rob_value,
        'bits_pdest': packet.pdest,
        'bits_psrc2': packet.psrc2,
        'bits_baseAddr': packet.base_addr,
        'bits_v0ByteMask': packet.v0_byte_mask,
        'bits_deew': packet.deew,
        'bits_ieew': packet.ieew,
        'bits_emul': packet.emul,
        'bits_vl': packet.vl,
        'bits_vstart': packet.vstart,
        'bits_vma': packet.vma,
        'bits_vta': packet.vta,
        'bits_uopIdx': packet.uop_idx,
        'bits_lastUop': packet.last_uop,
        'bits_nf': packet.nf,
    }


def _data_fields(packet: DataPacket):
    return {
        'bits_entryIdx': packet.entry_idx,
        'bits_robIdx_flag': packet.rob_flag,
        'bits_robIdx_value': packet.rob_value,
        'bits_op2Data': packet.op2_data,
    }


def _native(values, group, lane, packet: NativePacket):
    prefix = f'io_{group}_{lane}_'
    _set(values, prefix + 'valid', int(packet.valid))
    _set_packet(values, prefix + 'bits_', packet.values())


def _response(values, group, lane, response: Response):
    prefix = f'io_{group}_{lane}_'
    _set(values, prefix + 'valid', int(response.valid))
    _set_packet(values, prefix + 'bits_', {
        'entryIdx': response.entry_idx,
        'issueMask': response.issue_mask,
        'isNACK': response.is_nack,
        'exception': response.exception,
        'exceptionNumber': response.exception_number,
        'faultElemIdx': response.fault_elem_idx,
    })


def encode(beat: Beat):
    values = {name: 0 for name in INPUT_NAMES}

    for lane, (packet, valid) in enumerate(zip(beat.addr, beat.addr_valid)):
        _set(values, f'io_addrUop_{lane}_valid', int(valid))
        if packet is not None:
            _set_packet(values, f'io_addrUop_{lane}_', _addr_fields(packet))

    for kind, packets, valids in (
        ('strideDataUop', beat.stride, beat.stride_valid),
        ('indexDataUop', beat.index, beat.index_valid),
    ):
        for lane, (packet, valid) in enumerate(zip(packets, valids)):
            _set(values, f'io_{kind}_{lane}_valid', int(valid))
            if packet is not None:
                _set_packet(values, f'io_{kind}_{lane}_', _data_fields(packet))

    for lane, packet in enumerate(beat.issue_lda):
        _native(values, 'issueLda', lane, packet)
    for lane, packet in enumerate(beat.issue_sta):
        _native(values, 'issueSta', lane, packet)

    for lane, ready in enumerate(beat.ldu_ready):
        _set(values, f'io_lduReq_{lane}_ready', int(ready))
    for lane, ready in enumerate(beat.sta_ready):
        _set(values, f'io_staReq_{lane}_ready', int(ready))
    for lane, ready in enumerate(beat.empty_ready):
        _set(values, f'io_lsqEmptyReq_{lane}_ready', int(ready))
    for lane, busy in enumerate(beat.std_busy):
        _set(values, f'io_stdDataBusy_{lane}', int(busy))

    for lane, response in enumerate(beat.ldu_resp):
        _response(values, 'lduResp', lane, response)
    for lane, response in enumerate(beat.sta_resp):
        _response(values, 'staResp', lane, response)
    for lane, response in enumerate(beat.empty_resp):
        prefix = f'io_lsqEmptyResp_{lane}_'
        _set(values, prefix + 'valid', int(response.valid))
        _set_packet(values, prefix + 'bits_', {
            'entryIdx': response.entry_idx,
            'issueMask': response.issue_mask,
            'isNACK': response.is_nack,
        })

    _set(values, 'io_vrfReadResp_valid', int(beat.vrf_resp.valid))
    _set_packet(values, 'io_vrfReadResp_bits_', {
        'entryIdx': beat.vrf_resp.entry_idx,
        'robIdx_flag': beat.vrf_resp.rob_flag,
        'robIdx_value': beat.vrf_resp.rob_value,
        'data': beat.vrf_resp.data,
    })
    _set(values, 'io_psrc2ReadyMask', beat.psrc2_ready_mask)
    _set(values, 'io_redirect_valid', int(beat.redirect.valid))
    _set_packet(values, 'io_redirect_bits_', {
        'level': beat.redirect.level,
        'robIdx_flag': beat.redirect.rob_flag,
        'robIdx_value': beat.redirect.rob_value,
    })
    return values


def valid(outputs, name):
    return bool(outputs.get(name, 0))


def output(outputs, name):
    return int(outputs.get(name, 0))
