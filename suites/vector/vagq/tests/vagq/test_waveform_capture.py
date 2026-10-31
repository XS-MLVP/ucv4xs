"""Regression for real FST capture, independent of functional coverage claims."""

import json

import pytest

from suites.vector.vagq.legacy_pins import P
from suites.vector.vagq.native import open_dut
from suites.vector.vagq.vagq.env import Env
from suites.vector.vagq.vagq.external_env import PublicVAGQEnvironment, Scenario
from suites.vector.vagq.vagq.types import AddrPacket, DataPacket
from suites.vector.vagq.waveform import convert_fst, read_public_samples


pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_vagq_fst_contains_clock_reset_requests_and_writeback(native_registration, tmp_path):
    addr = AddrPacket(
        entry_idx=0, uop_type=0, rob_value=64, pdest=16, psrc2=32,
        base_addr=0x4000, v0_byte_mask=0xffff,
        deew=0, ieew=0, emul=0, vl=2, vsew=0, vlmul=0,
    )
    data = DataPacket(entry_idx=0, rob_value=64, op2_data=8)
    with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
        assert dut.GetWaveFormat() == 'fst'
        log = PublicVAGQEnvironment(log_root=tmp_path / 'stimulus-logs').run(
            Env.create(dut), Scenario(
                name='fst-capture-strided-load', packets=((addr, data),),
                response_latency=1, min_cycles=24, max_cycles=80,
            ),
        )
    assert log.completed and not log.timed_out
    assert len(log.accepted_requests) == 2 and len(log.writebacks) == 1

    names = ['clock', 'reset', P.p_addrUop_0_valid, P.p_addrUop_0_ready,
             P.p_robWriteback_valid, P.p_robWriteback_bits_entryIdx]
    for lane in range(3):
        prefix = P.io(f'lduReq_{lane}_')
        names.extend(prefix + suffix for suffix in (
            'valid', 'ready', 'bits_meta_valid', 'bits_meta_entryIdx',
            'bits_req_data_src_0', 'bits_meta_dataMask',
        ))
    vcd = convert_fst(tmp_path / 'VAGQ.fst', tmp_path / 'VAGQ.vcd')
    samples = read_public_samples(vcd, names)
    clock_values = {sample['values']['clock'] for sample in samples}
    reset_values = {sample['values']['reset'] for sample in samples}
    clock_edges = sum(
        left['values']['clock'] != right['values']['clock']
        for left, right in zip(samples, samples[1:])
    )
    assert clock_values == {0, 1}
    assert reset_values == {0, 1}
    assert clock_edges >= 2 * log.cycles
    assert any(
        left['values']['reset'] == 1 and right['values']['reset'] == 0
        for left, right in zip(samples, samples[1:])
    )
    requests = set()
    writeback_entries = set()
    reset_asserted = False
    for sample in samples:
        values = sample['values']
        if values['reset'] == 1:
            reset_asserted = True
        # Random register initialization before the first reset edge is not
        # a request accepted by the post-reset environment. Observe the same
        # reset-delimited interval as its public event log.
        if not reset_asserted or values['reset'] != 0:
            continue
        for lane in range(3):
            prefix = P.io(f'lduReq_{lane}_')
            if all(values[prefix + suffix] == 1 for suffix in ('valid', 'ready', 'bits_meta_valid')):
                requests.add((values[prefix + 'bits_meta_entryIdx'],
                              values[prefix + 'bits_req_data_src_0'],
                              values[prefix + 'bits_meta_dataMask']))
        if values[P.p_robWriteback_valid] == 1:
            writeback_entries.add(values[P.p_robWriteback_bits_entryIdx])
    expected_requests = {(item['entry'], item['address'], item['mask']) for item in log.accepted_requests}
    assert requests == expected_requests
    assert writeback_entries == {item['entry'] for item in log.writebacks}
    summary = {
        'source': 'actual native FST decoded by fst2vcd; not synthesized from logs',
        'observation_window': 'after reset assertion and subsequent deassertion observed in the native waveform',
        'first_time': samples[0]['time'], 'last_time': samples[-1]['time'],
        'native_timepoints': len(samples), 'clock_edges': clock_edges,
        'clock_values': sorted(clock_values), 'reset_values': sorted(reset_values),
        'waveform_request_signatures': sorted(requests),
        'event_log_request_signatures': sorted(expected_requests),
        'waveform_writeback_entries': sorted(writeback_entries),
        'request_signatures_match_event_log': requests == expected_requests,
        'limitation': 'signatures are compared, not a cycle-exact whole-chip or ISA proof',
    }
    (tmp_path / 'waveform-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (tmp_path / 'waveform-samples.json').write_text(json.dumps(samples, indent=2) + '\n')
