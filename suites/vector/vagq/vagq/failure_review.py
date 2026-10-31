"""Post-run causal review; never changes the frozen exhaustive test or oracle."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate_protocol, mop_info

from .exhaustive import ShapeSession, U64_MASK, build_shape_sequence, observed_bytes
from .scenario_matrix import feature_case_id


FAMILIES = {
    'narrow_spill': 'Address claim/checker scope mismatch; full raw request byte Counter is correct; full segment data placement remains unverified.',
    'zero_mask': 'Forced-port wide-segment zero request mask; response cannot ACK the pending start bit; not a confirmed production-path defect.',
    'special7': 'Forced-port producer/consumer contract inconsistency: 4-byte layout stride versus 7-byte request/ACK width.',
    'wide_offset': 'Forced-port wide-segment selector uses site.orR and misidentifies a first MOP with nonzero startByteOffset.',
}


def metadata(plan, entry):
    addr = plan.packets[entry][0]
    req = MaskRequest(addr.v0_byte_mask, addr.deew, addr.ieew, addr.emul,
                      addr.vl, addr.vstart, addr.vma, addr.vta, addr.uop_idx, addr.nf)
    return mop_info(req), evaluate_protocol(req)


def source_prediction(plan, request):
    """Explain actual public fields from source equations, NOT an ISA answer."""
    entry, site = request['entry'], request['byte_offset']
    addr, data = plan.packets[entry]
    info, _ = metadata(plan, entry)
    width = (addr.nf + 1) << addr.deew
    special = addr.nf == 6 and addr.deew == 0 and addr.ieew == 2
    offset = (site >> addr.ieew) if special else int(bool(site)) if width > 16 else (
        ((site - info.first_byte) >> addr.deew) // (addr.nf + 1))
    element = info.first + offset
    if info.first_field and site == 0:
        remaining = (addr.nf + 1 - info.first_field) << addr.deew
        mask = (1 << remaining) - 1 if remaining <= 16 else 0
    else:
        remaining = None
        mask = (1 << min(width, 16)) - 1
    first_field = info.first_field if offset == 0 else 0
    if plan.case.indexed:
        bits, slots = 8 << addr.ieew, 16 >> addr.ieew
        displacement = (data.op2_data >> ((element % slots) * bits)) & ((1 << bits) - 1)
    else:
        displacement = element * data.op2_data
    address = (addr.base_addr + displacement + (first_field << addr.deew)) & U64_MASK
    return dict(element=element, data_mask=mask, address=address,
                start_byte=info.first_byte, start_field=info.first_field,
                remaining_width=remaining, idx_offset=offset)


def analyze_failure(row, case):
    path = Path(row['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    record = json.loads(path.read_text())
    plan = build_shape_sequence(case, row['ordinal'])
    assert record['stimulus'] == plan.stimulus()
    events = record['events']
    raw, placed, placements = observed_bytes(events['requests'])
    checks = dict(input_sequence_matches_frozen_plan=True,
                  unique_admission=Counter(x['entry'] for x in events['admissions']) == Counter(range(len(plan.packets))))
    predictions = [source_prediction(plan, req) for req in events['requests']]
    checks['all_request_source_equations_match'] = all(
        all(req[key] == pred[key] for key in ('element', 'data_mask', 'address'))
        for req, pred in zip(events['requests'], predictions))
    expected_responses = Counter((req['cycle'] + 1, 'ldu' if req['kind'] == 'load' else 'sta',
        req['entry'], (req['data_mask'] << req['byte_offset']) & 0xFFFF)
        for req in events['requests'])
    actual_responses = Counter((resp['cycle'], resp['kind'], resp['entry'], resp['issue_mask'])
                               for resp in events['responses'])
    checks['all_lsu_responses_follow_recorded_source_contract'] = actual_responses == expected_responses
    special = case.indexed and case.nf == 6 and case.data_eew == 0 and case.index_eew == 2
    width = (case.nf + 1) << case.data_eew
    family = 'special7' if special else 'zero_mask' if events['timed_out'] else 'narrow_spill' if width <= 16 else 'wide_offset'
    witnesses = {}
    completed = {x['entry'] for x in events['writebacks']}
    missing_wb = sorted(set(range(len(plan.packets))) - completed)
    if family == 'narrow_spill':
        spilled = Counter()
        for req in events['requests']:
            for byte in range(16):
                if req['data_mask'] & (1 << byte) and req['byte_offset'] + byte >= 16:
                    spilled[(req['element'], (req['address'] + byte) & U64_MASK)] += 1
        checks.update(raw_counter_exactly_matches_independent_architecture=raw == plan.expected_bytes,
            failure_exactly_explained_by_consumer_clipping=plan.expected_bytes - placed == spilled and not placed - plan.expected_bytes,
            no_duplicate_placements=all(count == 1 for count in placements.values()),
            all_uops_completed=not missing_wb and len(events['writebacks']) == len(plan.packets))
        witnesses = dict(spilled_byte_occurrences=sum(spilled.values()),
            raw_byte_occurrences=sum(raw.values()), placed_byte_occurrences=sum(placed.values()))
    elif family == 'zero_mask':
        zero = [dict(request=req, prediction=pred) for req, pred in zip(events['requests'], predictions) if not req['data_mask']]
        zero_entries = {x['request']['entry'] for x in zero}
        predicted_missing = (set(range(min(zero_entries), len(plan.packets)))
                             if zero_entries and case.operation == 6 else zero_entries)
        unacked = {}
        for entry in missing_wb:
            _, masks = metadata(plan, entry)
            ack = (~masks['elemValidMask']) & 0xFFFF
            for resp in events['responses']:
                if resp['entry'] == entry:
                    ack |= resp['issue_mask']
            for req in events['empty_requests']:
                if req['entry'] == entry:
                    ack |= req['issue_mask']
            unacked[str(entry)] = (~ack) & 0xFFFF
        checks.update(valid_zero_mask_observed=bool(zero),
            all_zero_masks_explained_by_unclamped_remaining_width=all(
                x['request']['byte_offset'] == 0 and x['prediction']['start_field'] > 0
                and x['prediction']['remaining_width'] > 16 for x in zero),
            missing_writebacks_exactly_follow_zero_ack_or_ordered_dependency=set(missing_wb) == predicted_missing,
            zero_ack_bit_remains_pending=all(unacked.get(str(entry), 0) & 1 for entry in zero_entries))
        witnesses = dict(zero_mask_requests=zero, missing_writeback_entries=missing_wb,
                         reconstructed_unacked_bits=unacked,
                         ordered_dependency=case.operation == 6)
    elif family == 'special7':
        active_sites = set()
        for entry in range(len(plan.packets)):
            _, masks = metadata(plan, entry)
            active_sites.update((entry, byte) for byte in range(16) if masks['elemActiveMask'] & (1 << byte))
        issued = {(req['entry'], req['byte_offset']) for req in events['requests']}
        unissued = active_sites - issued
        preacked = set()
        for entry, byte in unissued:
            if any(resp['entry'] == entry and resp['issue_mask'] & (1 << byte)
                   for resp in events['responses']):
                preacked.add((entry, byte))
        checks.update(special_layout_stride_four=all(
                mop.byte % 4 == 0 for mops in plan.layout for mop in mops if mop.valid_bit),
            request_width_seven=all(req['data_mask'] == 0x7F for req in events['requests']),
            ordered_missing_sites_exactly_preacked=unissued == preacked,
            nonordered_raw_requests_match=raw == plan.expected_bytes if case.operation != 6 else True,
            nonordered_overlap_observed=any(n > 1 for n in placements.values()) if case.operation != 6 else True)
        witnesses = dict(layout_stride_bytes=4, request_width_bytes=7,
            unissued_active_sites=sorted(unissued), prematurely_acked_sites=sorted(preacked),
            raw_counter_matches=raw == plan.expected_bytes,
            duplicate_location_count=sum(n - 1 for n in placements.values() if n > 1))
    else:
        corrections = []
        fixed = deepcopy(events['requests'])
        for req in fixed:
            info, _ = metadata(plan, req['entry'])
            if req['byte_offset'] == info.first_byte and info.first_byte > 0:
                intended = next(m for m in plan.layout[req['entry']] if m.valid_bit and m.byte == req['byte_offset'])
                corrections.append(dict(entry=req['entry'], site=req['byte_offset'],
                    start_byte=info.first_byte, intended_element=intended.index,
                    actual_element=req['element']))
                req['element'] = intended.index
                req['address'] = (plan.base + plan.index_values[intended.index]
                                  + (intended.field << case.data_eew)) & U64_MASK
        _, corrected, _ = observed_bytes(fixed)
        checks.update(nonzero_first_site_witness=bool(corrections),
            first_mop_misidentified_by_plus_one=all(x['actual_element'] == x['intended_element'] + 1 for x in corrections),
            element_address_substitution_explains_entire_byte_difference=corrected == plan.expected_bytes)
        witnesses = dict(corrections=corrections,
            substitution_scope='offline causal check only, not a DUT fix or passing execution')
    return dict(ordinal=row['ordinal'], shape_id=feature_case_id(case),
        original_result=str(path), original_sha256=row['sha256'], family=family,
        classification=FAMILIES[family], checks=checks,
        all_checks_satisfied=all(checks.values()), witnesses=witnesses,
        boundary='nf>0 forced-port; current production decoder excludes this input',
        indexed_data_eew_equals_vsew=(case.data_eew == case.vsew) if case.indexed else None)


class ReviewSession(ShapeSession):
    """Explicit counterfactual responses; never counted as acceptance passes."""
    def __init__(self, dut):
        super().__init__(dut)
        self.policy = 'baseline'
        self.last_outputs = None
        self.driven_responses = []
        self.overrides = []
        self.review_cycle = 0

    def reset(self):
        super().reset()
        self.last_outputs = None
        self.driven_responses = []
        self.overrides = []
        self.review_cycle = 0

    def cycle(self, beat):
        changes = {}
        for kind, responses in (('ldu', beat.ldu_resp), ('sta', beat.sta_resp)):
            modified = []
            for lane, resp in enumerate(responses):
                if resp.valid and self.last_outputs is not None:
                    prefix = f'io_{kind}Req_{lane}_'
                    if (self.policy == 'onehot_all' or self.policy == 'ack_zero_only'
                            and self.last_outputs[prefix + 'bits_meta_dataMask'] == 0):
                        actual = 1 << self.last_outputs[prefix + 'bits_meta_byteOffset']
                        if actual != resp.issue_mask:
                            self.overrides.append(dict(cycle=self.review_cycle - 1, kind=kind, lane=lane,
                                entry=resp.entry_idx, original=resp.issue_mask, driven=actual))
                        resp = replace(resp, issue_mask=actual)
                if resp.valid:
                    self.driven_responses.append(dict(cycle=self.review_cycle - 1, kind=kind,
                        lane=lane, entry=resp.entry_idx, issue_mask=resp.issue_mask))
                modified.append(resp)
            changes[kind + '_resp'] = tuple(modified)
        actual_beat = replace(beat, **changes)
        outputs = super().cycle(actual_beat)
        self.last_outputs = outputs
        self.review_cycle += 1
        return outputs
