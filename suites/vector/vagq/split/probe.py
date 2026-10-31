"""Schema-driven SplitCtrl picker binding; no pending/stage semantics here."""
from suites.vector.vagq import ROOT as _SUITE_ROOT
import json
from dataclasses import dataclass
from pathlib import Path

from toffee import Bundle

from .types import Beat, EmptyReq, Entry, ExcpUpdate, LsuReq, Observation, Update

ROOT = _SUITE_ROOT
SCHEMA = json.loads((ROOT / 'dut/SplitCtrl/signals.json').read_text())


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

        def lsu(lane):
            prefix = f'io_lsuReq_{lane}_'
            if not get(prefix + 'valid'):
                return None
            return LsuReq(
                get(prefix + 'bits_entryIdx'), get(prefix + 'bits_robIdx_flag'),
                get(prefix + 'bits_robIdx_value'), get(prefix + 'bits_isLoad'),
                get(prefix + 'bits_lqIdx_flag'), get(prefix + 'bits_lqIdx_value'),
                get(prefix + 'bits_sqIdx_first_flag'), get(prefix + 'bits_sqIdx_second_flag'),
                get(prefix + 'bits_sqIdx_value'), get(prefix + 'bits_elemIdx'),
                get(prefix + 'bits_dataSize'), get(prefix + 'bits_dataMask'),
                get(prefix + 'bits_ftqPtr_flag'), get(prefix + 'bits_ftqPtr_value'),
                get(prefix + 'bits_ftqOffset'), get(prefix + 'bits_byteOffset'),
                get(prefix + 'bits_vaddr'), get(prefix + 'bits_pdest'),
            )

        def empty(lane):
            prefix = f'io_lsqEmptyReq_{lane}_'
            if not get(prefix + 'valid'):
                return None
            return EmptyReq(
                get(prefix + 'bits_entryIdx'), get(prefix + 'bits_robIdx_flag'),
                get(prefix + 'bits_robIdx_value'), get(prefix + 'bits_isLoad'),
                get(prefix + 'bits_lqIdx_value'), get(prefix + 'bits_sqIdx_first_flag'),
                get(prefix + 'bits_sqIdx_second_flag'), get(prefix + 'bits_sqIdx_value'),
                get(prefix + 'bits_issueMask'),
            )

        updates = tuple(Update(
            bool(get(f'io_update_{lane}_valid')),
            get(f'io_update_{lane}_bits_entryIdxOH'),
            get(f'io_update_{lane}_bits_setReqSent'),
        ) for lane in range(2))
        excp = ExcpUpdate(
            bool(get('io_excpUpdate_valid')),
            get('io_excpUpdate_bits_entryIdxOH'),
            get('io_excpUpdate_bits_excpSet'),
        )
        return Observation(tuple(lsu(lane) for lane in range(3)),
                           tuple(empty(lane) for lane in range(2)), updates, excp)

    return ports, sample


def encode(beat: Beat):
    values = {name: 0 for name in INPUT_NAMES}
    for index, entry in enumerate(beat.entries):
        p = f'io_in_{index}_entry_'
        for suffix, value in (
            ('valid', int(entry.valid)), ('static_uopType', entry.uop_type),
            ('static_robIdx_flag', entry.rob_flag), ('static_robIdx_value', entry.rob_value),
            ('static_pdest', entry.pdest), ('static_baseAddr', entry.base_addr),
            ('static_op2Data', entry.op2_data), ('static_ieew', entry.ieew),
            ('static_deew', entry.deew), ('static_elemBase', entry.elem_base),
            ('static_startFieldOffset', entry.start_field), ('static_startByteOffset', entry.start_byte),
            ('static_elemValidMask', entry.elem_valid), ('static_elemActiveMask', entry.elem_active),
            ('static_nf', entry.nf), ('dynamic_reqSent', entry.req_sent),
            ('dynamic_reqAck', entry.req_ack), ('dynamic_exception', int(entry.exception)),
            ('dynamic_faultElemIdx', entry.fault_elem), ('dynamic_state', entry.state),
            ('static_meta_ftqPtr_flag', entry.ftq_flag), ('static_meta_ftqPtr_value', entry.ftq_value),
            ('static_meta_ftqOffset', entry.ftq_offset), ('static_meta_lqIdx_flag', entry.lq_flag),
            ('static_meta_lqIdx_value', entry.lq_value), ('static_meta_sqIdx_first_flag', entry.sq_first_flag),
            ('static_meta_sqIdx_second_flag', entry.sq_second_flag), ('static_meta_sqIdx_value', entry.sq_value),
        ):
            if p + suffix in values:
                values[p + suffix] = value
        values[f'io_in_{index}_orderedCanProceed'] = int(entry.ordered_can_proceed)
    values.update({
        'io_redirect_valid': int(beat.redirect.valid),
        'io_redirect_bits_level': beat.redirect.level,
        'io_redirect_bits_robIdx_flag': beat.redirect.rob_flag,
        'io_redirect_bits_robIdx_value': beat.redirect.rob_value,
    })
    for lane, ready in enumerate(beat.lsu_ready):
        values[f'io_lsuReq_{lane}_ready'] = int(ready)
    for lane, ready in enumerate(beat.empty_ready):
        values[f'io_lsqEmptyReq_{lane}_ready'] = int(ready)
    for i in range(8):
        for j in range(8):
            if i != j:
                values[f'io_olderMatrix_{i}_{j}'] = int(beat.older_matrix[i][j])
    return values
