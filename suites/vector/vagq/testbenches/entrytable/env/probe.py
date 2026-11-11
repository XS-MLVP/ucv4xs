"""Schema-driven flat binding for the wide EntryTable picker root."""
from suites.vector.vagq import ROOT as _SUITE_ROOT
import json
from dataclasses import dataclass
from pathlib import Path

from toffee import Bundle

ROOT = _SUITE_ROOT


def _leaves(node, prefix=''):
    result = []
    for name, value in node.items():
        path = prefix + name
        if value.get('_') is True:
            result.append((path, value['Pin']))
        else:
            result.extend(_leaves(value, path + '_'))
    return result


SCHEMA = json.loads((ROOT / 'dut/VAGQEntryTable/signals.json').read_text())
LEAVES = _leaves(SCHEMA)
INPUT_NAMES = tuple(name for name, pin in LEAVES if pin == 'input' and name not in ('clock', 'reset'))


def _entry_outputs():
    names = []
    fields = (
        'valid', 'static_meta_ftqPtr_flag', 'static_meta_ftqPtr_value',
        'static_meta_ftqOffset', 'static_meta_lqIdx_flag', 'static_meta_lqIdx_value',
        'static_meta_sqIdx_first_flag', 'static_meta_sqIdx_second_flag',
        'static_meta_sqIdx_value', 'static_meta_vsew', 'static_meta_vlmul',
        'static_uopType', 'static_robIdx_flag', 'static_robIdx_value',
        'static_pdest', 'static_psrc2', 'static_baseAddr', 'static_op2Data',
        'static_ieew', 'static_deew', 'static_uopIdx', 'static_lastUop',
        'static_elemBase', 'static_startFieldOffset', 'static_startByteOffset',
        'static_skipMerge', 'static_elemValidMask', 'static_elemActiveMask',
        'static_mergeWriteMask', 'static_elemAgnosticMask', 'static_nf',
        'dynamic_reqSent', 'dynamic_reqAck', 'dynamic_dataSent', 'dynamic_exception',
        'dynamic_exceptionNumber', 'dynamic_faultElemIdx', 'dynamic_state',
    )
    for i in range(8):
        names.extend(f'io_entries_{i}_{field}' for field in fields)
    names.extend(('io_addrUop_0_ready', 'io_addrUop_1_ready', 'io_dataUop_0_ready', 'io_dataUop_1_ready'))
    names.extend(f'io_olderMatrix_{i}_{j}' for i in range(8) for j in range(8) if i != j)
    return tuple(names), fields


OUTPUT_NAMES, ENTRY_OUTPUT_FIELDS = _entry_outputs()


@dataclass(frozen=True, slots=True)
class Ports:
    clock: object
    reset: object
    inputs: Bundle
    outputs: Bundle


def bind(dut):
    ports = Ports(
        dut.clock, dut.reset,
        Bundle(**{name: getattr(dut, name) for name in INPUT_NAMES}),
        Bundle(**{name: getattr(dut, name) for name in OUTPUT_NAMES}),
    )
    sampler = ports.outputs.compile_sampler()

    def sample():
        dut.RefreshComb()
        value = sampler()
        entries = []
        for i in range(8):
            prefix = f'io_entries_{i}_'
            entries.append(tuple(getattr(value, prefix + field).as_int() for field in ENTRY_OUTPUT_FIELDS))
        ready = tuple(bool(getattr(value, name).as_int()) for name in (
            'io_addrUop_0_ready', 'io_addrUop_1_ready', 'io_dataUop_0_ready', 'io_dataUop_1_ready'))
        older = [[False] * 8 for _ in range(8)]
        for i in range(8):
            for j in range(8):
                if i != j:
                    older[i][j] = bool(getattr(value, f'io_olderMatrix_{i}_{j}').as_int())
        return tuple(entries), ready[:2], ready[2:], tuple(tuple(row) for row in older)

    return ports, sample


def _set(values, name, value):
    if name in values:
        values[name] = value


def encode(beat):
    values = {name: 0 for name in INPUT_NAMES}
    for lane, (packet, valid) in enumerate(zip(beat.addr, beat.addr_valid)):
        _set(values, f'io_addrUop_{lane}_valid', int(valid))
        if packet is None:
            continue
        p = f'io_addrUop_{lane}_bits_'
        for suffix, value in (
            ('meta_ftqPtr_flag', packet.meta_ftq_flag), ('meta_ftqPtr_value', packet.meta_ftq_value),
            ('meta_ftqOffset', packet.meta_ftq_offset), ('meta_lqIdx_flag', packet.meta_lq_flag),
            ('meta_lqIdx_value', packet.meta_lq_value),
            ('meta_sqIdx_first_flag', packet.meta_sq_first_flag),
            ('meta_sqIdx_second_flag', packet.meta_sq_second_flag),
            ('meta_sqIdx_value', packet.meta_sq_value), ('meta_vsew', packet.meta_vsew),
            ('meta_vlmul', packet.meta_vlmul),
            ('entryIdx', packet.entry_idx), ('uopType', packet.uop_type),
            ('robIdx_flag', packet.rob_flag), ('robIdx_value', packet.rob_value),
            ('pdest', packet.pdest), ('psrc2', packet.psrc2), ('baseAddr', packet.base_addr),
            ('v0ByteMask', packet.v0_mask), ('deew', packet.deew), ('ieew', packet.ieew),
            ('emul', packet.emul), ('vl', packet.vl), ('vstart', packet.vstart),
            ('vma', packet.vma), ('vta', packet.vta), ('uopIdx', packet.uop_idx),
            ('lastUop', packet.last_uop), ('nf', packet.nf),
        ):
            _set(values, p + suffix, value)
    for kind, packets, valids in (('dataUop', beat.data, beat.data_valid), ('indexDataUop', beat.index, beat.index_valid)):
        for lane, (packet, valid) in enumerate(zip(packets, valids)):
            p = f'io_{kind}_{lane}_'
            _set(values, p + 'valid', int(valid))
            if packet is not None:
                for suffix, value in (('bits_entryIdx', packet.entry_idx), ('bits_robIdx_flag', packet.rob_flag),
                                      ('bits_robIdx_value', packet.rob_value), ('bits_op2Data', packet.op2_data)):
                    _set(values, p + suffix, value)
    for lane, update in enumerate(beat.split_req):
        p = f'io_splitReqUpdate_{lane}_'
        _set(values, p + 'valid', int(update.valid)); _set(values, p + 'bits_entryIdxOH', update.entry_oh)
        _set(values, p + 'bits_setReqSent', update.set_req_sent)
    for lane, update in enumerate(beat.merge_resp):
        p = f'io_mergeRespUpdate_{lane}_'
        for suffix, value in (('entryHitOH', update.entry_oh), ('setReqAck', update.set_req_ack),
                              ('clearReqSent', update.clear_req_sent), ('exception', int(update.exception)),
                              ('exceptionNumber', update.exception_number), ('faultElemIdx', update.fault_elem_idx)):
            _set(values, p + suffix, value)
    for prefix, update in (('splitDoneUpdate', beat.split_done), ('mergeDoneUpdate', beat.merge_done),
                           ('robClearUpdate', beat.rob_clear)):
        _set(values, f'io_{prefix}_valid', int(update.valid)); _set(values, f'io_{prefix}_bits_entryIdxOH', update.entry_oh)
        _set(values, f'io_{prefix}_bits_stateNext', update.state_next)
    for lane, update in enumerate(beat.store_update):
        p = f'io_storeDataUpdate_{lane}_'
        _set(values, p + 'valid', int(update.valid)); _set(values, p + 'bits_entryIdx', update.entry_idx)
        _set(values, p + 'bits_setDataSent', update.set_data_sent)
    _set(values, 'io_excpUpdate_valid', int(beat.excp_update.valid)); _set(values, 'io_excpUpdate_bits_entryIdxOH', beat.excp_update.entry_oh)
    _set(values, 'io_excpUpdate_bits_excpSet', beat.excp_update.excp_set)
    for suffix, value in (('valid', int(beat.redirect.valid)), ('bits_level', beat.redirect.level),
                          ('bits_robIdx_flag', beat.redirect.rob_flag), ('bits_robIdx_value', beat.redirect.rob_value)):
        _set(values, 'io_redirect_' + suffix, value)
    return values
