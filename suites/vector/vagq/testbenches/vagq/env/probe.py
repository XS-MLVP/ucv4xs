"""Schema-driven VAGQ public binding and packet encoder."""
from dataclasses import dataclass

from toffee import Bundle

from suites.vector.vagq.testbenches.vagq.env.schema import INPUT_NAMES
from suites.vector.vagq.testbenches.vagq.env.schema import OUTPUT_NAMES
from suites.vector.vagq.testbenches.vagq.transactions import ActiveRequest
from suites.vector.vagq.testbenches.vagq.transactions import Beat
from suites.vector.vagq.testbenches.vagq.transactions import DataPacket
from suites.vector.vagq.testbenches.vagq.transactions import EmptyRequest
from suites.vector.vagq.testbenches.vagq.transactions import NativePacket
from suites.vector.vagq.testbenches.vagq.transactions import Observation
from suites.vector.vagq.testbenches.vagq.transactions import Response
from suites.vector.vagq.testbenches.vagq.transactions import StoreData
from suites.vector.vagq.testbenches.vagq.transactions import VrfRead
from suites.vector.vagq.testbenches.vagq.transactions import VrfWrite
from suites.vector.vagq.testbenches.vagq.transactions import Wakeup
from suites.vector.vagq.testbenches.vagq.transactions import Writeback


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


# Public leaves that the generated VAGQ schema intentionally omits.  Reading a
# zero for these is a *constant* of the pruned interface, not a missing
# observation.  Everything else in OUTPUT_NAMES is required to be sampled.
PRUNED_OUTPUT_REASONS = {
    f'io_staReq_{lane}_{suffix}': reason
    for lane, suffix, reason in (
        (0, 'bits_req_data_pc', 'STA payload has no public PC leaf'),
        (0, 'bits_req_ctrl_vecWen', 'STA payload has no public vector-write leaf'),
        (1, 'bits_req_data_pc', 'STA payload has no public PC leaf'),
        (1, 'bits_req_ctrl_vecWen', 'STA payload has no public vector-write leaf'),
    )
}
_REQUIRED_OUTPUTS = frozenset(OUTPUT_NAMES)


def sampled_output(outputs, name):
    """Read one sampled public leaf, distinguishing pruning from absence.

    A leaf registered in the generated schema must be present in the sample;
    silently substituting zero would turn a missing observation into a fake
    constant.  Only explicitly pruned leaves return their documented constant.
    """
    if name in outputs:
        return int(outputs[name])
    if name in _REQUIRED_OUTPUTS:
        raise ValueError(f'missing required public output sample: {name}')
    if name in PRUNED_OUTPUT_REASONS:
        return 0
    raise ValueError(f'unknown public output leaf: {name}')


def _active_request(outputs, group, lane):
    prefix = f'io_{group}_{lane}_'
    return ActiveRequest(
        group='load' if group == 'lduReq' else 'store',
        lane=lane,
        valid=bool(sampled_output(outputs, prefix + 'valid')),
        meta_valid=bool(sampled_output(outputs, prefix + 'bits_meta_valid')),
        entry_idx=sampled_output(outputs, prefix + 'bits_meta_entryIdx'),
        byte_offset=sampled_output(outputs, prefix + 'bits_meta_byteOffset'),
        elem_idx=sampled_output(outputs, prefix + 'bits_meta_elemIdx'),
        data_mask=sampled_output(outputs, prefix + 'bits_meta_dataMask'),
        data_size=sampled_output(outputs, prefix + 'bits_meta_dataSize'),
        vaddr=sampled_output(outputs, prefix + 'bits_req_data_src_0'),
        pc=sampled_output(outputs, prefix + 'bits_req_data_pc'),
        rob_flag=sampled_output(outputs, prefix + 'bits_req_robIdx_flag'),
        rob_value=sampled_output(outputs, prefix + 'bits_req_robIdx_value'),
        lq_flag=sampled_output(outputs, prefix + 'bits_req_lqIdx_flag'),
        lq_value=sampled_output(outputs, prefix + 'bits_req_lqIdx_value'),
        sq_first_flag=sampled_output(outputs, prefix + 'bits_req_sqIdx_first_flag'),
        sq_second_flag=sampled_output(outputs, prefix + 'bits_req_sqIdx_second_flag'),
        sq_value=sampled_output(outputs, prefix + 'bits_req_sqIdx_value'),
        ftq_flag=sampled_output(outputs, prefix + 'bits_req_ctrl_ftqIdx_flag'),
        ftq_value=sampled_output(outputs, prefix + 'bits_req_ctrl_ftqIdx_value'),
        ftq_offset=sampled_output(outputs, prefix + 'bits_req_ctrl_ftqOffset'),
        pdest=sampled_output(outputs, prefix + 'bits_req_toRF_pdest'),
        ctrl_fu_type=sampled_output(outputs, prefix + 'bits_req_ctrl_fuType'),
        ctrl_vec_wen=sampled_output(outputs, prefix + 'bits_req_ctrl_vecWen'),
    )


def _empty_request(outputs, lane):
    prefix = f'io_lsqEmptyReq_{lane}_'
    return EmptyRequest(
        lane=lane,
        valid=bool(sampled_output(outputs, prefix + 'valid')),
        entry_idx=sampled_output(outputs, prefix + 'bits_entryIdx'),
        issue_mask=sampled_output(outputs, prefix + 'bits_issueMask'),
        rob_flag=sampled_output(outputs, prefix + 'bits_robIdx_flag'),
        rob_value=sampled_output(outputs, prefix + 'bits_robIdx_value'),
        is_load=sampled_output(outputs, prefix + 'bits_isLoad'),
        lq_value=sampled_output(outputs, prefix + 'bits_lqIdx_value'),
        sq_value=sampled_output(outputs, prefix + 'bits_sqIdx_value'),
    )


def decode(outputs, *, cycle=0, beat=None):
    """Decode one public sample into immutable transaction records.

    Physical leaf names stay in this binding layer; tests consume only the
    typed snapshot.  Every leaf registered in the generated schema must be
    present.  Only explicitly pruned leaves (documented in
    ``PRUNED_OUTPUT_REASONS``) resolve to their constant zero.

    ``beat`` is the exact same-cycle input that produced ``outputs``.  When it
    is supplied, its target-ready values are captured as positive handshake
    evidence (including all-False).  When it is omitted the snapshot records
    "no evidence" (``None``), which is deliberately distinct from a known
    all-False cycle.
    """
    return Observation(
        cycle=cycle,
        ldu_ready=None if beat is None else beat.ldu_ready,
        sta_ready=None if beat is None else beat.sta_ready,
        empty_ready=None if beat is None else beat.empty_ready,
        addr_ready=(
            bool(sampled_output(outputs, 'io_addrUop_0_ready')),
            bool(sampled_output(outputs, 'io_addrUop_1_ready')),
        ),
        loads=tuple(_active_request(outputs, 'lduReq', lane) for lane in range(3)),
        stores=tuple(_active_request(outputs, 'staReq', lane) for lane in range(2)),
        empty_requests=tuple(_empty_request(outputs, lane) for lane in range(2)),
        vrf_read=VrfRead(
            valid=bool(sampled_output(outputs, 'io_vrfReadReq_valid')),
            entry_idx=sampled_output(outputs, 'io_vrfReadReq_bits_entryIdx'),
            rob_flag=sampled_output(outputs, 'io_vrfReadReq_bits_robIdx_flag'),
            rob_value=sampled_output(outputs, 'io_vrfReadReq_bits_robIdx_value'),
        ),
        vrf_write=VrfWrite(
            valid=bool(sampled_output(outputs, 'io_vrfWriteReq_valid')),
            entry_idx=sampled_output(outputs, 'io_vrfWriteReq_bits_entryIdx'),
            pdest=sampled_output(outputs, 'io_vrfWriteReq_bits_pdest'),
            mask=sampled_output(outputs, 'io_vrfWriteReq_bits_mask'),
            data=sampled_output(outputs, 'io_vrfWriteReq_bits_data'),
        ),
        store_data=tuple(
            StoreData(
                lane=lane,
                valid=bool(sampled_output(outputs, f'io_vagqStdData_{lane}_valid')),
                sq_first_flag=sampled_output(
                    outputs, f'io_vagqStdData_{lane}_bits_sqIdx_first_flag'),
                sq_second_flag=sampled_output(
                    outputs, f'io_vagqStdData_{lane}_bits_sqIdx_second_flag'),
                sq_value=sampled_output(outputs, f'io_vagqStdData_{lane}_bits_sqIdx_value'),
                data=sampled_output(outputs, f'io_vagqStdData_{lane}_bits_data'),
            )
            for lane in range(2)
        ),
        writeback=Writeback(
            valid=bool(sampled_output(outputs, 'io_robWriteback_valid')),
            entry_idx=sampled_output(outputs, 'io_robWriteback_bits_entryIdx'),
            rob_flag=sampled_output(outputs, 'io_robWriteback_bits_robIdx_flag'),
            rob_value=sampled_output(outputs, 'io_robWriteback_bits_robIdx_value'),
            exception=sampled_output(outputs, 'io_robWriteback_bits_exception'),
            exception_number=sampled_output(
                outputs, 'io_robWriteback_bits_exceptionNumber'),
            fault_vstart=sampled_output(outputs, 'io_robWriteback_bits_faultVstart'),
            uop_idx=sampled_output(outputs, 'io_robWriteback_bits_uopIdx'),
            uop_type=sampled_output(outputs, 'io_robWriteback_bits_uopType'),
            nf=sampled_output(outputs, 'io_robWriteback_bits_nf'),
            deew=sampled_output(outputs, 'io_robWriteback_bits_deew'),
        ),
        wakeup=Wakeup(
            valid=bool(sampled_output(outputs, 'io_vpWakeUp_valid')),
            pdest=sampled_output(outputs, 'io_vpWakeUp_bits'),
        ),
    )
