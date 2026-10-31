"""Schema-driven StoreDataCtrl picker binding and input encoding."""
from suites.vector.vagq import ROOT as _SUITE_ROOT
import json
from dataclasses import dataclass
from pathlib import Path

from toffee import Bundle

from .types import (
    Beat,
    Observation,
    StoreDataRequest,
    Update,
    VrfReadRequest,
)

ROOT = _SUITE_ROOT
SCHEMA = json.loads((ROOT / 'dut/StoreDataCtrl/signals.json').read_text())


def _leaves(node, prefix=''):
    result = []
    for name, value in node.items():
        path = prefix + name
        if value.get('_') is True:
            result.append((path, value['Pin']))
        else:
            result.extend(_leaves(value, path + '_'))
    return result


LEAVES = _leaves(SCHEMA)
INPUT_NAMES = tuple(name for name, pin in LEAVES if pin == 'input' and name not in ('clock', 'reset'))
OUTPUT_NAMES = tuple(name for name, pin in LEAVES if pin == 'output')


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

        def get(name):
            return getattr(value, name).as_int()

        read_req = VrfReadRequest(
            bool(get('io_vrfReadReq_valid')),
            get('io_vrfReadReq_bits_entryIdx'),
            get('io_vrfReadReq_bits_robIdx_flag'),
            get('io_vrfReadReq_bits_robIdx_value'),
            get('io_vrfReadReq_bits_psrc'),
        )

        store_data = []
        for slot in range(2):
            prefix = f'io_storeDataReq_{slot}_'
            if not get(prefix + 'valid'):
                store_data.append(None)
            else:
                store_data.append(StoreDataRequest(
                    get(prefix + 'bits_sqIdx_first_flag'),
                    get(prefix + 'bits_sqIdx_second_flag'),
                    get(prefix + 'bits_sqIdx_value'),
                    get(prefix + 'bits_data'),
                ))

        updates = tuple(
            Update(
                bool(get(f'io_update_{slot}_valid')),
                get(f'io_update_{slot}_bits_entryIdx'),
                get(f'io_update_{slot}_bits_setDataSent'),
            )
            for slot in range(2)
        )
        return Observation(read_req, tuple(store_data), updates)

    return ports, sample


def encode(beat: Beat):
    values = {name: 0 for name in INPUT_NAMES}
    for index, entry in enumerate(beat.entries):
        prefix = f'io_entry_{index}_entry_'
        for suffix, value in (
            ('valid', int(entry.valid)),
            ('static_meta_sqIdx_first_flag', entry.sq_first_flag),
            ('static_meta_sqIdx_second_flag', entry.sq_second_flag),
            ('static_meta_sqIdx_value', entry.sq_value),
            ('static_uopType', entry.uop_type),
            ('static_robIdx_flag', entry.rob_flag),
            ('static_robIdx_value', entry.rob_value),
            ('static_psrc2', entry.psrc2),
            ('static_deew', entry.deew),
            ('static_startByteOffset', entry.start_byte),
            ('static_elemActiveMask', entry.elem_active),
            ('dynamic_reqAck', entry.req_ack),
            ('dynamic_dataSent', entry.data_sent),
            ('dynamic_state', entry.state),
        ):
            if prefix + suffix in values:
                values[prefix + suffix] = value
        values[f'io_entry_{index}_orderedCanProceed'] = int(entry.ordered_can_proceed)
        values[f'io_psrc2Ready_{index}'] = int(beat.psrc2_ready[index])

    values.update({
        'io_redirect_valid': int(beat.redirect.valid),
        'io_redirect_bits_level': beat.redirect.level,
        'io_redirect_bits_robIdx_flag': beat.redirect.rob_flag,
        'io_redirect_bits_robIdx_value': beat.redirect.rob_value,
        'io_vrfReadReq_ready': int(beat.vrf_read_req_ready),
        'io_vrfReadResp_valid': int(beat.vrf_read_resp.valid),
        'io_vrfReadResp_bits_entryIdx': beat.vrf_read_resp.entry_idx,
        'io_vrfReadResp_bits_robIdx_flag': beat.vrf_read_resp.rob_flag,
        'io_vrfReadResp_bits_robIdx_value': beat.vrf_read_resp.rob_value,
        'io_vrfReadResp_bits_data': beat.vrf_read_resp.data,
    })
    for slot, ready in enumerate(beat.store_data_ready):
        values[f'io_storeDataReq_{slot}_ready'] = int(ready)
    for i in range(8):
        for j in range(8):
            if i != j:
                values[f'io_olderMatrix_{i}_{j}'] = int(beat.older_matrix[i][j])
    return values
