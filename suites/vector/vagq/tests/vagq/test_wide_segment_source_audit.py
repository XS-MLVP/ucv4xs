
import ucv.runtime as ucv_paths
"""Audit the old wide-segment claim against producer and consumer contracts.

These tests distinguish direct VAGQ injection from a reachable decoded
instruction.  The downstream arithmetic below is a source-contract check,
not a simulation of NewLoadUnit or an independent architectural-state oracle.
"""
from collections import Counter
from dataclasses import asdict, replace
import json
from pathlib import Path
import re

import pytest

from suites.vector.vagq.legacy_pins import P
from suites.vector.vagq.vagq.driver import response_beat
from suites.vector.vagq.vagq.types import AddrPacket, Beat, DataPacket


pytestmark = [
    pytest.mark.vagq_isa_audit,
    pytest.mark.toffee_functional_coverage(False),
]

ROOT = Path(__file__).resolve().parents[2]
XS = ucv_paths.source_path_for(ROOT)
SCALA = XS / 'src/main/scala/xiangshan'


def test_current_decoder_excludes_segment_uops_from_vagq(tmp_path):
    from ucv.common import read, file_hash
    from ucv.config import Project
    contract = read(ROOT / 'manifest/source-contract.json')
    suite = Project().suite('vagq')
    assert suite.baseline['name'] == contract['baseline'], 'Re-audit the source contract for a new baseline'
    for relative, expected in contract['source_files'].items():
        assert file_hash(XS / relative) == expected, relative
    rtl = ucv_paths.soc_rtl_for(ROOT)
    for relative, expected in contract['rtl_files'].items():
        assert file_hash(rtl / relative) == expected, relative
    (tmp_path / 'decoder-reachability.json').write_text(json.dumps({
        'method': contract['scope'],
        'conclusion': contract['conclusion'],
        'nf_field': 'rawInst[31:29]',
        'production_useVAGQ_for_nf4': False,
        'standalone_port_can_be_forced': True,
        'source_hashes': contract['source_files'],
        'rtl_hashes': contract['rtl_files'],
    }, indent=2) + '\n')


@pytest.mark.parametrize('nf', (0, 4), ids=('reachable-nonsegment-control', 'forced-segment'))
def test_real_root_with_source_matched_response_masks(vagq_env, tmp_path, nf):
    indices = (0x20, 0x40, 0x60, 0x80)
    base = 0x9000
    fields = nf + 1
    flow_count = fields  # Four e32 elements, LMUL=1, VLEN=16 bytes.
    index_data = sum(value << (8 * index) for index, value in enumerate(indices))
    packets = []
    for flow in range(flow_count):
        addr = AddrPacket(
            entry_idx=flow, uop_type=4, rob_value=64,
            pdest=16 + flow, psrc2=32 + flow,
            base_addr=base, v0_byte_mask=0xffff,
            deew=2, ieew=0, emul=0,
            vl=4, vstart=0, nf=nf, vsew=2, vlmul=0,
            uop_idx=flow, last_uop=int(flow == flow_count - 1),
        )
        data = DataPacket(entry_idx=flow, rob_value=64, op2_data=index_data)
        packets.append((addr, data))

    requests = []
    responses = []
    writebacks = []
    admission = []
    dut = vagq_env
    dut.reset()
    dut.driver.drive(Beat())
    dut.sample()
    dut.driver.tick()
    beat = Beat()
    cursor = 0
    for cycle in range(160):
        if cursor < len(packets):
            addr, data = packets[cursor]
            beat = replace(
                beat, addr=(addr, None), addr_valid=(True, False),
                index=(data, None), index_valid=(True, False),
            )
        dut.driver.drive(beat)
        output = dut.sample()
        if cursor < len(packets) and output[P.p_addrUop_0_ready]:
            admission.append({'cycle': cycle, 'flow': cursor})
            cursor += 1
        for lane in range(3):
            prefix = P.io(f'lduReq_{lane}_')
            if output[prefix + 'valid'] and output[prefix + 'bits_meta_valid']:
                record = {
                    'cycle': cycle, 'lane': lane,
                    'entry': output[prefix + 'bits_meta_entryIdx'],
                    'element': output[prefix + 'bits_meta_elemIdx'],
                    'byte_offset': output[prefix + 'bits_meta_byteOffset'],
                    'data_mask': output[prefix + 'bits_meta_dataMask'],
                    'data_size': output[prefix + 'bits_meta_dataSize'],
                    'address': output[prefix + 'bits_req_data_src_0'],
                    'pdest': output[prefix + 'bits_req_toRF_pdest'],
                }
                record['lsu_response_mask'] = (
                    record['data_mask'] << record['byte_offset']
                ) & 0xffff
                requests.append(record)
        for lane, response in enumerate(beat.ldu_resp):
            if response.valid:
                responses.append({'cycle': cycle, 'lane': lane, **asdict(response)})
        if output[P.p_robWriteback_valid]:
            writebacks.append({
                'cycle': cycle,
                'entry': output[P.p_robWriteback_bits_entryIdx],
                'exception': output[P.p_robWriteback_bits_exception],
            })
        dut.driver.tick()

        # NewLoadUnit.scala returns dataMask << byteOffset, truncated to the
        # 16-bit public response leaf, not the old one-hot environment mask.
        beat = response_beat(output)
        beat = replace(beat, ldu_resp=tuple(
            replace(response, issue_mask=(
                output[P.io(f'lduReq_{lane}_bits_meta_dataMask')]
                << output[P.io(f'lduReq_{lane}_bits_meta_byteOffset')]
            ) & 0xffff) if response.valid else response
            for lane, response in enumerate(beat.ldu_resp)
        ))
        if len(writebacks) == flow_count and cycle >= 24:
            break

    raw_memory = Counter()
    destination = {}
    duplicate_destinations = []
    effective_memory = Counter()
    for request in requests:
        assert request['pdest'] == 16 + request['entry']
        for byte in range(16):
            if not request['data_mask'] & (1 << byte):
                continue
            memory_address = request['address'] + byte
            raw_memory[memory_address] += 1
            # NewLoadUnit's returned 128-bit data and 16-bit mask are shifted
            # by byteOffset and truncated; destination is a staging flow.
            destination_byte = request['byte_offset'] + byte
            if destination_byte >= 16:
                continue
            key = (request['entry'], destination_byte)
            if key in destination:
                duplicate_destinations.append(key)
            destination[key] = memory_address
            effective_memory[memory_address] += 1

    # Normative element/field address equation is independent of the VAGQ
    # table.  Only the packing into 16-byte staging flows is an adapter rule.
    expected = {}
    for element, index in enumerate(indices):
        for field in range(fields):
            for byte in range(4):
                packed = (element * fields + field) * 4 + byte
                expected[(packed // 16, packed % 16)] = base + index + field * 4 + byte

    report = {
        'scope': 'standalone injection' if nf else 'nonsegment control',
        'production_reachability': False if nf else 'nf guard permits; not a full decoder simulation',
        'nf': nf,
        'stimulus': [{'addr': asdict(addr), 'data': asdict(data)} for addr, data in packets],
        'accepted_addresses': admission,
        'accepted_requests': requests,
        'driven_responses': responses,
        'writebacks': writebacks,
        'raw_request_byte_occurrences': sum(raw_memory.values()),
        'raw_duplicate_bytes': sum(count - 1 for count in raw_memory.values()),
        'source_contract_destination_bytes': len(destination),
        'source_contract_duplicate_destinations': duplicate_destinations,
        'source_contract_effective_memory_duplicates': sum(count - 1 for count in effective_memory.values()),
        'source_contract_destination_matches_packed_oracle': destination == expected,
        'consumer_is_simulated': False,
        'consumer_semantics': 'source-derived data placement/response mask check, not LSU RTL execution',
    }
    (tmp_path / 'source-chain-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    assert cursor == flow_count
    assert len(writebacks) == flow_count
    assert not any(item['exception'] for item in writebacks)
    assert destination == expected
    assert not duplicate_destinations
    assert sum(raw_memory.values()) == (104 if nf else 16)
    assert sum(count - 1 for count in raw_memory.values()) == (24 if nf else 0)
