"""Machine-readable functional-point ledger for the LSQ suite.

This is the executable half of `docs/spec/design/contracts/instruction-source-mapping.md`
and `docs/spec/design/contracts/kind-outcome-matrix.md`.  The prose explains *why* a cell
has its status; this module makes the matrix enumerable so a self-test can
reject an iteration that adds a transaction kind or a response outcome without
declaring what covers it.

Status vocabulary (mirrors the docs):

- ``pass``          covered and passing in the authoritative run
- ``fail``          covered and truly failing (RTL defect or known model residue)
- ``gap``           mechanism exists, stimulus or observation missing
- ``na``            this DUT/interface has no such mechanism
- ``out-of-domain`` the mechanism lives in another block

Every ``pass``/``fail`` cell must carry at least one evidence locator;
every ``gap`` must carry ``missing`` and ``next``.
"""
from dataclasses import dataclass, field

PASS, FAIL, GAP, NA, OUT = "pass", "fail", "gap", "na", "out-of-domain"
STATUSES = (PASS, FAIL, GAP, NA, OUT)

#: Transaction kinds of the wrapper mixed-traffic actor.  They are transaction
#: types, not instruction families; see the instruction mapping contract.
KINDS = ("cached", "nc_load", "mmio_load", "io_load", "store", "nc_store", "io_store", "cbo")

#: Response-result domains.  "fault" means a bus or cache error response, not a
#: pre-existing instruction exception such as tlbMiss or hasException.
OUTCOMES = ("clean", "fault", "replay", "tag_error", "refill", "tlb_miss")

#: Instruction families that reach (or provably bypass) this suite.
INSTRUCTIONS = {
    "LD/LBU/LH/LHU/LW/LWU/LD/LQ": dict(reaches=True, entry="LoadQueue enq", domain="in-layer"),
    "SB/SH/SW/SD": dict(reaches=True, entry="StoreQueue enq", domain="in-layer"),
    "HLV/HLVU/HLVX/HSV": dict(reaches=True, entry="LoadQueue/StoreQueue enq", domain="in-layer (exception-carried isHyper only)"),
    "vector load (vle/vlse/vlxei/vleff)": dict(reaches=True, entry="LoadQueue enq, numLsElem", domain="in-layer; first vector route unproven"),
    "vector store (vse/vsse/vsxei/vsseg)": dict(reaches=True, entry="StoreQueue enq, numLsElem", domain="in-layer; segmented+AMO gap"),
    "CBO.clean/flush/inval/zero": dict(reaches=True, entry="StoreQueue enq, cboType", domain="in-layer"),
    "AMO (amo*)": dict(reaches=False, entry="-", domain="out-of-domain", reason="Dispatch.scala:741 filters isAMOVec; AtomicsUnit drives dcache.io.lsu.atomics"),
    "LR/SC": dict(reaches=False, entry="-", domain="out-of-domain", reason="same as AMO"),
    "Zicbop prefetch.i/r/w": dict(reaches=False, entry="-", domain="out-of-domain", reason="Dispatch.scala:675-676 excludes LSUOpType.isPrefetch; handled by NewLoadUnit software prefetch"),
    "fence / fence.i": dict(reaches=False, entry="-", domain="out-of-domain", reason="affects the suite only through sbuffer flush, MemBlock.scala:1178-1187"),
}

REQUIRED_INSTRUCTIONS = (
    "LD/LBU/LH/LHU/LW/LWU/LD/LQ", "SB/SH/SW/SD", "HLV/HLVU/HLVX/HSV",
    "vector load (vle/vlse/vlxei/vleff)", "vector store (vse/vsse/vsxei/vsseg)",
    "CBO.clean/flush/inval/zero", "AMO (amo*)", "LR/SC", "Zicbop prefetch.i/r/w", "fence / fence.i",
)


@dataclass(frozen=True)
class Cell:
    status: str
    evidence: tuple = ()
    note: str = ""
    missing: str = ""
    next: str = ""


def _p(*evidence, note=""):
    return Cell(PASS, evidence, note=note)


def _f(*evidence, note=""):
    return Cell(FAIL, evidence, note=note)


def _g(missing, next_, note=""):
    return Cell(GAP, (), note=note, missing=missing, next=next_)


def _na(reason):
    return Cell(NA, (), note=reason)


def _out(reason):
    return Cell(OUT, (), note=reason)


#: kind -> outcome -> Cell.  Populated completely below; :func:`validate`
#: rejects a missing kind or a missing outcome.
CELLS = {
    "cached": {
        "clean": _p("testbenches/load_queue/tests/test_initial.py", note="17 nodes"),
        "fault": _p("testbenches/lsq_wrapper/tests/test_ldu_s4_errors.py", note="78 nodes, tag_error/tl_d_corrupt"),
        "replay": _p("testbenches/replay/tests/test_timing.py", "testbenches/lsq_wrapper/tests/test_ldu_s4_precise.py", note="67+84 nodes"),
        "tag_error": _p("testbenches/lsq_wrapper/tests/test_ldu_s4_errors.py", note="AF patterns in the 78"),
        "refill": _p("testbenches/lsq_wrapper/tests/test_replay_population.py", note="20 nodes"),
        "tlb_miss": _p("testbenches/lsq_wrapper/tests/test_ldu_s4_plain.py", note="PF patterns + TlbHint"),
    },
    "nc_load": {
        "clean": _p("testbenches/lsq_wrapper/tests/test_bus.py", note="nc, fault=False"),
        "fault": _p("testbenches/lsq_wrapper/tests/test_bus.py", note="nc, fault=True"),
        "replay": _p("testbenches/lsq_wrapper/tests/test_bus.py", note="asserts replay_0_valid"),
        "tag_error": _na("UncacheWordResp carries no tag_error"),
        "refill": _na("uncached path bypasses the MSHR"),
        "tlb_miss": _g("NC load combined with a TLB miss hint has no dedicated case",
                       "add an nc_load case that also drives slow_tlb/fast_tlb"),
    },
    "mmio_load": {
        "clean": _p("testbenches/lsq_wrapper/tests/test_bus.py", "testbenches/deq/tests/test_uncache_and_queue.py"),
        "fault": _p("testbenches/lsq_wrapper/tests/test_bus.py", note="mmio, fault=True"),
        "replay": _p("testbenches/lsq_wrapper/tests/test_bus.py"),
        "tag_error": _na("UncacheWordResp carries no tag_error"),
        "refill": _na("uncached path bypasses the MSHR"),
        "tlb_miss": _g("MMIO load combined with a TLB miss hint has no dedicated case",
                       "extend the bus trace with a tlb hint"),
    },
    "io_load": {
        "clean": _p("testbenches/load_queue/tests/test_uncache.py", "testbenches/lsq_wrapper/tests/test_uncache_pressure.py"),
        "fault": _p("testbenches/lsq_wrapper/tests/test_uncache_recovery.py",
                    "testbenches/lsq_wrapper/tests/uncache_owners.py", note="error/nderr transfer"),
        "replay": _p("testbenches/lsq_wrapper/tests/test_uncache_recovery.py"),
        "tag_error": _na("device/IO response has no cache tag"),
        "refill": _na("device/IO path bypasses the MSHR"),
        "tlb_miss": _g("IO load combined with a TLB miss hint has no dedicated case",
                       "extend the uncache owner with a slow_tlb hint"),
    },
    "store": {
        "clean": _p("tests/store_queue", "tests/psq", note="bulk of the store domain"),
        "fault": _p("testbenches/store_queue/tests/test_recovery.py",
                    note="pre-existing hasException, NOT a response fault"),
        "replay": _na("Store has no replay path"),
        "tag_error": _na("normal committed Store takes no dcache response"),
        "refill": _na("normal committed Store takes no refill"),
        "tlb_miss": _p("testbenches/store_queue/tests/test_remaining.py", note="ready-holes + tlb retry"),
    },
    "nc_store": {
        "clean": _p("testbenches/lsq_wrapper/tests/test_bus.py", note="nc, completes on idResp"),
        "fault": _na("FSM waitReqAck -> idle; ncFinish sets handleFinish without a writeback stage "
                     "(NewStoreQueue.scala:1044-1049, :1706-1707)"),
        "replay": _na("Store has no replay path"),
        "tag_error": _na("uncached Store takes no dcache tag response"),
        "refill": _na("uncached Store takes no refill"),
        "tlb_miss": _p("testbenches/store_queue/tests/test_remaining.py", note="shared store address path"),
    },
    "io_store": {
        "clean": _p("testbenches/lsq_wrapper/tests/test_bus.py", note="io, writeback path"),
        "fault": _f("testbenches/lsq_wrapper/tests/test_uncache_store_fault.py",
                    note="nderr->exceptionVec_7 and error->exceptionVec_19 both read 0; "
                         "PhysicalStoreQueue exposes only resp_valid, no resp_bits"),
        "replay": _na("Store has no replay path"),
        "tag_error": _na("uncached Store takes no dcache tag response"),
        "refill": _na("uncached Store takes no refill"),
        "tlb_miss": _p("testbenches/store_queue/tests/test_remaining.py", note="shared store address path"),
    },
    "cbo": {
        "clean": _p("testbenches/lsq_wrapper/tests/test_serialized_cbo.py", "testbenches/lsq_wrapper/tests/test_normal_cbo_paths.py"),
        "fault": _f("testbenches/deq/tests/test_cbo_fault_consumption.py",
                    "testbenches/lsq_wrapper/tests/test_serialized_cbo.py",
                    note="cache errors lost at writeback / ordering"),
        "replay": _na("CBO has no replay path"),
        "tag_error": _na("CBO response fields are denied/corrupt only"),
        "refill": _na("CBO does not consume refills"),
        "tlb_miss": _g("CBO address translation miss has no dedicated case",
                       "drive a tlbMiss CMO address and check the FSM does not enter sendReq"),
    },
}

#: Cross-cutting gaps that are not a single kind x outcome cell.
CROSS_GAPS = {    "GAP-6704": dict(
        area="store x cross16B x head/tail window",
        missing="memory_owners.write() sends head and tail in one call; no head-accepted/tail-pending window",
        next="split write_head_only(), insert a lower-half-only Load query, assert forward-or-block, then send the tail",
        evidence="docs/spec/design/contracts/instruction-source-mapping.md",
    ),
    "GAP-6688": dict(
        area="replay x configuration domain",
        missing="DUT fixes ColdDownThreshold=12; no 0-threshold build",
        next="build a 0-configuration DUT; assert 0 is rejected and 1/12/15 remain legal",
        evidence="docs/spec/design/contracts/kind-outcome-matrix.md",
    ),
    "GAP-PSQ-CREDIT": dict(
        area="store/cbo x deq credit",
        missing="testbenches/deq/model.py does not consume DeqControl.memory_type; the Sbuffer-credit rule for "
                "cacheable deq-window entries is unmodelled",
        next="model credit demand as isCacheable && !isCbo && !vecInactive and re-verify separately",
        evidence="docs/spec/verification/evidence/reports/upstream-audit-20261103.md",
    ),
    "GAP-AMO-OBLIGATION": dict(
        area="AMO x sbuffer drain",
        missing="AMO bypasses the LSQ but requires stIsEmpty (MemBlock.scala:1181-1182, :1225)",
        next="belongs to the MemBlock combination domain; needs Sbuffer + AtomicsUnit joint DUT",
        evidence="docs/spec/design/contracts/instruction-source-mapping.md",
    ),
    "GAP-IO-STORE-TRAP": dict(
        area="io_store fault x trap flow",
        missing="the mixed actor asserts the writeback fault bits but has no modelled "
                "'external trap after LSQ completion' path for an uncached Store bus fault",
        next="model the post-writeback trap/redirect sequence for io_store faults, then let the "
             "actor drive the redirect instead of only recording bus_fault",
        evidence="testbenches/lsq_wrapper/tests/mixed_owners.py (s['bus_fault'])",
    ),
    "GAP-SEG-VSTORE": dict(
        area="vector store x AMO",
        missing="VSQ stimulus drives flows counts only; no multi-register segmented store followed by an AMO",
        next="build a real segmented-store flow split and a following AMO issue sequence",
        evidence="docs/spec/design/contracts/instruction-source-mapping.md",
    ),
}


#: Interaction windows: cross-module combinations where two Scala conditions can
#: interleave into a window that is not covered by a single kind x outcome cell.
#: Each entry follows docs/spec/design/contracts/interaction-semantics.md.
INTERACTION_WINDOWS = {
    "IWL-VSQ-RETIRE": dict(
        boundary="VirtualStoreQueue -> PhysicalStoreQueue",
        scala="VirtualStoreQueue.scala:323",
        window="multi-flow segmented store retires; retirePtr must equal getEntryEndSqIdx(deqPtrVec.head-1)",
        status=GAP,
        evidence="docs/spec/design/contracts/interaction-semantics.md",
        missing="VSQ stimulus drives flows counts only; no multi-register segmented store followed by another op",
        next="build a real segmented-store flow split and a following AMO issue sequence",
    ),
    "IWL-UQ-SECOND-PAGE": dict(
        boundary="PhysicalStoreQueue -> UnalignQueue -> ForwardModule",
        scala="NewStoreQueue.scala:1299 with :1632",
        window="first 16B fragment accepted by Sbuffer but the second fragment still queued: the older "
               "store's second-page bytes are in neither Sbuffer nor UnalignQueue",
        status=FAIL,
        evidence="testbenches/lsq_wrapper/tests/test_interaction_windows.py",
        note="probe: uq_held control blocks (3/3 PASS); uq_released accepts with no block and no "
             "forwarded bytes (3/3 FAIL); same root cause as upstream #6822",
    ),
    "IWL-NC-CROSS16B": dict(
        boundary="DeqModule -> Uncache",
        scala="NewStoreQueue.scala:1448 (assertion) with :1071-1080 (single 8-byte mask)",
        window="uncached Store whose vaddr would cross 16B",
        status=PASS,
        evidence="testbenches/lsq_wrapper/tests/test_interaction_windows.py",
        note="RETRACTED DEFECT CLAIM. A first probe drove a misaligned NC store with hasException=0 "
             "and reported the 4-of-8-byte mask as a defect. That stimulus is illegal: "
             "NewStoreUnit.scala:633 sets am = !align && isScalar && isNC, so hasException=1 and "
             "LSQ's uncacheCanHandle requires !hasException. The corrected probe shows the aligned NC "
             "store sends a full 8-byte mask and the misaligned one is suppressed entirely, i.e. LSQ "
             "behaves correctly. The :1448 XSError is a defensive assertion that upstream guarantees.",
    ),
    "IWL-CREDIT-TYPE": dict(
        boundary="DeqModule -> EnterSbufferQueue",
        scala="NewStoreQueue.scala:1323-1325",
        window="cacheable and uncacheable entries interleaved in the deq window; credit demand depends on type",
        status=GAP,
        evidence="docs/spec/design/contracts/kind-outcome-matrix.md",
        missing="testbenches/deq/model.py computes credit from commitment bits only, not from isCacheable && !isCbo && !vecInactive",
        next="model credit demand by entry type and re-verify the three post-edge nodes separately",
    ),
    "IWL-PRECOMMIT-RETIRE": dict(
        boundary="VirtualStoreQueue -> PhysicalStoreQueue",
        scala="VirtualStoreQueue.scala:327-329",
        window="pre-committed but not yet retired: preCommitPtr must stay within [deqPtr, enqPtr]",
        status=PASS,
        evidence="testbenches/store_queue/tests/test_remaining.py",
        note="bounds checked every cycle through the store actor's pointer assertions",
    ),
}


def validate():
    """Return a list of human-readable problems; empty means the ledger is sound."""
    problems = []
    for kind in KINDS:
        if kind not in CELLS:
            problems.append(f"missing kind row: {kind}")
            continue
        row = CELLS[kind]
        for outcome in OUTCOMES:
            if outcome not in row:
                problems.append(f"missing cell: {kind} x {outcome}")
    for kind in CELLS:
        if kind not in KINDS:
            problems.append(f"unknown kind row: {kind}")
        for outcome, cell in CELLS[kind].items():
            tag = f"{kind} x {outcome}"
            if outcome not in OUTCOMES:
                problems.append(f"unknown outcome column: {tag}")
            if cell.status not in STATUSES:
                problems.append(f"bad status {cell.status!r}: {tag}")
            if cell.status in (PASS, FAIL) and not cell.evidence:
                problems.append(f"{tag} claims {cell.status} without evidence")
            if cell.status == GAP and not (cell.missing and cell.next):
                problems.append(f"{tag} is a gap without missing/next")
            if cell.status == NA and not cell.note:
                problems.append(f"{tag} is na without a structural reason")
            if cell.status == OUT and not cell.note:
                problems.append(f"{tag} is out-of-domain without a target")
    for name, item in INSTRUCTIONS.items():
        if not all(item.get(key) for key in ("entry", "domain")):
            problems.append(f"instruction {name} lacks entry/domain")
        if item["reaches"] and not item["entry"]:
            problems.append(f"instruction {name} reaches the suite but has no entry")
        if not item["reaches"] and not item.get("reason"):
            problems.append(f"instruction {name} bypasses the suite without a source reason")
    for name in REQUIRED_INSTRUCTIONS:
        if name not in INSTRUCTIONS:
            problems.append(f"required instruction family missing: {name}")
    for wid, window in INTERACTION_WINDOWS.items():
        for key in ("boundary", "scala", "window", "status", "evidence"):
            if not window.get(key):
                problems.append(f"{wid} lacks {key}")
        if window["status"] not in STATUSES:
            problems.append(f"{wid} has bad status {window['status']!r}")
        if window["status"] in (PASS, FAIL) and not window.get("note"):
            problems.append(f"{wid} claims {window['status']} without a note")
        if window["status"] == GAP and not (window.get("missing") and window.get("next")):
            problems.append(f"{wid} is a gap without missing/next")
    for gid, gap in CROSS_GAPS.items():
        for key in ("area", "missing", "next", "evidence"):
            if not gap.get(key):
                problems.append(f"{gid} lacks {key}")
    return problems


def summary():
    counts = {status: 0 for status in STATUSES}
    for row in CELLS.values():
        for cell in row.values():
            counts[cell.status] += 1
    return dict(cells=sum(counts.values()), **counts)
