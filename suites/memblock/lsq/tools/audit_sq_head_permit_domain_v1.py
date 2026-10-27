#!/usr/bin/env python3
"""Pinned-source triage of the required SQ head-precommit/flushSelf failure.

This does not turn a source-level IRQ exclusion into a general reachability
proof, and it never changes a native coverage point or a failed test outcome.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import hashlib
import json
from pathlib import Path
import re
import subprocess

from audit_evidence_io import write_report
from audit_gap_closure_v1 import native
from audit_coverage_points_v1 import records, sha256_file
from audit_vsq_cancel_capacity_v1 import FULL, failure_witness
from audit_vsq_recovery_boundaries_v1 import SOURCES

ROOT = Path(__file__).resolve().parents[1]
REPO = ucv_paths.source_path_for(ROOT)
COMMIT = "893e1580b705d81f113c30c7a05734e09a08050e"
PREFIX = "src/main/scala/xiangshan/"


def source(path):
    name = PREFIX + path
    raw = subprocess.check_output(["git", "show", f"{COMMIT}:{name}"], cwd=REPO)
    assert (REPO / name).read_bytes() == raw, ("working source differs from pinned git object", name)
    return raw.decode(), dict(repository="XiangShan", commit=COMMIT, path=name,
                              SHA256=hashlib.sha256(raw).hexdigest(), working_bytes_equal_git_object=True)


def evidence(text, identity, start, end, required):
    rows = text.splitlines()
    snippet = "\n".join(rows[start - 1:end]) + "\n"
    assert all(token in snippet for token in required), (identity["path"], start, end)
    return dict(**identity, start_line=start, end_line=end,
                range_SHA256=hashlib.sha256(snippet.encode()).hexdigest(), checked_expressions=required)


def interrupt_exclusion():
    # The premise is a valid store member of this entry. Store commitType=11
    # makes allowInterrupts=false, hence that member's unsafe bit must be set.
    # All other membership/unsafe bits are arbitrary. This is NOT a model of
    # exceptions, debug, replay or the complete backend redirect network.
    count, digest = 0, hashlib.sha256()
    for lane in range(8):
        for mask in range(256):
            if not mask >> lane & 1:
                continue
            for unsafe in range(256):
                if not unsafe >> lane & 1:
                    continue
                safe = not bool(mask & unsafe)
                assert not safe
                for intr, wait, flushed in ((i, w, f) for i in range(2) for w in range(2) for f in range(2)):
                    assert not (intr and not wait and safe and not flushed)
                digest.update(bytes((lane, mask, unsafe, int(safe))))
                count += 1
    assert count == 131072
    return dict(premise="valid store lane belongs to the pending ROB entry; actual decoded store commitType=11",
                arbitrary_other_entry_and_unsafe_mask_bits=True, exhaustive_mask_rows=count,
                interrupt_boolean_complements_per_row=8, truth_SHA256=digest.hexdigest(),
                result="entry.interruptSafe=0, so intrEnable=0 for this store-containing entry",
                not_proven="head self-flush through non-IRQ exceptions/debug/single-step/replay or other redirects")


def audit():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip() == COMMIT
    loaded = {}
    for path in ("package.scala", "backend/rename/CompressUnit.scala", "backend/rename/Rename.scala",
                 "backend/Bundles.scala", "backend/dispatch/Dispatch.scala", "backend/rob/RobBundles.scala",
                 "backend/rob/Rob.scala", "backend/CtrlBlock.scala", "mem/lsqueue/VirtualStoreQueue.scala",
                 "mem/lsqueue/NewStoreQueue.scala", "mem/pipeline/NewStoreUnit.scala",
                 "mem/lsqueue/LSQWrapper.scala", "mem/MemBlock.scala", "XSCore.scala"):
        loaded[path] = source(path)
    ranges = []

    def add(path, start, end, *expressions):
        ranges.append(evidence(*loaded[path], start, end, list(expressions)))

    add("package.scala", 145, 154, 'def STORE  = b"11"', 'def isLoadStore(commitType: UInt): Bool = commitType(1)')
    add("backend/rename/CompressUnit.scala", 94, 96, '!CommitType.isLoadStore(x.bits.commitType)')
    add("backend/rename/CompressUnit.scala", 233, 235, 'in.valid && !allow')
    add("backend/rename/CompressUnit.scala", 296, 307, 'entryInterruptSafeByToken(t) := !(entryMaskByToken(t) & unsafeMaskBits).orR')
    add("backend/rename/CompressUnit.scala", 334, 343, 'io.out.interruptSafe(i)        := entryInterruptSafeByToken(tokenId)')
    add("backend/rename/Rename.scala", 462, 469, 'uops(i).interruptSafe := interruptSafe(i)')
    add("backend/dispatch/Dispatch.scala", 888, 896, 'io.enqRob.req(i).bits.connectEnqRobUop(updatedUop(i))')
    add("backend/Bundles.scala", 347, 355, 'connectSamePort(this, source)', 'this.replayInst   := false.B')
    add("backend/rob/RobBundles.scala", 210, 227, 'robEntry.interruptSafe := robEnq.interruptSafe')
    add("backend/rob/RobBundles.scala", 264, 281, 'robCommitEntry.interruptSafe := robEntry.interruptSafe')
    add("backend/rob/Rob.scala", 764, 787, 'deqPtrEntry.interruptSafe && !deqHasFlushed', 'deqHasException', 'deqHasReplayInst')
    add("backend/rob/Rob.scala", 849, 859, 'io.flushOut.valid :=', 'intrEnable || deqHasException', 'isFlushPipe')
    add("backend/rob/Rob.scala", 898, 900, 'RedirectLevel.flush, RedirectLevel.flushAfter')
    add("backend/CtrlBlock.scala", 127, 146, 's0_robFlushRedirect = rob.io.flushOut', 's1_robFlushRedirect.valid := GatedValidRegNext', 's1_s3_redirect = Mux')
    add("backend/rob/Rob.scala", 1224, 1256, 'flushesHeadEntry', 'clearsHeadLatter', 'io.redirect.bits.flushItself()', 'io.lsq.pendingPtr :=')
    add("XSCore.scala", 216, 217, 'backend.io.mem.robLsqIO.pendingPtr')
    add("mem/MemBlock.scala", 1051, 1052, 'lsq.io.rob.pendingPtr          := io.ooo_to_mem.lsqio.pendingPtr')
    add("mem/lsqueue/LSQWrapper.scala", 211, 211, 'storeQueue.io.fromRob.robHeadPtr            := io.rob.pendingPtr')
    add("mem/lsqueue/VirtualStoreQueue.scala", 282, 297, 'preCommitMoveValid', '.robIdx.isSameSlot(robHeadPtr)', 'when(redirectReg.valid)')
    add("mem/lsqueue/VirtualStoreQueue.scala", 327, 331, '&& !redirectReg.valid', 'io.toPhysicalQueue.preCommitPtr.valid := preCommitValid')
    add("mem/lsqueue/NewStoreQueue.scala", 1634, 1636, 'virtualStoreQueuePreCommitPtr = GatedRegNext')
    add("mem/lsqueue/NewStoreQueue.scala", 1995, 2017, '!ctrlEntries(ptr).hasException', '!ctrlEntries(ptr).waitStoreS2', 'ctrlEntries(ptr).committed   := commitVec(i) || ctrlEntries(ptr).committed')
    add("mem/lsqueue/NewStoreQueue.scala", 1233, 1249, 'toSbufferValid(i) :=', 'ctrlEntry.committed')
    add("mem/lsqueue/NewStoreQueue.scala", 1289, 1294, 'sink               <> source', 'io.writeToSbuffer    <> dataQueue.io.toSbuffer')
    add("mem/lsqueue/NewStoreQueue.scala", 727, 735, 'val fromDeqModule', 'val toSbuffer', 'val deqPtrMove')
    add("mem/lsqueue/NewStoreQueue.scala", 786, 798, 'when(enqSet)', 'allocated(i) := true.B', '}.elsewhen(deqCancel)', 'allocated(i) := false.B')
    add("mem/lsqueue/NewStoreQueue.scala", 824, 837, 'io.toSbuffer.req(i).valid := allocated(deqPtrVec(i).value)', '&& io.toSbuffer.req(i).fire')
    add("mem/pipeline/NewStoreUnit.scala", 364, 366, 'isDebugMode', 'isBreakPoint')
    add("mem/pipeline/NewStoreUnit.scala", 476, 481, 'hasException || isDebugMode || isBreakPoint')
    add("mem/pipeline/NewStoreUnit.scala", 630, 667, 'val hasException = in.hasException.get || af || am', 'io.toSqAddrRe.hasException := fire && hasException')
    fifo = ROOT / 'rtl/store_queue/EnterSbufferQueue.sv'
    raw = fifo.read_text()
    expected_sha = json.loads((fifo.parent / 'source.json').read_text())['files'][fifo.name]
    assert sha256_file(fifo) == expected_sha == '35e3124ddb6624ff53c510e69e3c95f0bbdfd1f076dac42a292555297925e2ca'
    header = raw[raw.index('module EnterSbufferQueue('):raw.index(');', raw.index('module EnterSbufferQueue(')) + 2]
    assert not re.search(r'flush|redirect|robIdx|sqIdx', header, re.I)
    assert 'io_toSbuffer_req_0_ready' in header and 'io_fromDeqModule_0_valid' in header
    counts = []
    for dut, path in SOURCES.items():
        meta, dat = native(FULL, dut)
        assert sha256_file(dat) == meta['artifact']['sha256']
        points = [p for p in records(dat) if p['t'] == 'toggle' and p['f'] == str(ROOT / path)
                  and (p['o'].startswith('cancelCount[') or p['o'].startswith('retireReqNumReg[')) and not p['hit']]
        counts.append(dict(dut=dut, source=path, build_id=meta['artifact']['build']['build_id'],
                           dat_SHA256=sha256_file(dat), missing=[dict(line=int(p['l']), point=p['o'], hierarchy=p['h']) for p in points]))
    assert [len(row['missing']) for row in counts] == [4, 5, 5]
    report = dict(format='lsq-sq-head-permit-domain-audit-v1', run=FULL, commit=COMMIT,
        pinned_source_ranges=ranges, interrupt_only_exclusion=interrupt_exclusion(),
        exported_fifo=dict(source=str(fifo.relative_to(ROOT)), SHA256=expected_sha,
                           header_SHA256=hashlib.sha256(header.encode()).hexdigest(),
                           no_redirect_or_flush_or_uop_identity_input=True,
                           scope='Only requests already accepted into this FIFO; not a proof that a particular failed owner entered it at any specific tick.'),
        retained_failure=failure_witness(FULL), latest_count_domains=counts,
        findings=[
            'The pinned CompressUnit blocks IRQ on an entry containing a valid store; this is executable masking logic, not the commented-out historical allow_interrupts block in Rob.scala.',
            'Rob.flushOut has non-IRQ exception/replay paths and explicit head/former/latter flushSelf handling. IRQ exclusion alone cannot prove all head self-flush histories impossible.',
            'VSQ head equality issues precommit; a later redirect only suppresses current validity. PSQ committed state and a request already in EnterSbufferQueue are separate persistent domains.',
            'The exported EnterSbufferQueue has no redirect input; a queued request is not canceled by a later redirect. This is consistent with the observed old bytes but does not retrospectively reconstruct unretained cycle data.',
            'Using the exact per-build source mapping (leaf VirtualStoreQueueDut.v, parent VirtualStoreQueue.sv), VSQ still lacks retire bit6 both directions; SQ lacks bit4 falling; Wrapper lacks bit6 falling. Startup high-bit gaps remain separate.'],
        open_obligations=[
            'Prove or dynamically exhibit a complete upstream producer history for the required old-UID self-flush, including scalar/vector/compressed slots, pending pointer delay and non-IRQ flush origins.',
            'Keep the original SQ test required/failed; an unlicensed positive control and conditional IRQ proof do not waive it.',
            'Exercise legal parent multi-flow retirement and later small-batch known writes to target still-missing falling counter bits without using startup randomness.'],
        verification=dict(fixed_open_source_git_objects_and_working_bytes_equal=True, source_ranges_checked=True,
                          irq_exclusion_only_exhaustive=True, native_fifo_source_and_no_flush_port_checked=True,
                          original_failed_artifacts_retained=True, current_count_cones_read_from_actual_latest_dat=True),
        native_dynamic_coverage_gain=0, full_upstream_legality_proven=False, failure_waived=False,
        limits='Source triage only. No DUT executed, no raw trace reconstructed, no target RTL/Chisel modified, no native point or denominator removed, and no global failure classification changed.')
    output = ROOT / 'results' / FULL / 'sq-head-permit-domain-audit-v1.json'
    write_report(output, report)
    print(json.dumps({k: report[k] for k in ('run', 'interrupt_only_exclusion', 'latest_count_domains', 'verification', 'native_dynamic_coverage_gain', 'full_upstream_legality_proven', 'failure_waived')}, indent=2))
    return report


if __name__ == '__main__':
    audit()
