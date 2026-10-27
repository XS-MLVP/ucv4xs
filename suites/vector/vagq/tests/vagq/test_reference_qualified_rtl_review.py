"""Independent native counterexamples, runnable only AFTER reference qualification.

No allocated_uops/mop_info/source_prediction or output-derived expected active
mask is used. Producer metadata is validated before a downstream conclusion.
Correctness assertions stay FAIL when the unchanged RTL violates them.
"""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path

import pytest

from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.maskgen.flow_fixture import active_sites, flow_metadata, wide_flow
from vagqverify.maskgen.probe import bind_maskgen
from vagqverify.maskgen.reference import MaskRequest
from vagqverify.native import open_dut
from vagqverify.split.model import State
from vagqverify.split.probe import bind, encode
from vagqverify.split.types import Beat, Entry


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'results/vagq-reference-repair-rtl-rereview-20261020-v2'
pytestmark = pytest.mark.vagq_isa_audit


def _reference_is_qualified():
    if os.environ.get('RUN_QUALIFIED_RTL_REVIEW') != '1':
        pytest.skip('explicit independently qualified RTL review only')
    qualification = RUN / 'reference-qualification'
    result = json.loads((qualification / 'summary.json').read_text())
    assert result['architecture_reference_status'] == 'PASS_FOR_DECLARED_BOUND_DESTINATION_DOMAIN'
    assert result['counts']['noop_violations'] == result['counts']['running_violations'] == 0
    for name, expected in json.loads((qualification / 'source-hashes.json').read_text()).items():
        assert digest(ROOT / name) == expected, f'qualified reference changed: {name}'


def _beat(entry):
    return Beat(entries=(entry,) + (Entry(),) * 7,
        older_matrix=tuple(tuple(i < j for j in range(8)) for i in range(8)),
        lsu_ready=(True, True, True), empty_ready=(True, True))


class NativeSplit:
    def __init__(self, dut):
        self.dut = dut
        self.ports, self.sample = bind(dut)
        self.ports.reset.AsImmWrite()
        for signal in self.ports.inputs.values():
            signal.AsImmWrite()
        self.drive(Beat())
        self.ports.reset.Set(1)
        dut.Step(2)
        self.ports.reset.Set(0)
        dut.Step(1)

    def drive(self, beat):
        self.ports.inputs.drive(encode(beat))
        self.dut.RefreshComb()

    def cycle(self, beat):
        self.drive(beat)
        before = self.sample()
        self.dut.Step(1)
        after = self.sample()
        return before, after


def _single_request(observation):
    values = [value for value in observation.lsu if value is not None]
    assert len(values) == 1
    return values[0]


@pytest.mark.parametrize('case', ('wide_zero_mask', 'wide_tail_control', 'nonzero_first', 'index_bank_control', 'size_rounding_control'))
def test_split_requests_against_independent_stream_and_bank_binding(case, native_registration, tmp_path):
    _reference_is_qualified()
    if case == 'size_rounding_control':
        metadata = dict(elemBase=0, startFieldOffset=0, startByteOffset=0, elemValidMask=0x1001)
        active = 1
        source = MaskRequest(0xFFFF, 2, 2, 0, 1, 0, 0, 0, 0, 2)
        entry = Entry(valid=True, state=3, rob_value=32, base_addr=0x8000, op2_data=128,
            deew=2, ieew=2, nf=2, elem_valid=metadata['elemValidMask'], elem_active=active)
        expected = dict(elem_idx=0, data_mask=0xFFF, data_size=4, vaddr=0x8000)
    elif case in ('wide_zero_mask', 'wide_tail_control'):
        flow = 1 if case == 'wide_zero_mask' else 2
        fragments = wide_flow(8, 5, flow)
        metadata = flow_metadata(fragments)
        vl = 2 if case == 'wide_zero_mask' else 1
        active = active_sites(fragments, vl=vl, vstart=0, element_mask=3)
        source = MaskRequest(0xFFFF, 3, 3, 0, vl, 0, 0, 0, flow, 4)
        entry = Entry(valid=True, state=3, rob_value=32, base_addr=0x8000, op2_data=128,
            deew=3, ieew=3, nf=4, elem_base=metadata['elemBase'], start_field=metadata['startFieldOffset'],
            start_byte=metadata['startByteOffset'], elem_valid=metadata['elemValidMask'], elem_active=active)
        expected = dict(elem_idx=fragments[0].element,
            data_mask=(1 << fragments[0].width) - 1,
            vaddr=entry.base_addr + fragments[0].element * 128 + fragments[0].field * 8)
    else:
        if case == 'nonzero_first':
            # e32, five fields: flow 2 has element 1's continuation followed
            # by element 2 at site 8. The e64 index bank changes at element 2,
            # so the new bank's entry starts at that NONZERO physical site.
            fragment = wide_flow(4, 5, 2)[1]
            source = MaskRequest(0xFFFF, 2, 3, 0, 4, 0, 0, 0, 3, 4)
            fields = 5
        else:
            fragment = wide_flow(4, 6, 3)[0]  # same index bank begins at site 0
            source = MaskRequest(0xFFFF, 2, 3, 0, 4, 0, 0, 0, 3, 5)
            fields = 6
        metadata = dict(elemBase=fragment.element, startFieldOffset=fragment.field,
                        startByteOffset=fragment.site, elemValidMask=1 << fragment.site)
        active = metadata['elemValidMask']
        entry = Entry(valid=True, state=3, uop_type=4, rob_value=32,
            base_addr=0x8000, op2_data=0x100 | (0x200 << 64),
            deew=2, ieew=3, nf=fields - 1, elem_base=fragment.element,
            start_field=fragment.field, start_byte=fragment.site,
            elem_valid=active, elem_active=active)
        # This property is about element/address ownership. Raw request mask
        # versus single-flow placement is deliberately NOT conflated with it.
        expected = dict(elem_idx=2, vaddr=0x8100)
    entry = replace(entry, req_ack=(~entry.elem_valid) & 0xFFFF)
    with open_dut('MaskGen', tmp_path, register=native_registration) as producer:
        producer_actual = bind_maskgen(producer)(source)
    fixture_valid = all(producer_actual[key] == value for key, value in metadata.items())
    fixture_valid &= producer_actual['elemActiveMask'] == active
    assert fixture_valid, 'input layout not independently established; do not credit a downstream bug'
    beat = _beat(entry)
    # Verify the repaired reference itself against the independent fixture
    # BEFORE opening the SplitCtrl DUT. It is not the source of expected.
    reference = _single_request(State().following(beat).observe(Beat()))
    assert all(getattr(reference, key) == value for key, value in expected.items())
    with open_dut('SplitCtrl', tmp_path, clocked=True, register=native_registration) as dut:
        session = NativeSplit(dut)
        before, after = session.cycle(beat)
        actual = _single_request(after)
    differences = {key: dict(expected=value, actual=getattr(actual, key))
                   for key, value in expected.items() if getattr(actual, key) != value}
    atomic_json(tmp_path / 'split-review.json', dict(case=case, input_entry=asdict(entry),
        producer_input=asdict(source), producer_actual=producer_actual,
        fixture_metadata=metadata, layout_validated=bool(fixture_valid),
        expected=expected, repaired_reference=asdict(reference), actual=asdict(actual),
        before=asdict(before), after=asdict(after), differences=differences,
        status='PASS' if not differences else 'FAIL', production_scope='nf>0 forced public ports'))
    assert not differences, f'{case}: {differences}'


def test_maskgen_sparse_ownership_against_independent_wide_byte_stream(native_registration, tmp_path):
    _reference_is_qualified()
    failures, invalid_layout = [], []
    samples = controls = 0
    journal = tmp_path / 'maskgen-review.jsonl'
    with journal.open('x') as stream:
        with open_dut('MaskGen', tmp_path, register=native_registration) as dut:
            observe = bind_maskgen(dut)
            for fields in (5, 6, 7):
                for flow in range(fields):
                    fragments = wide_flow(4, fields, flow)
                    metadata = flow_metadata(fragments)
                    for vl in range(5):
                        for start in range(5):
                            for mask in range(16):
                                byte_mask = sum(0xF << (4 * element) for element in range(4) if (mask >> element) & 1)
                                request = MaskRequest(byte_mask, 2, 2, 0, vl, start, 0, 0, flow, fields - 1)
                                expected_active = active_sites(fragments, vl=vl, vstart=start, element_mask=mask)
                                actual = observe(request)
                                valid_layout = all(actual[key] == value for key, value in metadata.items())
                                row = dict(input=asdict(request), architectural_mask=mask,
                                    expected_metadata=metadata, fragments=[asdict(f) for f in fragments],
                                    layout_validated=valid_layout, expected_active=expected_active,
                                    actual=actual, matches=valid_layout and actual['elemActiveMask'] == expected_active)
                                stream.write(json.dumps(row) + '\n')
                                if not valid_layout:
                                    invalid_layout.append(row)
                                elif actual['elemActiveMask'] != expected_active:
                                    failures.append(row)
                                if mask in (0, 15):
                                    assert row['matches'], 'all-on/all-off control failed'
                                    controls += 1
                                samples += 1
                    stream.flush()
    atomic_json(tmp_path / 'maskgen-review-summary.json', dict(samples=samples,
        control_samples=controls, invalid_layout=len(invalid_layout), active_mismatches=len(failures),
        examples=failures[:5], status='PASS' if not failures and not invalid_layout else 'FAIL',
        expected_source='independent element-major byte stream, not MOP table',
        scope='nf>0 forced public component inputs'))
    assert samples == 7200 and not invalid_layout
    assert not failures, f'{len(failures)}/{samples} independently checked active-mask mismatches'


@pytest.mark.parametrize('special', (False, True), ids=('nonsegment_control', 'special7_contract'))
def test_response_ack_must_not_complete_an_unissued_element(special, native_registration, tmp_path):
    _reference_is_qualified()
    nf = 6 if special else 0
    request = MaskRequest(0xFFFF, 0, 2, 0, 4, 0, 0, 0, 0, nf)
    with open_dut('MaskGen', tmp_path, register=native_registration) as producer:
        metadata = bind_maskgen(producer)(request)
    assert metadata['elemBase'] == metadata['startByteOffset'] == metadata['startFieldOffset'] == 0
    assert metadata['elemValidMask'] == metadata['elemActiveMask']
    assert metadata['elemActiveMask'].bit_count() == 4
    index_values = (0x10, 0x80, 0xF0, 0x160)  # disjoint element memory intervals
    entry = Entry(valid=True, state=3, uop_type=6, rob_value=32,
        base_addr=0x8000, op2_data=sum(value << (32 * i) for i, value in enumerate(index_values)),
        deew=0, ieew=2, nf=nf, elem_base=0, start_field=0, start_byte=0,
        elem_valid=metadata['elemValidMask'], elem_active=metadata['elemActiveMask'])
    entry = replace(entry, req_ack=(~entry.elem_valid) & 0xFFFF)
    with open_dut('SplitCtrl', tmp_path, clocked=True, register=native_registration) as dut:
        session = NativeSplit(dut)
        _before, first = session.cycle(_beat(entry))
        first_request = _single_request(first)
        assert first_request.elem_idx == 0
        # This is the existing NewLoadUnit/NewStoreUnit SOURCE contract, not
        # an actual LSU simulation or a proposed one-hot ACK workaround.
        consumer_ack = (first_request.data_mask << first_request.byte_offset) & 0xFFFF
        sent = 1 << first_request.byte_offset
        premature = consumer_ack & entry.elem_valid & ~sent
        updated = replace(entry, req_sent=sent, req_ack=entry.req_ack | consumer_ack)
        _before, following = session.cycle(_beat(updated))
        next_request = _single_request(following)
    status = 'PASS' if not premature and next_request.elem_idx == 1 else 'FAIL'
    atomic_json(tmp_path / 'ack-contract-review.json', dict(special=special,
        producer_input=asdict(request), producer_metadata=metadata, input_entry=asdict(entry),
        index_values=index_values, first=asdict(first_request), consumer_ack=consumer_ack,
        sent_start_mask=sent, prematurely_acked_active_sites=premature,
        next=asdict(next_request), independently_required_next_element=1,
        status=status, expected_source='unissued active elements cannot be completed by another disjoint element',
        scope='public producer/split plus source-contract consumer, NOT full LSU or production decode'))
    assert status == 'PASS', f'ACK prematurely covers {premature:#x}; next element is {next_request.elem_idx}, expected 1'
