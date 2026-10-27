"""NF=0 instruction-shape boundary checks, not a complete ISA/data model.

Allocation remains a producer adapter. Expected memory bytes come exclusively
from the unchanged ISA oracle. The mask row encoding below is explicit NF=0
operand packing, not an assertion about actual decoder/rename execution.
"""
from collections import Counter
from dataclasses import dataclass, replace

from .driver import response_beat
from .exhaustive import ShapeSession, U64_MASK, _request, assess_shape_boundaries, build_shape_sequence
from .isa_reference import architectural_accesses, lmul
from .scenario_matrix import legal_public_feature_cases
from .types import Beat, EmptyResponse, Response


PROFILES = ('zero_mask', 'alternating', 'bank_distinct', 'clipped_restart', 'stalled_sparse')


def shape_scope(case):
    """Source/ISA shape restrictions, never a failure-dependent exclusion."""
    if case.nf:
        return 'segment_not_active_entry_scope'
    # Actual VSetFuncUnit.VillField, ELEN=64. VLMAX being integral is weaker.
    if (8 << case.vsew) > min(lmul(case.vlmul), 1) * 64:
        return 'vtype_unsupported'
    # Indexed EEW encodes the index width; its DATA width is architectural SEW.
    if case.indexed and case.data_eew != case.vsew:
        return 'indexed_data_eew_not_sew'
    return 'instruction_shape_compatible'


def compatible_shapes():
    return tuple((ordinal, case) for ordinal, case in enumerate(legal_public_feature_cases())
                 if shape_scope(case) == 'instruction_shape_compatible')


def byte_mask_row(mask, *, data_eew, index_eew, uop_idx):
    """NF=0 bank packing; index banks may subdivide one data register.

    The independent architectural mask remains unchanged. A physical byte row
    replicates each element bit across its DATA bytes, not its index width.
    """
    per_register = 16 >> data_eew
    per_uop = 16 >> max(data_eew, index_eew)
    first = (uop_idx * per_uop // per_register) * per_register
    return sum(((1 << (1 << data_eew)) - 1) << (slot << data_eew)
               for slot in range(per_register) if mask >> (first + slot) & 1)


@dataclass(frozen=True)
class Variant:
    ordinal: int
    profile: str
    mask: int
    plan: object

    def stimulus(self):
        result = self.plan.stimulus()
        first = self.plan.packets[0][0]
        result.update(ordinal=self.ordinal, profile=self.profile, architectural_mask=self.mask,
            vl=first.vl, vstart=first.vstart, vma=first.vma, vta=first.vta,
            scope='nf=0 public request/lifecycle; adapter-packed inputs, not actual rename proof')
        return result


def make_variant(case, ordinal, profile):
    if shape_scope(case) != 'instruction_shape_compatible' or profile not in PROFILES:
        raise ValueError('unsupported NF=0 instruction shape/profile')
    original = build_shape_sequence(case, ordinal)
    data_bytes = 1 << case.data_eew
    physical_elements = max(1, int(lmul(original.packets[0][0].emul))) * 16 // data_bytes
    all_bits = (1 << physical_elements) - 1
    distinct = sum(1 << i for i in range(physical_elements)
                   if (((i * 11) ^ (i >> 3)) % 7) < 3)
    distinct |= 1 | (1 << (case.vlmax - 1))
    mask = {'zero_mask': 0,
            'alternating': sum(1 << i for i in range(physical_elements) if i % 2 == 0),
            'bank_distinct': distinct, 'clipped_restart': all_bits,
            'stalled_sparse': distinct}[profile]
    vl = case.vlmax - 1 if profile == 'clipped_restart' else case.vlmax
    start = max(1, case.vlmax // 2 - 1) if profile == 'clipped_restart' and vl > 1 else 0
    assert 0 <= start < vl  # no VL=0 producer-gate assumption in this campaign
    packets = []
    for addr, data in original.packets:
        row = byte_mask_row(mask, data_eew=addr.deew, index_eew=addr.ieew, uop_idx=addr.uop_idx)
        packets.append((replace(addr, vl=vl, vstart=start, v0_byte_mask=row,
            vma=int(profile == 'bank_distinct'), vta=int(profile == 'bank_distinct')), data))
    accesses = architectural_accesses(kind='indexed' if case.indexed else 'strided',
        base=original.base, vsew=case.vsew, vlmul=case.vlmul, vl=vl, vstart=start,
        mask=mask, data_eew=case.data_eew, nf=0, stride=original.stride,
        index_values=original.index_values if case.indexed else None,
        index_eew=case.index_eew)
    expected = Counter((access.element, (access.address + byte) & U64_MASK)
        for access in accesses for byte in range(data_bytes))
    plan = replace(original, packets=tuple(packets), expected_bytes=expected)
    return Variant(ordinal, profile, mask, plan)


def ready_values(profile, cycle):
    if profile != 'stalled_sparse':
        return (True, True, True), (True, True), (True, True)
    # Start blocked, then bounded per-lane stalls; no response before fire.
    if cycle < 12:
        return (False, False, False), (False, False), (False, False)
    return (tuple((cycle + lane * 2) % 7 >= 3 for lane in range(3)),
            tuple((cycle + lane * 3) % 8 >= 4 for lane in range(2)),
            tuple((cycle + lane * 2) % 5 >= 2 for lane in range(2)))


def fired_response(outputs, beat):
    """Consumer source-contract ACKs for ACTUAL fires, not asserted valid."""
    response = response_beat(outputs,
        data=0x5A5A5A5A5A5A5A5AA5A5A5A5A5A5A5A5)
    updates = {}
    for group, ready, values in (('ldu', beat.ldu_ready, response.ldu_resp),
                                 ('sta', beat.sta_ready, response.sta_resp)):
        result = []
        for lane, value in enumerate(values):
            prefix = f'io_{group}Req_{lane}_'
            result.append(replace(value, issue_mask=(outputs[prefix + 'bits_meta_dataMask']
                << outputs[prefix + 'bits_meta_byteOffset']) & 0xFFFF)
                if value.valid and ready[lane] else Response())
        updates[group + '_resp'] = tuple(result)
    updates['empty_resp'] = tuple(value if beat.empty_ready[lane] else EmptyResponse()
                                   for lane, value in enumerate(response.empty_resp))
    return replace(response, **updates)


def _signature(outputs, group, lane):
    prefix = f'io_{group}_{lane}_'
    if group == 'lsqEmptyReq':
        leaves = ('bits_entryIdx', 'bits_issueMask')
    else:
        leaves = ('bits_meta_valid', 'bits_meta_entryIdx', 'bits_meta_elemIdx',
            'bits_meta_byteOffset', 'bits_meta_dataMask', 'bits_req_data_src_0',
            'bits_req_robIdx_flag', 'bits_req_robIdx_value')
    return tuple(outputs[prefix + name] for name in leaves)


def assess_events(variant, log):
    """Check architectural fires and owner completion, never fixed output lanes.

    VAGQArbiter's outputs are DecoupledIO, not IrrevocableIO. A request may be
    offered on another lane before acceptance; every actual fire still has to
    match the independent byte multiset exactly once. ACK timing is checked
    against the actual ready/valid fires, including the empty side.
    """
    plan, case = variant.plan, variant.plan.case
    assessment = assess_shape_boundaries(plan, log)
    errors = list(log['protocol_errors'])
    if Counter(row['entry'] for row in log['data_admissions']) != Counter(range(len(plan.packets))):
        errors.append('not every data half was admitted exactly once')
    expected_ack = Counter((row['cycle'] + 1, 'ldu' if row['kind'] == 'load' else 'sta',
        row['lane'], row['entry'], (row['data_mask'] << row['byte_offset']) & 0xFFFF)
        for row in log['requests'])
    expected_ack.update((row['cycle'] + 1, 'empty', row['lane'], row['entry'], row['issue_mask'])
                        for row in log['empty_requests'])
    actual_ack = Counter((row['cycle'], row['kind'], row['lane'], row['entry'], row['issue_mask'])
                         for row in log['responses'])
    if actual_ack != expected_ack:
        errors.append('driven ACK does not correspond exactly to previous-cycle fires')
    if case.operation == 6:
        sequence = [row['element'] for row in log['requests']]
        if sequence != sorted(sequence):
            errors.append('ordered-load PUBLIC request order decreased')
    if assessment['request_boundary_status'] != 'PASS':
        errors.append('independent raw request bytes or lifecycle mismatch')
    return assessment, sorted(set(errors))


def run_variant(session: ShapeSession, variant):
    plan, case = variant.plan, variant.plan.case
    session.reset()
    session.cycle(Beat())
    log = dict(admissions=[], data_admissions=[], requests=[], empty_requests=[],
        vrf_reads=[], std_outputs=[], writebacks=[], responses=[], flow_control=[],
        protocol_errors=[], lane_reassignments=[], blocked_cycles=0, timed_out=False, cycles=0)
    cursor = 0
    addr_sent = data_sent = False
    response = Beat()
    completed = Counter()
    held = {}
    drain = 0
    maximum_cycles = 512 + 64 * len(plan.packets) + 24 * case.vlmax
    for cycle in range(maximum_cycles):
        ldu_ready, sta_ready, empty_ready = ready_values(variant.profile, cycle)
        packet = plan.packets[cursor] if cursor < len(plan.packets) else None
        beat = replace(response, ldu_ready=ldu_ready, sta_ready=sta_ready, empty_ready=empty_ready)
        if packet:
            addr, data = packet
            beat = replace(beat, addr=(addr, None), addr_valid=(not addr_sent, False),
                stride=(data, None) if not case.indexed else (None, None),
                stride_valid=(not case.indexed and not data_sent, False),
                index=(data, None) if case.indexed else (None, None),
                index_valid=(case.indexed and not data_sent, False))
        outputs = session.cycle(beat)
        # These are the ACKs actually driven this cycle, not helper predictions.
        for kind, values in (('ldu', beat.ldu_resp), ('sta', beat.sta_resp), ('empty', beat.empty_resp)):
            for lane, value in enumerate(values):
                if value.valid:
                    log['responses'].append(dict(cycle=cycle, kind=kind, lane=lane,
                        entry=value.entry_idx, issue_mask=value.issue_mask))
        if packet:
            if not data_sent and (case.indexed or outputs['io_strideDataUop_0_ready']):
                data_sent = True
                log['data_admissions'].append(dict(cycle=cycle, entry=addr.entry_idx))
            if not addr_sent and outputs['io_addrUop_0_ready']:
                addr_sent = True
                log['admissions'].append(dict(cycle=cycle, entry=addr.entry_idx, uop_idx=addr.uop_idx))
            if addr_sent and data_sent:
                cursor += 1
                addr_sent = data_sent = False
        control = dict(cycle=cycle, ldu_ready=ldu_ready, sta_ready=sta_ready, empty_ready=empty_ready)
        for group, ready in (('lduReq', ldu_ready), ('staReq', sta_ready), ('lsqEmptyReq', empty_ready)):
            control[group + '_valid'] = []
            for lane, can_fire in enumerate(ready):
                prefix = f'io_{group}_{lane}_'
                valid = bool(outputs[prefix + 'valid'])
                control[group + '_valid'].append(valid)
                key = group, lane
                signature = _signature(outputs, group, lane)
                if key in held and (not valid or signature != held[key]):
                    if group == 'lsqEmptyReq':
                        # This is SplitCtrl's registered stage output, not the
                        # dynamically assigned multiport VAGQArbiter outputs.
                        log['protocol_errors'].append(f'{group}[{lane}] changed/dropped a backpressured request at {cycle}')
                    else:
                        log['lane_reassignments'].append(dict(cycle=cycle, group=group, lane=lane,
                            previous=held[key], current=signature, current_valid=valid,
                            note='Decoupled arbiter diagnostic; acceptance/loss checked globally'))
                if valid and not can_fire:
                    held[key] = signature
                    log['blocked_cycles'] += 1
                else:
                    held.pop(key, None)
                if not valid or not can_fire:
                    continue
                if group == 'lsqEmptyReq':
                    log['empty_requests'].append(dict(cycle=cycle, lane=lane,
                        entry=outputs[prefix + 'bits_entryIdx'], issue_mask=outputs[prefix + 'bits_issueMask']))
                elif outputs[prefix + 'bits_meta_valid']:
                    log['requests'].append(_request(outputs, group, lane, cycle))
                else:
                    log['protocol_errors'].append('unexpected native output without any native input')
        log['flow_control'].append(control)
        for lane in range(2):
            prefix = f'io_vagqStdData_{lane}_'
            if outputs[prefix + 'valid']:
                log['std_outputs'].append(dict(cycle=cycle, lane=lane,
                    sq=outputs[prefix + 'bits_sqIdx_value'], data=outputs[prefix + 'bits_data']))
        if outputs['io_vrfReadReq_valid']:
            log['vrf_reads'].append(dict(cycle=cycle, entry=outputs['io_vrfReadReq_bits_entryIdx']))
        if outputs['io_robWriteback_valid']:
            wb = dict(cycle=cycle, entry=outputs['io_robWriteback_bits_entryIdx'],
                rob=outputs['io_robWriteback_bits_robIdx_value'], rob_flag=outputs['io_robWriteback_bits_robIdx_flag'],
                exception=outputs['io_robWriteback_bits_exception'], uop_idx=outputs['io_robWriteback_bits_uopIdx'])
            log['writebacks'].append(wb)
            completed[wb['entry']] += 1
        response = fired_response(outputs, beat)
        log['cycles'] = cycle + 1
        if cursor == len(plan.packets) and all(completed[i] for i in range(len(plan.packets))):
            drain += 1
            if drain >= 4:
                break
    else:
        log['timed_out'] = True
    assessment, errors = assess_events(variant, log)
    return dict(stimulus=variant.stimulus(), events=log, assessment=assessment,
        status='FAIL' if errors else 'PASS', errors=sorted(set(errors)),
        actual_sequence_uops=len(plan.packets), max_cycles=maximum_cycles,
        final_memory_effect_verified=False, actual_producer_rename_verified=False,
        ordered_store_memory_order_verified=False)
