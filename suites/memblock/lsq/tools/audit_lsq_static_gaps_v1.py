import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Re-prove seven exact gaps in the actual53-file Wrapper closure, not a merge."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from audit_sq_initial import ROOT,sha,verify_common


def audit(name):
    run=ROOT/"results"/name
    verify_common(run)
    path=run/"line-audit.json"
    native=json.loads(path.read_text())["native"]
    assert len(native)==1 and native[0]["dut"]=="lsq_wrapper" and native[0]["closure_line_total"]==59602
    native=native[0]
    pinned=json.loads((ROOT/"rtl/lsq_wrapper/source.json").read_text())["files"]
    # Picker's top filename is an alias; its content hash remains exactly
    # original LsqWrapper.sv, as separately verified by the baseline gate.
    entries={"LsqWrapper.sv":native,**{Path(row["source"]).name:row for row in native["dependencies"]}}
    assert len(entries)==len(pinned)==53
    hashes={row["source"]:sha(ROOT/row["source"]) for row in entries.values()}
    assert all(hashes[row["source"]]==pinned[name] for name,row in entries.items())
    source=(ROOT/entries["LoadQueueUncache.sv"]["source"]).read_text()
    proofs=[]
    for lane,guard in enumerate(("_GEN_33","_GEN_34","_GEN_35")):
        suffix="" if lane==0 else f"_{lane}"
        nc,mmio="_respNCMatch_T"+suffix,"_respMMIOMatch_T"+suffix
        for vector,kind,size in ((nc,"nc",16),(mmio,"mmio",16),(guard,None,32)):
            match=re.search(r"wire\s+\["+str(size-1)+r":0\]\s+"+vector+r"\s*=\s*\{([^}]+)\};",source)
            assert match
            members=[item.strip() for item in match[1].split(",")]
            expected=[f"{kind}Match_{lane}_{i}" for i in reversed(range(16))] if kind else [f"{k}Match_{lane}_{i}" for k in ("nc","mmio") for i in reversed(range(16))]
            assert members==expected
        start=source.index(f"if (|{guard}) begin")
        block=source[start:source.index("s2RespValid"+suffix+" <=",start)]
        for target,width in (("s1RespData"+suffix,64),(f"io_bypass_{lane}_s1Resp_bits_paddr_r",48)):
            expression=re.search(r"\b"+target+r"\s*<=([^;]+);",block)
            assert expression
            text=expression[1]
            assert re.match(r"\s*\(\|"+nc+r"\)\s*\?",text) and re.search(r":\s*\(\|"+mmio+r"\)\s*\?",text)
            assert re.search(r":\s*"+str(width)+r"'h0\s*$",text)
            line=source.count("\n",0,start+expression.start(1)+text.rfind(":"))+1
            truth=[dict(nc_any=a,mmio_any=b,write_guard=a or b,default_selected=not a and not b,default_written=(a or b) and not a and not b) for a in (False,True) for b in (False,True)]
            assert not any(row["default_written"] for row in truth)
            proofs.append(dict(source="LoadQueueUncache.sv",line=line,classification="structurally_unreachable_guarded_default",truth_table=truth,
                               proof="This actual Wrapper child uses exactly the same32 NC/MMIO matches to enable the write and select both branches. Default write requires (NCany OR MMIOany) AND NOT NCany AND NOT MMIOany."))
    assert {p["line"] for p in proofs}=={2816,3012,3088,3284,3360,3556}
    wrapper=(ROOT/entries["LsqWrapper.sv"]["source"]).read_text()
    load=(ROOT/entries["LoadQueue.sv"]["source"]).read_text()
    vlq=(ROOT/entries["VirtualLoadQueue.sv"]["source"]).read_text()
    load_instance=wrapper[wrapper.index("LoadQueue loadQueue ("):wrapper.index("StoreQueue storeQueue (")]
    for lane in range(8):
        assert re.search(r"\.io_enq_req_"+str(lane)+r"_valid\s*\(io_enq_needAlloc_"+str(lane)+r"\[0\] & io_enq_req_"+str(lane)+r"_valid\)",load_instance)
        assert re.search(r"\.io_enq_req_"+str(lane)+r"_valid\s*\(io_enq_req_"+str(lane)+r"_valid\)",load)
        assert re.search(r"wire\s+enqCancel_"+str(lane)+r"\s*=\s*io_enq_req_"+str(lane)+r"_valid\s*&\s*io_redirect_valid",vlq)
    assert re.search(r"\.io_redirect_valid\s*\(io_brqRedirect_valid\)",load_instance)
    assert re.search(r"\.io_redirect_valid\s*\(io_redirect_valid\)",load)
    assert "lastEnqCancel_next_r <= 8'h0;" in vlq
    assert "if (_lastEnqCancel_T_12 != lastEnqCancel_next_r)\n        lastEnqCancel_next_r <= _lastEnqCancel_T_12;" in vlq
    expression=re.search(r"wire\s+\[7:0\]\s+_lastEnqCancel_T_12\s*=([^;]+);",vlq)[1]
    assert all(f"enqCancel_{lane} ? _GEN_{lane} : 8'h0" in expression for lane in range(8))
    xs=ucv_paths.source_path_for(ROOT)
    head=subprocess.check_output(["git","-C",str(xs),"rev-parse","HEAD"],text=True).strip()
    assert head=="893e1580b705d81f113c30c7a05734e09a08050e" and not subprocess.check_output(["git","-C",str(xs),"status","--porcelain"],text=True).strip()
    checks={
        "mem/lsqueue/LSQWrapper.scala":["val do_enq = enq.valid && !io.redirect.valid && !io.fromDispatch.recoverStall && io.fromDispatch.iqAccept(i) &&","toLsq.valid := RegNext(do_enq)","loadQueue.io.enq.req(i).valid      := io.enq.needAlloc(i)(0) && io.enq.req(i).valid","loadQueue.io.redirect            <> io.brqRedirect"],
        "backend/CtrlBlock.scala":["lsqEnqCtrl.io.redirect := s1_s3_redirect","io.toMem.lsqEnqIO <> lsqEnqCtrl.io.enqLsq","io.redirect := s1_s3_redirect"],
        "backend/Backend.scala":["io.mem.lsqEnqIO <> ctrlBlock.io.toMem.lsqEnqIO","io.mem.redirect := ctrlBlock.io.redirect"],
        "XSCore.scala":["backend.io.mem.lsqEnqIO <> memBlock.io.ooo_to_mem.enqLsq","memBlock.io.redirect := backend.io.mem.redirect"],
        "mem/MemBlock.scala":["val redirect = RegNextWithEnable(io.redirect)","lsq.io.enq            <> io.ooo_to_mem.enqLsq","lsq.io.brqRedirect    <> redirect"],
    }
    excerpts=[]
    for relative,needles in checks.items():
        file=xs/"src/main/scala/xiangshan"/relative
        text=file.read_text()
        hashes[str(file.relative_to(ROOT.parents[1]))]=sha(file)
        for needle in needles:
            assert needle in text
            excerpts.append(dict(source="XiangShan/src/main/scala/xiangshan/"+relative,line=text.count("\n",0,text.index(needle))+1,excerpt=needle))
    proofs.append(dict(source="VirtualLoadQueue.sv",line=14881,classification="normal_producer_exclusion_not_arbitrary_interface_unreachable",
                       proof="Same externally gated redirect delay reaches actual Wrapper, LoadQueue and VLQ. Ordinary dispatch AND redirect is zero; needAlloc AND dispatch cannot re-enable it. Eight enqCancel terms stay zero; reset initializes the saved sum zero and the change-only write cannot execute.",
                       evidence=excerpts,boundary="Only the pinned normal producer. Direct UNIT-INTERFACE dispatch+redirect can reach this line and was exercised at leaf; not dynamically covered at Wrapper."))
    gaps={(name,g["line"]) for name,row in entries.items() for g in row["uncovered"]}
    proven={(p["source"],p["line"]) for p in proofs}
    assert len(proven)==7 and proven<=gaps
    dest=run/"evidence-auditors"/Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest)==sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__),dest)
    report=dict(run=name,status="actual_wrapper_six_guarded_defaults_and_one_normal_producer_write_reproved",raw_hit=native["closure_line_hit"],raw_total=59602,
                raw_missing=len(gaps),proven_line_count=7,remaining_not_proven=len(gaps-proven),rows=proofs,source_sha256=hashes,
                raw_line_audit_sha256=sha(path),auditor_sha256=sha(dest),
                limits="Reperformed on this actual Wrapper53-file hierarchy and normal public producer connections, not copied leaf coverage/proof result. Six Boolean contradictions plus one narrowly qualified normal-producer exclusion only. No DA hit, exclusion, denominator/RTL/LCOV edit or full functional/formal acceptance.")
    output=run/"static-gap-proof-wrapper-v1.json"
    if output.exists():
        assert json.loads(output.read_text())==report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key not in ("rows","source_sha256")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
