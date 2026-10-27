#!/usr/bin/env python3
"""Conditional local retirement lemma; not a whole-cone reachability waiver."""
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_evidence_io import write_report
from audit_sq_head_permit_domain_v1 import source, evidence
from audit_vsq_recovery_boundaries_v1 import SOURCES, source_proof


def local_induction():
    """Enumerate all local legal prefix orders, including a leading cleared row.

    Assumptions are stated, not inferred from a passing reference model:
    allocated entries form [head + previousRetireCount, tail), ROB-retired and
    physically-consumed eligibility are prefixes of that interval, enqueues
    never overwrite a live/previously-cleared head, redirects only cancel a
    suffix that does not include an architecturally retired Store.
    """
    digest = sha256()
    checked = 0
    cases = {str(k): 0 for k in range(9)}
    for pending in range(9):
        # Beyond offset15 no first/next head predicate can distinguish the
        # rest of a128-entry suffix. This is an explicit local abstraction.
        for count in range(17 - pending):
            allocated = set(range(pending, pending + count))
            for retired, consumed in product(range(count + 1), repeat=2):
                rob_prefix = set(range(pending, pending + retired))
                physical_prefix = set(range(pending, pending + consumed))
                carry = []
                for offset in range(8):
                    base = offset in allocated and offset in rob_prefix
                    release = offset < 2 and offset in allocated and offset in physical_prefix
                    carry.append((base and (offset == 0 or carry[offset - 1])) or release)
                retiring = {offset for offset, yes in enumerate(carry) if yes}
                moved = len(retiring)
                next_allocated = allocated - retiring
                new_head = pending
                next_live = sorted(offset - new_head for offset in next_allocated)
                assert next_live == list(range(moved, max(next_live, default=moved - 1) + 1)), (
                    'conditional contiguous-prefix invariant', pending, count, retired, consumed, carry, next_live)
                head_retired = 0 in allocated and 0 in rob_prefix
                # Exact idle->release entry: pending must be0 when current
                # head is allocated; clear head now, advance head by0.
                if head_retired:
                    assert pending == 0 and carry[0] and 0 not in next_allocated
                row = [pending, count, retired, consumed, carry, next_live, head_retired]
                digest.update(json.dumps(row).encode() + b'\n')
                checked += 1
                cases[str(pending)] += 1
    return dict(exhaustive_local_rows=checked, rows_by_pending_retire_count=cases,
        local_table_SHA256=digest.hexdigest(), local_lookahead=16, retire_width=8, physical_release_width=2,
        lemma='Under the explicit contiguous-prefix/monotonic-eligibility assumptions, headIsRetired implies previousRetireCount=0; idle->release clears the same head and does not advance it, so the first release cycle has headIsRetired=false.',
        source_mapping_complete=False, whole128entry_cone_proven=False,
        open_induction_obligations=[
            'Map allocated prefix/hole shape to all128 exact RTL ctrlEntries writes, enq priority, deq vector and delayed retire registers, including wrap/reuse.',
            'Prove ROB isBeforeSlot order and former/isFormer projection for every legal architectural producer; no raw numeric pointer shortcut.',
            'Prove physical-end eligibility is monotonic over the live interval under the actual SQ ring widths, capacities and legal0-flow/vector snapshots.',
            'Prove dispatch cannot overwrite the cleared head before its delayed retire is applied, including full/rotate boundaries.',
            'Prove all redirect/flushSelf, cancellation, reset and overlapping consumption cases preserve the invariant without assuming the desired conclusion.',
        ])


def audit():
    ranges = []
    for start, end, checks in (
        (161, 184, ['val enqSet', 'ctrlEntries(i).allocated := true.B', 'ctrlEntries(i).allocated := false.B', 'retireCarryVec(j)']),
        (236, 270, ['val headIsRetired', 'when(io.redirect.valid && headIsRetired)', 'when(!headIsRetired)', 'retireCarryVec(i) := retireBaseVec(i) || releaseHit', 'retireVec(i) := RegNext(retireCarryVec(i), false.B)']),
        (273, 280, ['val retireValid', 'deqPtrVec := deqPtrVecNext']),
        (380, 387, ['preCommitRelease.zipWithIndex', 'io.fromPhysicalQueue.deqPtr >= getEntryEndSqIdx(ptr)']),
    ):
        ranges.append(evidence(*source('mem/lsqueue/VirtualStoreQueue.scala'), start, end, checks))
    proof = local_induction()
    report = dict(format='lsq-vsq-release-wait-conditional-local-lemma-v1',
        exact_state_control=[dict(dut=dut, **source_proof(dut)) for dut in SOURCES],
        fixed_Chisel_ranges=ranges, conditional_local_induction=proof,
        release_wait_classification='existing_feature_missing_case', release_wait_waived=False,
        whole_cone_unreachability_proven=False, native_DUT_runs=0, native_dynamic_coverage_gain=0,
        denominators_changed=False, historical_state3_boundary_reopened=False,
        practical_selection='Do not repeat long retired-prefix cases merely to expect release self-wait: the simple no-alias prefix trajectory exits release immediately. Next work must prove the outstanding cone obligations or construct an explicit legal invariant-breaking witness before a new DUT test.',
        limits='This conditional16-entry local abstraction is not a proof for the actual128-entry VSQ, not a replacement for native DUT tests, and not permission to waive the three open release-wait points. All original classifications, point denominators and failures stay unchanged.')
    out = ROOT / 'results/normal-replay-original-contributors-01/next-vsq-release-wait-local-lemma-v1.json'
    write_report(out, report)
    return report


if __name__ == '__main__':
    item = audit()
    print(json.dumps({k: v for k, v in item.items() if k not in ('exact_state_control', 'fixed_Chisel_ranges')}, indent=2, ensure_ascii=False))
