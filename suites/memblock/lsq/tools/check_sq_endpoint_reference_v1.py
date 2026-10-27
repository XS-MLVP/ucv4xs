import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Static anchored-endpoint scope/AST proof, not native functionality."""
import ast
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import sys
import types

from audit_sq_initial import ROOT, sha

sys.path.insert(0,str(ROOT))
from lsqverify.forward.types import Inputs, Query
from lsqverify.raw.types import SqPtr


def load(path,name):
    module=types.ModuleType(name)
    module.__package__="lsqverify.forward"
    sys.modules[name]=module
    exec(compile(path.read_text(),str(path),"exec"),module.__dict__)
    return module


def main():
    old=ROOT/"results/lsq-sq-endpoint-01/verification-source/lsqverify/forward/model.py"
    new=ROOT/"lsqverify/forward/model.py"
    a,b=ast.parse(old.read_text()),ast.parse(new.read_text())
    comparisons=[n for n in ast.walk(a) if isinstance(n,ast.Compare) and isinstance(n.left,ast.Constant) and n.left.value==0
                 and len(n.comparators)==2 and isinstance(n.comparators[0],ast.Name) and n.comparators[0].id=="age"
                 and isinstance(n.comparators[1],ast.Constant) and n.comparators[1].value==128]
    assert len(comparisons)==1 and all(isinstance(op,typ) for op,typ in zip(comparisons[0].ops,(ast.LtE,ast.Lt)))
    comparisons[0].ops[1]=ast.LtE()
    assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False), "only anchored upper endpoint operator may change"
    before,after=load(old,"old_endpoint_forward"),load(new,"new_endpoint_forward")
    unchanged=added=rejected=generic_rejected=producer=0
    for head in range(256):
        def gt(left,right):
            return bool((left//128 ^ right//128) ^ ((left%128)>(right%128)))
        assert gt((head+128)%256,head) and not gt((head+129)%256,head)
        assert gt((head+128)%256,(head+64)%256)
        producer+=1
        for limit in (0,1,64):
            for age in (0,1,63,64,65,127,128,129,255):
                for lane in range(3):
                    q=Query(True,0x10000,SqPtr.encode(head+age),3)
                    inp=Inputs(dequeue=SqPtr.encode(head),upper=SqPtr.encode(head+limit))
                    old_model,new_model=before.ForwardModel(),after.ForwardModel()
                    if age<128:
                        assert asdict(old_model.new_job(q,lane,inp))==asdict(new_model.new_job(q,lane,inp))
                        unchanged+=1
                    else:
                        try:old_model.new_job(q,lane,inp)
                        except ValueError:pass
                        else:raise AssertionError("old endpoint rejection evidence lost")
                        if age==128:
                            answer=new_model.new_job(q,lane,inp)
                            assert len(answer.older)==limit and answer.outside
                            assert answer.older==tuple(((head+n)%64,SqPtr.encode(head+n)) for n in range(limit))
                            added+=1
                        else:
                            try:new_model.new_job(q,lane,inp)
                            except ValueError:rejected+=1
                            else:raise AssertionError("beyond128 was admitted")
        try:after.after(SqPtr.encode(head+128),SqPtr.encode(head))
        except ValueError:generic_rejected+=1
        else:raise AssertionError("generic half-ring rejection weakened")
    assert (unchanged,added,rejected,generic_rejected,producer)==(13824,2304,4608,256,256)
    repo=ucv_paths.source_path_for(ROOT)
    files=[repo/"src/main/scala/xiangshan/backend/dispatch/Dispatch.scala",
           repo/"utility/src/main/scala/utility/MultiFlagCircualQueuePtr.scala",
           repo/"src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala",
           repo/"src/main/scala/xiangshan/mem/lsqueue/VirtualStoreQueue.scala",
           repo/"src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala"]
    d,p,w,v,s=(file.read_text() for file in files)
    assert "allowDispatch(index) := (sqIdxEnd > sqDeqIdx) && allowDispatchPrevious" in d
    assert "fromRename(i).ready := allowDispatch(i) && !uopBlockByIQ(i) && thisCanActualOut(i) && !lsqRecoverStall" in d
    assert "val compare = this.operation_value > that.operation_value" in p and "differentFlag ^ compare" in p
    assert "loadQueue.io.enq.req(i).bits.sqIdx := storeQueue.io.enq.resp(i).physicalQueuePtr" in w
    assert "io.enq.resp(i).physicalQueuePtr := io.enq.req(i).bits.reqStartPtr.sqIdx" in v
    assert "val s0LoadOutOfRange   = s0Req.bits.sqIdx > io.ctrlInfo.physicalQueueUpper" in s
    out=ROOT/"results/static/sq-endpoint-reference-v1"
    out.mkdir(parents=True,exist_ok=True)
    for path,label in ((Path(__file__),Path(__file__).name),(old,"old-forward-model.py"),(new,"new-forward-model.py")):
        target=out/label
        if target.exists():assert sha(target)==sha(path)
        else:shutil.copy2(path,target)
    report=dict(status="STATIC_ONLY_ANCHORED128_ADMISSION_SINGLE_AST_OPERATOR_NO_COMPARISON_WEAKENING",
                old_model_sha256=sha(old),new_model_sha256=sha(new),auditor_sha256=sha(out/Path(__file__).name),
                counts=dict(unchanged_profiles=unchanged,new_exact128_profiles=added,rejected_beyond128=rejected,
                            unchanged_generic_half_ring_rejections=generic_rejected,full128_not129_producer_pointer_positions=producer),
                public_source_evidence=[dict(path=str(file.relative_to(repo)),sha256=sha(file)) for file in files],
                limits="Static source/operator/input admission only, not native response or whole Backend proof. Relative age anchored at dequeue accepts exactly128; no expected/select/safety/knownness/mask change. Native old6PASS/6ValueError minimal histories retained in lsq-sq-endpoint-01; corrected native end-to-end results need separate evidence. All original RTL FAILs remain ordinary.")
    target=out/"report.json"
    if target.exists():assert json.loads(target.read_text())==report
    else:target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":main()
