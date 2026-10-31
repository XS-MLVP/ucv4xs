import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Only SMF exclusive/dequeue comparison may admit the full128 endpoint."""
import ast
import json
from pathlib import Path
import shutil
import sys
import types

from audit_sq_initial import ROOT, sha

sys.path.insert(0,str(ROOT))
from suites.memblock.lsq.raw.types import SqPtr


def load(file,name):
    module=types.ModuleType(name)
    module.__package__="suites.memblock.lsq.replay"
    sys.modules[name]=module
    exec(compile(file.read_text(),str(file),"exec"),module.__dict__)
    return module


def main():
    old=ROOT/'results/lsq-sq-endpoint-02/verification-source/lsqverify/replay/model.py'
    new=ROOT/"replay/model.py"
    a,b=ast.parse(old.read_text()),ast.parse(new.read_text())
    helper=[n for n in b.body if isinstance(n,ast.FunctionDef) and n.name=="sq_exclusive_after"]
    assert len(helper)==1
    expected=ast.parse("def sq_exclusive_after(left, right):\n    return (sq_serial(left) - sq_serial(right)) % 256 == 128 or sq_after(left, right)\n").body[0]
    assert ast.dump(helper[0])==ast.dump(expected)
    b.body.remove(helper[0])
    branches=[n for n in ast.walk(b) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and
              ast.dump(n.test)==ast.dump(ast.parse("cause == Cause.STORE_MULTI_MATCH",mode="eval").body)]
    assert len(branches)==1 and len(branches[0].body)==1
    calls=[n for n in ast.walk(branches[0]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="sq_exclusive_after"]
    assert len(calls)==1
    assert [ast.dump(n) for n in calls[0].args]==[ast.dump(ast.parse(s,mode="eval").body) for s in("req.uop.sq","inp.dequeue")]
    calls[0].func.id="sq_after"
    assert ast.dump(a)==ast.dump(b), "only SMF branch and explicit helper may change; RAW/address/data/knownness checks stay intact"
    before,after=load(old,"old_smf_replay"),load(new,"new_smf_replay")
    equal=new_full=generic_refused=0
    for head in range(256):
        for delta in range(256):
            left,right=SqPtr.encode(head+delta),SqPtr.encode(head)
            actual_source_not_after=bool((int(left.first)^int(right.first)) ^ ((64*int(left.second)+left.value)<=(64*int(right.second)+right.value)))
            value=after.sq_exclusive_after(left,right)
            assert value is not actual_source_not_after
            if delta==128:
                assert value
                new_full+=1
                for module in(before,after):
                    try:module.sq_after(left,right)
                    except ValueError:generic_refused+=1
                    else:raise AssertionError("generic half-ring guard changed")
            else:
                assert value==before.sq_after(left,right)
                equal+=1
    assert (equal,new_full,generic_refused)==(65280,256,512)
    source=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala'
    text=source.read_text()
    assert "blockSqIdx(i).isNotAfter(io.sqDeqPtr)" in text
    assert "Mux(isFF, replayInfo.data_inv_sq_idx, enq.bits.uop.sqIdx)" in text
    out=ROOT/"results/static/sq-smf-reference-v1"
    out.mkdir(parents=True,exist_ok=True)
    for file,name in((Path(__file__),Path(__file__).name),(old,"old-replay-model.py"),(new,"new-replay-model.py")):
        target=out/name
        if target.exists():assert sha(file)==sha(target)
        else:shutil.copy2(file,target)
    report=dict(status="STATIC_ONLY_SMF_EXCLUSIVE128_STAYS_BLOCKED_GENERIC_GUARD_AND_OTHER_SEMANTIC_AST_UNCHANGED",
                old_model_sha256=sha(old),new_model_sha256=sha(new),auditor_sha256=sha(out/Path(__file__).name),source_sha256=sha(source),
                counts=dict(unchanged_non_half_profiles=equal,full128_still_waiting_profiles=new_full,old_and_new_generic_rejections=generic_refused),
                limits="Public Replay.scala853-858/520-523 binds SMF blockSqIdx to original Load exclusive SQ and waits for real dequeue. Only SMF explicit boundary guard changes; RAW capacity and ordinary Store address/data generic guards are intentionally NOT widened without separate cases. No scheduling/expected/payload/free/reset/knownness/mask change. Static source proof not native function; old3ValueError and actual corrected native SMF cases require their own evidence. No RTL edit or whole Backend/ISA acceptance.")
    file=out/"report.json"
    if file.exists():assert json.loads(file.read_text())==report
    else:file.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":main()
