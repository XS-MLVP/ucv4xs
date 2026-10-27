import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Derive refill beat size from fixed parameters, not cache block size."""
import hashlib
import json
from pathlib import Path
import re

from audit_evidence_io import write_report
from audit_coverage_points_v1 import sha256_file
from audit_sq_head_permit_domain_v1 import source, evidence

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/replay-cause-lifetimes-contributor-regression-02/refill-width-source-correction-v2.json'
OLD_REPORTS = [
    'results/lrq-normal-metadata-after-02/normal-replay-metadata-evidence-v1.json',
    'results/lq-normal-metadata-after-02/normal-replay-metadata-evidence-v1.json',
    'results/lsq-normal-metadata-after-02/normal-replay-metadata-evidence-v1.json',
    'results/normal-replay-metadata-contributor-regression-01/normal-replay-metadata-contributor-evidence-v1.json',
    'results/lq-RAW-owners-after-02/load-RAW-owners-evidence-v1.json',
    'results/lsq-RAW-owners-after-02/load-RAW-owners-evidence-v1.json',
    'results/load-raw-owners-contributor-regression-02/load-RAW-owners-contributor-evidence-v1.json',
    'results/lq-response-payload-after-01/load-response-payload-evidence-v1.json',
    'results/lsq-response-payload-after-01/load-response-payload-evidence-v1.json',
    'results/load-response-contributor-regression-02/load-response-payload-contributor-evidence-v1.json',
    'results/lrq-cause-lifetimes-after-02/Replay-cause-lifetime-evidence-v1.json',
    'results/lq-cause-lifetimes-after-02/Replay-cause-lifetime-evidence-v1.json',
    'results/lsq-cause-lifetimes-after-02/Replay-cause-lifetime-evidence-v1.json',
]


def source_chain():
    chain = []
    for path, start, end, expressions in (
        ('Parameters.scala', 891, 892, ['def l1BusDataWidth = 256']),
        ('cache/L1Cache.scala', 41, 50, ['def blockBytes = cacheParams.blockBytes', 'def refillBytes = l1BusDataWidth / 8', 'def refillOffBits = log2Up(l1BusDataWidth / 8)']),
        ('cache/dcache/DCacheWrapper.scala', 49, 54, ['blockBytes: Int = 64']),
        ('mem/pipeline/NewLoadUnit.scala', 1602, 1618, ['lqWrite.rep_info.last_beat := paddr(log2Up(refillBytes))']),
    ):
        chain.append(evidence(*source(path), start, end, expressions))
    repository = ucv_paths.source_path_for(ROOT)
    definitions = []
    for path in (repository / 'src/main/scala').rglob('*.scala'):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'\b(?:def|val|var)\s+(?:l1BusDataWidth|refillBytes)\s*(?::[^=]+)?=', line):
                definitions.append((str(path.relative_to(repository)), number, line.strip()))
    assert len(definitions) == 2
    assert {row[2] for row in definitions} == {'def l1BusDataWidth = 256', 'def refillBytes = l1BusDataWidth / 8'}
    bits = int(re.search(r'def l1BusDataWidth = (\d+)', (repository / 'src/main/scala/xiangshan/Parameters.scala').read_text())[1])
    refill_bytes = bits // 8
    assert bits == 256 and refill_bytes == 32 and refill_bytes & (refill_bytes - 1) == 0
    return dict(fixed_ranges=chain, all_main_Scala_definitions=[list(row) for row in sorted(definitions)],
        l1_bus_data_bits=bits, refill_beat_bytes=refill_bytes, address_bit=refill_bytes.bit_length() - 1,
        DCache_block_bytes=64, block_and_beat_are_different=True)


def audit():
    chain = source_chain()
    assert chain['address_bit'] == 5
    if OUT.exists():
        report = json.loads(OUT.read_text())
        assert report['parameter_chain'] == chain
        return report
    producers = []
    for name in ('lsqverify/normal_replay_metadata.py', 'lsqverify/load_raw_owners.py',
        'lsqverify/load_response_payload.py', 'lsqverify/replay_cause_lifetimes.py'):
        p = ROOT / name
        lines = [dict(line=i, expression=line.strip()) for i, line in enumerate(p.read_text().splitlines(), 1)
            if 'last_beat' in line and re.search(r'&\s*64\b', line)]
        assert lines, name
        producers.append(dict(path=name, SHA256=sha256_file(p), incorrect_bit6_expressions=lines))
    old_reports = OLD_REPORTS + ['results/replay-cause-lifetimes-contributor-regression-02/Replay-cause-lifetime-contributor-evidence-v1.json']
    available = [name for name in old_reports if (ROOT / name).is_file()]
    # The source issue exists before a full02derived report is available; its
    # raw manifest/JUnit remains real and the subsequent report must carry scope.
    report = dict(format='lsq-refill-width-source-correction-v2', parameter_chain=chain,
        domain='UNIT_INTERFACE_PA_BIT6_NOT_FIXED32B_REFILL_LASTBEAT', old_bit5_vs6_assumption_wrong=True,
        required_lastBeat='bool(current_Load.PA &32)', incorrect_formula='bool(PA &64) or inherited bit6=0',
        cause02_owners_with_bit5_ne_bit6_per_layer=60, cause_owners_per_layer=120,
        old_source_producers=producers,
        prior_report_SHA256s={name: sha256_file(ROOT / name) for name in available},
        previous_PA6_correction_report='results/replay-cause-lifetimes-contributor-regression-01/PA-lastBeat-source-correction-v1.json',
        original01post_audit_failure='results/lsq-progress-regression-15/Replay-cause-post-audit-01.log',
        all_original_raw_DUT_results_and196failure_details_retained=True,
        old_normal_RAW_response_source_correct_lastBeat_admission_withdrawn=True,
        current_cause02_source_correct_lastBeat_admission_withdrawn=True,
        verification=dict(fixed_git_source_bytes_checked=True, full_parameter_to_lastBeat_chain_checked=True,
            all_main_Scala_refill_width_definitions_checked=True, block64_not_confused_with_beat32=True),
        limits='This source correction withdraws fixed-upstream lastBeat legality, not the real LSQ-interface DUT checks or coverage. Do not rewrite old raw dat/JUnit or claim earlier modelPASS proves source legality. Frozen older helpers are unchanged; their admission needs separate corrected-case evidence. Current new cause helper requires an independent formal03rerun with PA[5], not anotherPA[6] assertion.')
    write_report(OUT, report)
    return report


def annotate():
    report = audit()
    scope = dict(proven=False, domain=report['domain'], source_evidence=str(OUT.relative_to(ROOT)),
        source_evidence_SHA256=sha256_file(OUT), fixed_refill_bytes=32, required_PA_bit=5,
        actual_interface_checks_and_coverage_retained=True, raw_results_and_denominators_unchanged=True,
        reason='PA[6]was inferred from64Bcache block, but fixed256bitL1bus implies32Brefill and source lastBeat=PA[5]. Fixed-upstream legality is unproven for these input histories.')
    for name, digest in report['prior_report_SHA256s'].items():
        p = ROOT / name
        old = p.read_bytes()
        if sha256_file(p) != digest:
            archive = p.parent / 'audit-history' / f'{p.stem}-{digest}.json'
            assert sha256_file(archive) == digest
        item = json.loads(old)
        item['fixed_refill_width_source_admission'] = scope
        write_report(p, item)
    return scope


if __name__ == '__main__':
    r = audit(); print(json.dumps(r, indent=2, ensure_ascii=False))
