"""Schema-driven MergeCtrl picker binding and input encoding."""
from suites.vector.vagq import ROOT as _SUITE_ROOT
import json
from dataclasses import dataclass
from pathlib import Path

from toffee import Bundle

from .types import (
    Beat,
    Observation,
    ResponseUpdate,
    RobWriteback,
    StateUpdate,
    VrfReadRequest,
    VrfWriteRequest,
)

ROOT = _SUITE_ROOT
SCHEMA = json.loads((ROOT / 'dut/MergeCtrl/signals.json').read_text())


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

        updates = []
        for lane in range(7):
            prefix = f'io_update_{lane}_'
            updates.append(ResponseUpdate(
                get(prefix + 'setReqAck'),
                get(prefix + 'clearReqSent'),
                get(prefix + 'exception') if prefix + 'exception' in OUTPUT_NAMES else 0,
                get(prefix + 'exceptionNumber') if prefix + 'exceptionNumber' in OUTPUT_NAMES else 0,
                get(prefix + 'faultElemIdx') if prefix + 'faultElemIdx' in OUTPUT_NAMES else 0,
                get(prefix + 'entryHitOH'),
            ))

        def state_update(prefix):
            return StateUpdate(
                bool(get(prefix + '_valid')),
                get(prefix + '_bits_entryIdxOH'),
                get(prefix + '_bits_stateNext') if prefix + '_bits_stateNext' in OUTPUT_NAMES else 0,
            )

        read = VrfReadRequest(
            bool(get('io_vrfReadReq_valid')),
            get('io_vrfReadReq_bits_entryIdx'),
            get('io_vrfReadReq_bits_robIdx_flag'),
            get('io_vrfReadReq_bits_robIdx_value'),
            get('io_vrfReadReq_bits_psrc'),
        )
        write = VrfWriteRequest(
            bool(get('io_vrfWriteReq_valid')),
            get('io_vrfWriteReq_bits_entryIdx'),
            get('io_vrfWriteReq_bits_pdest'),
            get('io_vrfWriteReq_bits_data'),
            get('io_vrfWriteReq_bits_mask'),
        )
        wb = RobWriteback(
            bool(get('io_robWriteback_valid')),
            get('io_robWriteback_bits_entryIdx'),
            get('io_robWriteback_bits_robIdx_flag'),
            get('io_robWriteback_bits_robIdx_value'),
            get('io_robWriteback_bits_exception'),
            get('io_robWriteback_bits_exceptionNumber'),
            get('io_robWriteback_bits_faultVstart'),
            get('io_robWriteback_bits_uopType'),
            get('io_robWriteback_bits_uopIdx'),
            get('io_robWriteback_bits_deew'),
            get('io_robWriteback_bits_nf'),
            get('io_robWriteback_bits_meta_lqIdx_flag'),
            get('io_robWriteback_bits_meta_lqIdx_value'),
            get('io_robWriteback_bits_meta_sqIdx_first_flag'),
            get('io_robWriteback_bits_meta_sqIdx_second_flag'),
            get('io_robWriteback_bits_meta_sqIdx_value'),
            get('io_robWriteback_bits_meta_trigger'),
            get('io_robWriteback_bits_meta_vsew'),
            get('io_robWriteback_bits_meta_vlmul'),
            get('io_robWriteback_bits_meta_perfDebugInfo_eliminatedMove'),
            get('io_robWriteback_bits_meta_perfDebugInfo_renameTime'),
            get('io_robWriteback_bits_meta_perfDebugInfo_dispatchTime'),
            get('io_robWriteback_bits_meta_perfDebugInfo_enqRsTime'),
            get('io_robWriteback_bits_meta_perfDebugInfo_selectTime'),
            get('io_robWriteback_bits_meta_perfDebugInfo_issueTime'),
            get('io_robWriteback_bits_meta_perfDebugInfo_runahead_checkpoint_id'),
            get('io_robWriteback_bits_meta_perfDebugInfo_tlbFirstReqTime'),
            get('io_robWriteback_bits_meta_perfDebugInfo_tlbRespTime'),
            get('io_robWriteback_bits_meta_debug_seqNum_seqNum'),
            get('io_robWriteback_bits_meta_debug_seqNum_uopIdx'),
        )
        return Observation(
            tuple(updates),
            state_update('io_splitDoneUpdate'),
            state_update('io_mergeDoneUpdate'),
            StateUpdate(
                bool(get('io_robClearUpdate_valid')),
                get('io_robClearUpdate_bits_entryIdxOH'),
                0,
            ),
            read,
            write,
            wb,
            bool(get('io_vpWakeUp_valid')),
            get('io_vpWakeUp_bits'),
        )

    return ports, sample


def encode(beat: Beat):
    values = {name: 0 for name in INPUT_NAMES}
    field_map = {
        'valid': 'valid',
        'static_meta_lqIdx_flag': 'lq_flag',
        'static_meta_lqIdx_value': 'lq_value',
        'static_meta_sqIdx_first_flag': 'sq_first_flag',
        'static_meta_sqIdx_second_flag': 'sq_second_flag',
        'static_meta_sqIdx_value': 'sq_value',
        'static_meta_vsew': 'vsew',
        'static_meta_vlmul': 'vlmul',
        'static_meta_perfDebugInfo_eliminatedMove': 'perf_eliminated',
        'static_meta_perfDebugInfo_renameTime': 'perf_rename',
        'static_meta_perfDebugInfo_dispatchTime': 'perf_dispatch',
        'static_meta_perfDebugInfo_enqRsTime': 'perf_enq_rs',
        'static_meta_perfDebugInfo_selectTime': 'perf_select',
        'static_meta_perfDebugInfo_issueTime': 'perf_issue',
        'static_meta_perfDebugInfo_runahead_checkpoint_id': 'perf_runahead',
        'static_meta_perfDebugInfo_tlbFirstReqTime': 'perf_tlb_first',
        'static_meta_perfDebugInfo_tlbRespTime': 'perf_tlb_resp',
        'static_meta_debug_seqNum_seqNum': 'debug_seq_num',
        'static_meta_debug_seqNum_uopIdx': 'debug_uop_idx',
        'static_uopType': 'uop_type',
        'static_robIdx_flag': 'rob_flag',
        'static_robIdx_value': 'rob_value',
        'static_pdest': 'pdest',
        'static_psrc2': 'psrc2',
        'static_deew': 'deew',
        'static_uopIdx': 'uop_idx',
        'static_skipMerge': 'skip_merge',
        'static_elemActiveMask': 'elem_active',
        'static_mergeWriteMask': 'merge_write',
        'static_elemAgnosticMask': 'elem_agnostic',
        'static_nf': 'nf',
        'dynamic_reqAck': 'req_ack',
        'dynamic_dataSent': 'data_sent',
        'dynamic_exception': 'exception',
        'dynamic_exceptionNumber': 'exception_number',
        'dynamic_faultElemIdx': 'fault_elem',
        'dynamic_state': 'state',
    }
    for index, entry in enumerate(beat.entries):
        prefix = f'io_entry_{index}_entry_'
        for suffix, field in field_map.items():
            name = prefix + suffix
            if name in values:
                values[name] = int(getattr(entry, field))
        values[f'io_entry_{index}_orderedCanProceed'] = int(entry.ordered_can_proceed)
        values[f'io_psrc2Ready_{index}'] = int(beat.psrc2_ready[index])

    values.update({
        'io_vrfReadReq_ready': int(beat.vrf_read_req_ready),
        'io_vrfReadResp_valid': int(beat.vrf_read_resp_valid),
        'io_vrfReadResp_bits_entryIdx': beat.vrf_read_resp_entry_idx,
        'io_vrfReadResp_bits_robIdx_flag': beat.vrf_read_resp_rob_flag,
        'io_vrfReadResp_bits_robIdx_value': beat.vrf_read_resp_rob_value,
        'io_vrfReadResp_bits_data': beat.vrf_read_resp_data,
        'io_redirect_valid': int(beat.redirect.valid),
        'io_redirect_bits_level': beat.redirect.level,
        'io_redirect_bits_robIdx_flag': beat.redirect.rob_flag,
        'io_redirect_bits_robIdx_value': beat.redirect.rob_value,
    })
    responses = beat.ldu_resp + beat.sta_resp + beat.empty_resp
    for lane, response in enumerate(responses):
        prefix = 'io_lduResp_' if lane < 3 else 'io_staResp_' if lane < 5 else 'io_lsqEmptyResp_'
        local = lane if lane < 3 else lane - 3 if lane < 5 else lane - 5
        p = f'{prefix}{local}_'
        values[p + 'valid'] = int(response.valid)
        values[p + 'bits_entryIdx'] = response.entry_idx
        values[p + 'bits_issueMask'] = response.issue_mask
        values[p + 'bits_isNACK'] = int(response.is_nack)
        if p + 'bits_exception' in values:
            values[p + 'bits_exception'] = int(response.exception)
            values[p + 'bits_exceptionNumber'] = response.exception_number
            values[p + 'bits_faultElemIdx'] = response.fault_elem
    for i in range(NUM_ENTRIES := 8):
        for j in range(NUM_ENTRIES):
            if i != j:
                values[f'io_olderMatrix_{i}_{j}'] = int(beat.older_matrix[i][j])
    return values
