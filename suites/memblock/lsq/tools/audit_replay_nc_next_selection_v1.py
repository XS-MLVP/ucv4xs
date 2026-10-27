#!/usr/bin/env python3
"""Source-backed next-case selection only; not a new NC stimulus contract."""
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_coverage_points_v1 import records, sha256_file
from audit_evidence_io import write_report
from audit_gap_closure_v1 import native, digest_keys, point_key
from audit_sq_head_permit_domain_v1 import source, evidence


def audit(run='replay-cause-lifetimes-contributor-regression-03'):
    checks = []
    for path, start, end, expressions in (
        ('mem/MemBlock.scala', 511, 511, ['val newLoadUnits = Seq.tabulate(LduCnt)(i => Module(new NewLoadUnit(ldaParams(i))))']),
        ('mem/MemBlock.scala', 958, 958, ['lsq.io.ldu.ldin(i) <> newLoadUnits(i).io.lqWrite']),
        ('mem/lsqueue/LoadQueueReplay.scala', 868, 877, ['isNC(enqIndex)      := enq.bits.nc && enq.bits.rep_info.cause(LoadReplayCauses.C_UNCACHE)']),
        ('mem/lsqueue/LoadQueueReplay.scala', 773, 778, ['replay_req(i).bits.uncacheReplay.get := s1_replayCauses(LoadReplayCauses.C_UNCACHE)', 'replay_req(i).bits.ncReplay.get := s1_replayCauses(LoadReplayCauses.C_UNCACHE) && s1_nc']),
        ('mem/lsqueue/LoadQueueUncache.scala', 193, 197, ['when (io.uncache.resp.fire)', 'uncacheData := io.uncache.resp.bits.data']),
        ('mem/lsqueue/LoadQueueUncache.scala', 432, 440, ['e.io.slaveId.valid && e.io.slaveId.bits === io.uncache.resp.bits.id', 'e.io.uncache.resp <> io.uncache.resp']),
    ):
        checks.append(evidence(*source(path), start, end, expressions))
    rows = []
    for dut in ('load_queue_replay', 'load_queue', 'lsq_wrapper'):
        meta, dat = native(run, dut)
        path = ROOT / 'dut/load_queue_replay/LoadQueueReplayDut.v' if dut == 'load_queue_replay' else ROOT / 'rtl' / dut / 'LoadQueueReplay.sv'
        points = [p for p in records(dat) if p['f'] == str(path) and p['t'] == 'toggle']
        nc = [p for p in points if re.fullmatch(r'isNC_\d+:(0->1|1->0)', p['o'])]
        cause0 = [p for p in points if re.fullmatch(r'cause_\d+\[0\]:(0->1|1->0)', p['o'])]
        assert len(nc) == len(cause0) == 240
        rows.append(dict(dut=dut, baseline_run=run, native_build_id=meta['artifact']['build']['build_id'],
            source=str(path.relative_to(ROOT)), source_SHA256=sha256_file(path),
            families={name: dict(total=240, missing=sum(not p['hit'] for p in selected),
                missing_by_direction=dict(Counter(p['o'].split(':')[-1] for p in selected if not p['hit'])),
                missing_point_set_SHA256=digest_keys({point_key(p) for p in selected if not p['hit']}))
                for name, selected in (('stored_NC_type', nc), ('stored_UNCACHE_cause', cause0))}))
    result = dict(format='lsq-Replay-NC-next-selection-v1', baseline_run=run, source_ranges=checks, rows=rows,
        native_dynamic_coverage_gain=0, next_contract_created=False, next_tests_created=False,
        decision='Type bit requires nc AND C_UNCACHE on an actual admitted owner. Setting nc on normal Cache/TLB replay writes0 and cannot supply the missing positive case. Plan known-write NC/MMIO/cacheable lifetimes at each public slot, with real parent bus response,bypass,source-correct S3 and final LQ release.',
        preserved_failures=['SID reused after response while old data unconsumed','strict/disabled','mixed fairness','head permit'],
        admission_obligations=['Every NC/MMIO parent owner must get an actually accepted bus request and ack-bound SID before its matching response.',
            'Replay ready/grant and original bank LDU S0/bypass must coincide; do not blindly enlarge an older sequential helper or infer upstream legality from a passing LSQ-only checker.',
            'Every full-slot known-write cohort must execute in one test without reset; do not OR a NC test and a normal test to claim a falling transition.',
            'The known passing SID-after-consumption path does not replace the existing mandatory unconsumed-data reuse failures.',
            'Keep64B/ending-halfword FTQ and bounded pendingNext/pending; no arbitrary high opcode/VA or120unexecuted IQ fiction.'],
        limits='Selection and fixed-source checks only. Not native coverage gain, not a new test or contract, not proof of a native Cache/Uncache/Frontend/ROB implementation. Current original inventory, denominators and all historical failures stay unchanged.')
    write_report(ROOT / 'results' / run / 'next-NC-type-lifetimes-selection-v1.json', result)
    return result


if __name__ == '__main__':
    r = audit(); print(json.dumps({k: v for k, v in r.items() if k != 'source_ranges'}, indent=2, ensure_ascii=False))
