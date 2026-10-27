#!/usr/bin/env python3
"""LSQ-side128 reservation admission, not a complete backend reachability proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from audit_evidence_io import write_report
from audit_sq_head_permit_domain_v1 import COMMIT, REPO, evidence, source
from audit_vsq_recovery_boundaries_v1 import ROOT

UTILITY_COMMIT = "eb8e12b00a33e4716e7778175f6dd45b7a3a9ede"


def audit():
    ranges=[]
    def add(path,start,end,*checks):
        ranges.append(evidence(*source(path),start,end,list(checks)))
    add("Parameters.scala",110,115,"StoreQueuePhysicalSize: Int = 64","StoreQueueMultiple: Int = 2","RobSize: Int = 160")
    add("Parameters.scala",421,440,'"STA0"','"STA1"',"numEntries = 16, numEnq = 2")
    add("backend/rename/Rename.scala",387,395,"u.numLsElem := 1.U","port.bits.num := uops(i).numLsElem")
    add("backend/dispatch/Dispatch.scala",710,726,"allowDispatch(index) := (sqIdxEnd > sqDeqIdx) && allowDispatchPrevious")
    add("backend/dispatch/Dispatch.scala",729,746,"enqLsqIO.needAlloc(i) := 2.U","enqLsqIO.req(i).bits.uop.numLsElem := numLsElem(i)")
    add("mem/lsqueue/LSQWrapper.scala",412,445,"val storeQueueElem =","val sqAllocNumber =","resp.sqIdx := sqTailPtr + sqOffset + storeQueueElem(i)")
    add("mem/lsqueue/LSQWrapper.scala",483,505,"val sqCanAccept = sqTailPtr >= sqHeadPtr","val do_enq = enq.valid && !io.redirect.valid","!io.fromDispatch.recoverStall")
    add("mem/lsqueue/VirtualStoreQueue.scala",59,62,"val Size = PhysicalQueueSize * Multiple")
    add("mem/lsqueue/VirtualStoreQueue.scala",213,227,"allowEnqueue := enqPtrVec.head >= deqPtrVec.head","val cancelCount = PopCount(needCancelReg)")
    add("mem/lsqueue/NewStoreQueue.scala",34,44,"extends MultiFlagCircularQueuePtr","PhysicalSize","Multiple","withInPhysicalQueue(startPtr, this, PhysicalSize)")
    add("mem/lsqueue/NewStoreQueue.scala",1546,1549,"val virtualValidCount  = enqPtr.distanceBetween(deqPtrExt.head)","RegNext(virtualValidCount) <= StoreQueueSize.U")
    add("mem/lsqueue/NewStoreQueue.scala",2076,2076,"io.full := !allowEnqueue")
    add("mem/lsqueue/NewStoreQueue.scala",2149,2150,"io.sqFull          := physicalQueue.io.full")
    add("mem/pipeline/NewStoreUnit.scala",128,139,"sink.bits.illegalIssue := !sink.bits.uop.sqIdx.withInPhysicalQueue(io.sqDeqPtr)")
    add("backend/rob/RobBundles.scala",302,309,"val differentFlag = this.flag ^ that.flag","(differentFlag ^ compare)")
    add("backend/rob/RobBundles.scala",355,357,"redirect.valid && (flushItself || isAfterSlot(redirect.bits.robIdx))")
    link=subprocess.check_output(["git","ls-tree",COMMIT,"utility"],cwd=REPO,text=True).strip()
    assert link == f"160000 commit {UTILITY_COMMIT}\tutility"
    repo=REPO/"utility"
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()==UTILITY_COMMIT
    path="src/main/scala/utility/MultiFlagCircualQueuePtr.scala"
    raw=subprocess.check_output(["git","show",f"{UTILITY_COMMIT}:{path}"],cwd=repo)
    assert (repo/path).read_bytes()==raw
    identity=dict(repository="XiangShan/utility",commit=UTILITY_COMMIT,path=path,SHA256=hashlib.sha256(raw).hexdigest(),working_bytes_equal_git_object=True)
    text=raw.decode()
    ranges.append(evidence(text,identity,100,116,["differentFlag ^ compare","this.operation_value > that.operation_value","this.operation_value >= that.operation_value"]))
    ranges.append(evidence(text,identity,177,179,["val endPtr = startPtr + entrySize.U","thisPtr >= startPtr && thisPtr < endPtr"]))
    digest=hashlib.sha256();rows=0
    for base in range(256):
        for delta in range(256):
            end=(base+delta)%256
            after=bool((end//128)^(base//128)) ^ (end%128>base%128)
            assert after == (1<=delta<=128)
            # Before the next enqueue, >= accepts empty through127 occupied;
            # no extra enqueue is allowed from the known full128 state.
            not_before=bool((end//128)^(base//128)) ^ (end%128>=base%128)
            assert not_before == (delta<128)
            digest.update(bytes((base,delta,int(after),int(not_before))));rows+=1
    assert rows==65536
    physical=ROOT/"rtl/store_queue/PhysicalStoreQueue.sv"
    physical_sha=json.loads((physical.parent/"source.json").read_text())["files"][physical.name]
    assert hashlib.sha256(physical.read_bytes()).hexdigest()==physical_sha
    assert physical.read_text().splitlines()[16122].strip()=="assign io_full = allowEnqueue_REG > 8'h80;"
    report=dict(format="lsq-sq-scalar-reservation-domain-v1",commit=COMMIT,utility_gitlink=link,source_ranges=ranges,
        contract="docs/contracts/sq-scalar-reservation-pool.md",domain="UNIT_INTERFACE_LSQ_CAPACITY",
        scalar_count=1,LSQ_virtual_capacity=128,physical_issue_window=64,ROB_entries=160,
        public_sqFull=dict(source="rtl/store_queue/PhysicalStoreQueue.sv",source_SHA256=physical_sha,source_line=16123,
            exact_assignment="assign io_full = allowEnqueue_REG > 8'h80;",value_at_exact128=0,
            not_the_removed_VSQ_canAccept=True,probe01_wrong_virtual_full_precondition_retained=True),
        SQ_compare=dict(all_base_and_distance_rows=rows,truth_SHA256=digest.hexdigest(),
                        strict_after_legal_positive_distance=[1,128],not_before_distance=[0,127]),
        resource_boundary=dict(configured_STA_IQs=[16,16],total_STA_IQ_entries=32,
            proposed_old_executed=64,proposed_old_unexecuted=64,
            full_backend_resource_history_proven=False,
            reason="LSQ-side admission is not a full backend proof. The extra64unexecuted STA cannot simply be declared resident in a32-entry IQ. In-flight/replay/other configurations need separate evidence; neither complete upstream reachability nor global unreachability is claimed."),
        verification=dict(pinned_main_source_and_utility_gitlink_bytes_checked=True,LSQ_scalar_admission_cone_checked=True,
            exhaustive_SQ_all_flags_and_boundaries_checked=True,physical_window_source_checked=True,
            full_backend_IQ_limitation_explicit=True),
        dynamic_native_coverage_gain=0,normal_full_core_producer_proven=False,
        limits="Static module-interface legality only. Do not classify128scalar reservation as normal full-core reachable, close the original head-flush failure, remove a point/denominator, or substitute this for real remaining Load/bus/exception work.")
    write_report(ROOT/"results/vsq-retire-known-width-contributor-regression-01/sq-scalar-reservation-domain-v1.json",report)
    print(json.dumps({k:report[k] for k in ("domain","SQ_compare","resource_boundary","verification","normal_full_core_producer_proven")},indent=2))
    return report


if __name__ == "__main__":
    audit()
