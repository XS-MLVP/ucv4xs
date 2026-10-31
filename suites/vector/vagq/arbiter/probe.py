"""Schema-driven VAGQArbiter binding and semantic input encoding."""
from dataclasses import dataclass

from toffee import Bundle

from .schema import INPUT_NAMES, OUTPUT_NAMES
from .types import Beat


@dataclass(frozen=True, slots=True)
class Ports:
    inputs: Bundle
    outputs: Bundle


def bind(dut):
    ports = Ports(
        Bundle(**{name: getattr(dut, name) for name in INPUT_NAMES}),
        Bundle(**{name: getattr(dut, name) for name in OUTPUT_NAMES}),
    )
    sampler = ports.outputs.compile_sampler()

    def sample():
        dut.RefreshComb()
        value = sampler()
        return {
            name: getattr(value, name).as_int()
            for name in OUTPUT_NAMES
        }

    return ports, sample


def encode(beat: Beat):
    values = {name: 0 for name in INPUT_NAMES}

    for lane, request in enumerate(beat.issue_lda):
        values[f'io_issueLda_{lane}_valid'] = int(request.valid)
        for field, value in request.fields:
            name = f'io_issueLda_{lane}_bits_{field}'
            if name in values:
                values[name] = value

    for lane, request in enumerate(beat.issue_sta):
        values[f'io_issueSta_{lane}_valid'] = int(request.valid)
        for field, value in request.fields:
            name = f'io_issueSta_{lane}_bits_{field}'
            if name in values:
                values[name] = value

    for lane, request in enumerate(beat.vagq_lsu):
        prefix = f'io_vagqLsuReq_{lane}_'
        values[prefix + 'valid'] = int(request.valid)
        for suffix, value in {
            'bits_entryIdx': request.entry_idx,
            'bits_robIdx_flag': request.rob_flag,
            'bits_robIdx_value': request.rob_value,
            'bits_isLoad': int(request.is_load),
            'bits_lqIdx_flag': request.lq_flag,
            'bits_lqIdx_value': request.lq_value,
            'bits_sqIdx_first_flag': request.sq_first_flag,
            'bits_sqIdx_second_flag': request.sq_second_flag,
            'bits_sqIdx_value': request.sq_value,
            'bits_elemIdx': request.elem_idx,
            'bits_dataSize': request.data_size,
            'bits_dataMask': request.data_mask,
            'bits_pc': request.pc,
            'bits_ftqPtr_flag': request.ftq_flag,
            'bits_ftqPtr_value': request.ftq_value,
            'bits_ftqOffset': request.ftq_offset,
            'bits_byteOffset': request.byte_offset,
            'bits_vaddr': request.vaddr,
            'bits_pdest': request.pdest,
        }.items():
            if prefix + suffix in values:
                values[prefix + suffix] = value

    for lane, request in enumerate(beat.vagq_store_data):
        prefix = f'io_vagqStoreDataReq_{lane}_'
        values[prefix + 'valid'] = int(request.valid)
        for suffix, value in {
            'bits_sqIdx_first_flag': request.sq_first_flag,
            'bits_sqIdx_second_flag': request.sq_second_flag,
            'bits_sqIdx_value': request.sq_value,
            'bits_data': request.data,
        }.items():
            if prefix + suffix in values:
                values[prefix + suffix] = value

    for lane, ready in enumerate(beat.ldu_ready):
        values[f'io_lduReq_{lane}_ready'] = int(ready)
    for lane, ready in enumerate(beat.sta_ready):
        values[f'io_staReq_{lane}_ready'] = int(ready)
    for lane, busy in enumerate(beat.std_busy):
        values[f'io_stdDataBusy_{lane}'] = int(busy)
    return values
