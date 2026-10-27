"""Full-length public VAGQ sequences with a separate architectural byte oracle.

``allocated_uops`` is an implementation-specific producer adapter, used only
to construct the public sequence/index-register payload.  The expected memory
bytes are computed independently by ``isa_reference.architectural_accesses``.
The consumer's shifted/truncated response placement is reported separately
from raw request bytes: neither represents real SQ/DCache memory effects.
"""
from collections import Counter
from dataclasses import asdict, dataclass, replace

from toffee import Bundle

from vagqverify.maskgen.reference import MaskRequest, allocated_uops

from .driver import Driver, response_beat
from .isa_reference import architectural_accesses, emul_encoding
from .probe import bind, encode
from .schema import OUTPUT_NAMES
from .scenario_matrix import FeatureCase, feature_case_id
from .types import AddrPacket, Beat, DataPacket


U64_MASK = (1 << 64) - 1
VERSION = 2


@dataclass(frozen=True)
class ShapePlan:
    case: FeatureCase
    packets: tuple
    layout: tuple
    index_values: tuple
    expected_bytes: Counter
    base: int
    stride: int

    def stimulus(self):
        return {
            'case': asdict(self.case),
            'shape_id': feature_case_id(self.case),
            'inventory_data_flow_count': self.case.uop_count,
            'actual_sequence_uops': len(self.packets),
            'packets': [dict(addr=asdict(addr), data=asdict(data))
                        for addr, data in self.packets],
            'index_values': list(self.index_values),
            'vl': self.case.vlmax,
            'expected_architectural_bytes': sum(self.expected_bytes.values()),
            'production_decode_scope': 'nf=0' if self.case.nf == 0 else 'forced-public-port-segment',
        }


def index_value(element, eew):
    # Each register contains distinct offsets; include the high bit to expose
    # accidental sign extension without overflowing the actual index operand.
    bits = 8 << eew
    return ((1 << (bits - 1)) | (0x20 + element * 67)) & ((1 << bits) - 1)


def build_shape_sequence(case: FeatureCase, ordinal: int):
    data_emul = emul_encoding(
        vsew=case.vsew, vlmul=case.vlmul, eew=case.data_eew,
    )
    # getIeew in Opcode.scala uses data EEW for strided operations.  ``na``
    # in the inventory is not a literal zero on this physical port.
    ieew = case.index_eew if case.indexed else case.data_eew
    request = MaskRequest(
        0xFFFF, case.data_eew, ieew, data_emul, case.vlmax, 0, 0, 0, 0, case.nf,
    )
    layout = allocated_uops(request)
    if not 1 <= len(layout) <= 8:
        raise ValueError(f'producer returned {len(layout)} uops')
    base = (0x100000 + ordinal * 0x1000) & U64_MASK
    stride = 128  # do not hide element identity behind overlapping strides
    indices = tuple(index_value(i, ieew) for i in range(case.vlmax)) if case.indexed else ()
    packets = []
    slots = 16 >> ieew
    for uop_idx, mops in enumerate(layout):
        real = [mop for mop in mops if mop.valid_bit]
        banks = {mop.index // slots for mop in real}
        if len(banks) > 1:
            raise ValueError('producer adapter crossed an index-register boundary')
        bank = min(banks, default=0)
        op2 = sum(index_value(bank * slots + i, ieew) << (i * (8 << ieew))
                  for i in range(slots)) if case.indexed else stride
        absolute_lsq = uop_idx * 16
        addr = AddrPacket(
            entry_idx=uop_idx, uop_type=case.operation,
            rob_value=64, pdest=8 + uop_idx, psrc2=32 + uop_idx,
            base_addr=base, v0_byte_mask=0xFFFF,
            deew=case.data_eew, ieew=ieew, emul=data_emul,
            vl=case.vlmax, vstart=0, vma=0, vta=0,
            uop_idx=uop_idx, last_uop=int(uop_idx == len(layout) - 1), nf=case.nf,
            lq_value=absolute_lsq & 0x7F, lq_flag=(absolute_lsq >> 7) & 1,
            sq_value=absolute_lsq & 0x3F,
            sq_first_flag=(absolute_lsq >> 6) & 1,
            sq_second_flag=((absolute_lsq >> 6) + 1) & 1,
            vsew=case.vsew, vlmul=case.vlmul,
        )
        packets.append((addr, DataPacket(uop_idx, 0, addr.rob_value, op2)))
    # The answer does NOT use the layout adapter, MOP masks or DUT outputs.
    accesses = architectural_accesses(
        kind='indexed' if case.indexed else 'strided', base=base,
        vsew=case.vsew, vlmul=case.vlmul, vl=case.vlmax, vstart=0,
        mask=(1 << case.vlmax) - 1, data_eew=case.data_eew, nf=case.nf,
        stride=stride, index_values=indices if case.indexed else None,
        index_eew=ieew,
    )
    expected = Counter((access.element, (access.address + byte) & U64_MASK)
                       for access in accesses for byte in range(1 << case.data_eew))
    return ShapePlan(case, tuple(packets), layout, indices, expected, base, stride)


def _sample_names():
    names = set()
    for group, lanes in (('lduReq', 3), ('staReq', 2)):
        for lane in range(lanes):
            prefix = f'io_{group}_{lane}_'
            names.update(prefix + suffix for suffix in (
                'valid', 'bits_meta_valid', 'bits_meta_entryIdx',
                'bits_meta_elemIdx', 'bits_meta_byteOffset', 'bits_meta_dataMask',
                'bits_req_data_src_0', 'bits_req_robIdx_flag', 'bits_req_robIdx_value',
            ))
    for lane in range(2):
        names.add(f'io_addrUop_{lane}_ready')
        names.add(f'io_strideDataUop_{lane}_ready')
        prefix = f'io_lsqEmptyReq_{lane}_'
        names.update(prefix + suffix for suffix in (
            'valid', 'bits_entryIdx', 'bits_issueMask',
        ))
    names.update(name for name in OUTPUT_NAMES if name.startswith((
        'io_vrfReadReq_', 'io_vagqStdData_',
    )))
    names.update('io_robWriteback_' + suffix for suffix in (
        'valid', 'bits_entryIdx', 'bits_robIdx_value', 'bits_robIdx_flag',
        'bits_exception', 'bits_uopIdx', 'bits_lastUop', 'bits_nf', 'bits_deew',
    ) if 'io_robWriteback_' + suffix in OUTPUT_NAMES)
    return tuple(sorted(names))


class ShapeSession:
    """Same picker/toffee public binding; only changed inputs are written.

    Every sample is a fresh compiled toffee Bundle sample.  Unchanged input
    pins retain their values; reset invalidates the write cache.  No internal
    state writes, model.checker bypass or functional-credit shortcuts.
    """
    def __init__(self, dut):
        self.dut = dut
        self.ports, _ = bind(dut)
        self.driver = Driver(dut, self.ports)
        self.names = _sample_names()
        self.sampler = Bundle(**{n: getattr(dut, n) for n in self.names}).compile_sampler()
        self.previous_inputs = None

    def reset(self):
        self.driver.reset_dut()
        self.previous_inputs = None

    def cycle(self, beat):
        values = encode(beat)
        for name, value in values.items():
            if self.previous_inputs is None or self.previous_inputs[name] != value:
                self.ports.inputs[name].Set(value)
        self.previous_inputs = values
        self.dut.RefreshComb()
        sampled = self.sampler()
        outputs = {n: getattr(sampled, n).as_int() for n in self.names}
        self.driver.tick()
        return outputs


def _packet_beat(response, packet, *, send_data):
    if packet is None:
        return response
    addr, data = packet
    return replace(
        response, addr=(addr, None), addr_valid=(True, False),
        stride=(data, None) if addr.uop_type < 4 and send_data else (None, None),
        stride_valid=(addr.uop_type < 4 and send_data, False),
        index=(data, None) if addr.uop_type >= 4 and send_data else (None, None),
        index_valid=(addr.uop_type >= 4 and send_data, False),
    )


def _request(outputs, group, lane, cycle):
    prefix = f'io_{group}_{lane}_'
    return {
        'cycle': cycle, 'kind': 'load' if group == 'lduReq' else 'store',
        'lane': lane, 'entry': outputs[prefix + 'bits_meta_entryIdx'],
        'element': outputs[prefix + 'bits_meta_elemIdx'],
        'byte_offset': outputs[prefix + 'bits_meta_byteOffset'],
        'data_mask': outputs[prefix + 'bits_meta_dataMask'],
        'address': outputs[prefix + 'bits_req_data_src_0'],
        'rob': outputs[prefix + 'bits_req_robIdx_value'],
        'rob_flag': outputs[prefix + 'bits_req_robIdx_flag'],
    }


def observed_bytes(requests):
    """Retain occurrence counts and all bytes, not first-address sets.

    Raw bytes include the request's entire dataMask.  Effective bytes model
    the actual 16-byte public response placement (shift then truncate).  A
    wide segment request may extend beyond its current flow; that difference
    is retained as raw diagnostics, never called real memory-effect proof.
    """
    raw, effective, placement = Counter(), Counter(), Counter()
    for req in requests:
        for byte in range(16):
            if not req['data_mask'] & (1 << byte):
                continue
            key = (req['element'], (req['address'] + byte) & U64_MASK)
            raw[key] += 1
            local = req['byte_offset'] + byte
            if local < 16:
                effective[key] += 1
                placement[(req['entry'], local)] += 1
    return raw, effective, placement


def _counter_rows(counter):
    return [dict(key=list(key) if isinstance(key, tuple) else key, count=value)
            for key, value in sorted(counter.items())]


def compare_shape(plan, log):
    """Frozen v2 composite diagnostic, retained for historical comparison.

    Its placement-vs-architecture error is NOT an isolated address verdict.
    Use assess_shape_boundaries() for explicitly scoped, independent results.
    """
    errors = []
    expected_entries = Counter(range(len(plan.packets)))
    accepted = Counter(record['entry'] for record in log['admissions'])
    completed = Counter(record['entry'] for record in log['writebacks'])
    if accepted != expected_entries:
        errors.append('not every uop address was accepted exactly once')
    if completed != expected_entries:
        errors.append('not every uop wrote back exactly once')
    for wb in log['writebacks']:
        if (wb['entry'] not in range(len(plan.packets)) or wb['rob'] != 64
                or wb['rob_flag'] != 0 or wb['exception']
                or wb['uop_idx'] != wb['entry']):
            errors.append('writeback ownership/exception/uop mismatch')
    for req in log['requests']:
        if (req['rob'] != 64 or req['rob_flag'] != 0
                or req['entry'] not in range(len(plan.packets))
                or (req['kind'] == 'load') != plan.case.load):
            errors.append('request ownership/operation mismatch')
    raw, actual, placement = observed_bytes(log['requests'])
    missing, extra = plan.expected_bytes - actual, actual - plan.expected_bytes
    duplicate_placements = Counter({key: count - 1 for key, count in placement.items() if count > 1})
    if missing or extra:
        errors.append('full architectural byte multiset mismatch')
    if duplicate_placements:
        errors.append('duplicate public response placement')
    if log['timed_out']:
        errors.append('bounded public protocol timeout')
    return {
        'status': 'PASS' if not errors else 'FAIL',
        'errors': sorted(set(errors)),
        'expected_byte_occurrences': sum(plan.expected_bytes.values()),
        'raw_request_byte_occurrences': sum(raw.values()),
        'placed_byte_occurrences': sum(actual.values()),
        'missing_byte_occurrences': sum(missing.values()),
        'extra_byte_occurrences': sum(extra.values()),
        'duplicate_placements': _counter_rows(duplicate_placements),
        'missing_bytes': _counter_rows(missing),
        'extra_bytes': _counter_rows(extra),
    }


def assess_shape_boundaries(plan, log):
    """Separate architectural requests, lifecycle, and synthetic placement.

    No overall ISA/data PASS is inferred from request bytes or completions.
    Original v2 statuses are kept verbatim, rather than rewriting old FAILs.
    ``projection_matches_architecture`` is a diagnostic comparison, not a
    contract that all bytes of a segment must fit into a single flow.
    """
    legacy = compare_shape(plan, log)
    raw, placed, locations = observed_bytes(log['requests'])
    missing, extra = plan.expected_bytes - raw, raw - plan.expected_bytes
    lifecycle_errors = [error for error in legacy['errors'] if error not in (
        'full architectural byte multiset mismatch',
        'duplicate public response placement',
    )]
    request_status = 'PASS' if not missing and not extra else 'FAIL'
    lifecycle_status = 'PASS' if not lifecycle_errors else 'FAIL'
    placement_missing = plan.expected_bytes - placed
    placement_extra = placed - plan.expected_bytes
    duplicates = Counter({key: count - 1 for key, count in locations.items() if count > 1})
    return {
        'version': 1,
        'architectural_requests': {
            'status': request_status,
            'scope': 'Full raw (element,address) byte multiset ONLY; not data or memory effects',
            'expected_byte_occurrences': sum(plan.expected_bytes.values()),
            'observed_byte_occurrences': sum(raw.values()),
            'missing_byte_occurrences': sum(missing.values()),
            'extra_byte_occurrences': sum(extra.values()),
            'missing_bytes': _counter_rows(missing),
            'extra_bytes': _counter_rows(extra),
        },
        'public_lifecycle': {'status': lifecycle_status, 'errors': lifecycle_errors},
        'request_boundary_status': 'PASS' if request_status == lifecycle_status == 'PASS' else 'FAIL',
        'response_placement': {
            'status': 'OBSERVED_NOT_ACCEPTANCE',
            'scope': 'Synthetic single-flow projection, NOT architectural memory/data proof',
            'projection_matches_architecture': not placement_missing and not placement_extra,
            'placed_byte_occurrences': sum(placed.values()),
            'spilled_request_byte_occurrences': sum(raw.values()) - sum(placed.values()),
            'missing_vs_architecture': sum(placement_missing.values()),
            'extra_vs_architecture': sum(placement_extra.values()),
            'duplicate_location_occurrences': sum(duplicates.values()),
            'duplicate_locations': _counter_rows(duplicates),
        },
        'legacy_v2': {'status': legacy['status'], 'errors': legacy['errors']},
        'full_data_and_memory_effect': {'status': 'NOT_VERIFIED'},
        'overall_isa_acceptance': 'NOT_VERIFIED',
    }


def run_shape_sequence(session, case, ordinal, *, plan=None, max_idle=64):
    plan = plan or build_shape_sequence(case, ordinal)
    session.reset()
    session.cycle(Beat())
    log = dict(admissions=[], requests=[], empty_requests=[], vrf_reads=[],
               std_outputs=[], writebacks=[], responses=[], timed_out=False, cycles=0)
    cursor, data_sent = 0, False
    response = Beat()
    last_progress = 0
    completed = Counter()
    max_cycles = 128 + 32 * len(plan.packets) + 8 * case.vlmax
    drain = 0
    for cycle in range(max_cycles):
        packet = plan.packets[cursor] if cursor < len(plan.packets) else None
        beat = _packet_beat(response, packet, send_data=not data_sent)
        outputs = session.cycle(beat)
        events_before = sum(len(log[key]) for key in (
            'admissions', 'requests', 'empty_requests', 'vrf_reads', 'std_outputs', 'writebacks',
        ))
        if packet is not None:
            addr, _data = packet
            if not data_sent:
                if case.indexed or outputs['io_strideDataUop_0_ready']:
                    data_sent = True
            if outputs['io_addrUop_0_ready']:
                if not data_sent:
                    raise RuntimeError('address accepted before its one-shot data producer; driver cannot advance')
                log['admissions'].append(dict(cycle=cycle, entry=addr.entry_idx, uop_idx=addr.uop_idx))
                cursor += 1
                data_sent = False
        for group, lanes in (('lduReq', 3), ('staReq', 2)):
            for lane in range(lanes):
                prefix = f'io_{group}_{lane}_'
                if outputs[prefix + 'valid'] and outputs[prefix + 'bits_meta_valid']:
                    log['requests'].append(_request(outputs, group, lane, cycle))
        for lane in range(2):
            prefix = f'io_lsqEmptyReq_{lane}_'
            if outputs[prefix + 'valid']:
                log['empty_requests'].append(dict(
                    cycle=cycle, entry=outputs[prefix + 'bits_entryIdx'],
                    issue_mask=outputs[prefix + 'bits_issueMask'], lane=lane,
                ))
            prefix = f'io_vagqStdData_{lane}_'
            if outputs[prefix + 'valid']:
                log['std_outputs'].append(dict(cycle=cycle, lane=lane,
                    sq=outputs[prefix + 'bits_sqIdx_value'], data=outputs[prefix + 'bits_data']))
        if outputs['io_vrfReadReq_valid']:
            log['vrf_reads'].append(dict(cycle=cycle, entry=outputs['io_vrfReadReq_bits_entryIdx']))
        if outputs['io_robWriteback_valid']:
            wb = dict(cycle=cycle, entry=outputs['io_robWriteback_bits_entryIdx'],
                rob=outputs['io_robWriteback_bits_robIdx_value'],
                rob_flag=outputs['io_robWriteback_bits_robIdx_flag'],
                exception=outputs['io_robWriteback_bits_exception'],
                uop_idx=outputs['io_robWriteback_bits_uopIdx'])
            log['writebacks'].append(wb)
            completed[wb['entry']] += 1
        # Real NewLoadUnit/NewStoreUnit source contracts return all dataMask
        # bits shifted by byteOffset, not just the request's first bit.
        response = response_beat(outputs, data=0x5A5A5A5A5A5A5A5AA5A5A5A5A5A5A5A5)
        updates = {}
        for group, responses in (('ldu', response.ldu_resp), ('sta', response.sta_resp)):
            corrected = []
            for lane, resp in enumerate(responses):
                if resp.valid:
                    prefix = f'io_{group}Req_{lane}_'
                    issue_mask = (outputs[prefix + 'bits_meta_dataMask'] <<
                                  outputs[prefix + 'bits_meta_byteOffset']) & 0xFFFF
                    resp = replace(resp, issue_mask=issue_mask)
                    log['responses'].append(dict(cycle=cycle + 1, kind=group,
                        entry=resp.entry_idx, issue_mask=issue_mask))
                corrected.append(resp)
            updates[group + '_resp'] = tuple(corrected)
        response = replace(response, **updates)
        log['cycles'] = cycle + 1
        events_after = sum(len(log[key]) for key in (
            'admissions', 'requests', 'empty_requests', 'vrf_reads', 'std_outputs', 'writebacks',
        ))
        if events_after != events_before:
            last_progress = cycle
        if cursor == len(plan.packets) and all(completed[i] for i in range(len(plan.packets))):
            drain += 1
            if drain >= 4:
                break
        if cycle - last_progress >= max_idle:
            log['timed_out'] = True
            break
    else:
        log['timed_out'] = True
    verdict = compare_shape(plan, log)
    return {
        'version': VERSION, 'ordinal': ordinal, 'shape_id': feature_case_id(case),
        'actual_sequence_uops': len(plan.packets),
        'admitted_uops': len(log['admissions']), 'writebacks': len(log['writebacks']),
        'cycles': log['cycles'], **verdict, 'events': log,
        'scope': 'public request/response-placement model; no final memory effect proof',
    }
