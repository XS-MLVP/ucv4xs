import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Narrow proofs in the REAL LoadQueue closure; retain every raw DA line."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from audit_sq_initial import ROOT, sha


def prove(name):
    run = ROOT / "results" / name
    audit_path = run / "line-audit.json"
    audit = json.loads(audit_path.read_text())
    native = next(row for row in audit["native"] if row["dut"] == "load_queue")
    assert native["line_total"] == 57 and native["closure_line_total"] == 50520
    pinned = json.loads((ROOT / "rtl/load_queue/source.json").read_text())["files"]
    dependencies = {Path(row["source"]).name: row for row in native["dependencies"]}
    rows, sources = [], {}
    path = ROOT / dependencies["LoadQueueUncache.sv"]["source"]
    source = path.read_text()
    assert sha(path) == pinned[path.name]
    sources[str(path.relative_to(ROOT))] = sha(path)
    for lane, guard in enumerate(("_GEN_33", "_GEN_34", "_GEN_35")):
        suffix = "" if not lane else "_" + str(lane)
        nc, mmio = "_respNCMatch_T" + suffix, "_respMMIOMatch_T" + suffix
        for vector, kind, size in ((nc, "nc", 16), (mmio, "mmio", 16), (guard, None, 32)):
            match = re.search(r"wire\s+\[" + str(size - 1) + r":0\]\s+" + vector + r"\s*=\s*\{([^}]+)\};", source)
            assert match
            members = [item.strip() for item in match[1].split(",")]
            expected = ([f"{kind}Match_{lane}_{i}" for i in reversed(range(16))] if kind else
                        [f"{k}Match_{lane}_{i}" for k in ("nc", "mmio") for i in reversed(range(16))])
            assert members == expected
        start = source.index(f"if (|{guard}) begin")
        block = source[start:source.index("s2RespValid" + suffix + " <=", start)]
        for target, width in (("s1RespData" + suffix, 64), (f"io_bypass_{lane}_s1Resp_bits_paddr_r", 48)):
            expression = re.search(r"\b" + target + r"\s*<=([^;]+);", block)
            assert expression
            text = expression[1]
            assert re.match(r"\s*\(\|" + nc + r"\)\s*\?", text)
            assert re.search(r":\s*\(\|" + mmio + r"\)\s*\?", text)
            assert re.search(r":\s*" + str(width) + r"'h0\s*$", text)
            offset = start + expression.start(1) + text.rfind(":")
            line = source.count("\n", 0, offset) + 1
            truth = [{"nc_any": a, "mmio_any": b, "write_enabled": a or b,
                      "default_written": (a or b) and not a and not b} for a in (False, True) for b in (False, True)]
            assert not any(row["default_written"] for row in truth)
            rows.append(dict(source=path.name, line=line, target=target,
                             classification="structurally_unreachable_guarded_default", truth_table=truth,
                             proof="same NC/MMIO vectors guard the write and select the data; default write requires (NCany OR MMIOany) AND NOT NCany AND NOT MMIOany"))
    assert {row["line"] for row in rows} == {2816, 3012, 3088, 3284, 3360, 3556}

    vlq = ROOT / dependencies["VirtualLoadQueue.sv"]["source"]
    source = vlq.read_text()
    assert sha(vlq) == pinned[vlq.name]
    sources[str(vlq.relative_to(ROOT))] = sha(vlq)
    for lane in range(8):
        assert re.search(r"wire\s+enqCancel_" + str(lane) + r"\s*=\s*io_enq_req_" + str(lane) + r"_valid\s*&\s*io_redirect_valid", source)
    assert "lastEnqCancel_next_r <= 8'h0;" in source
    assert "if (_lastEnqCancel_T_12 != lastEnqCancel_next_r)\n        lastEnqCancel_next_r <= _lastEnqCancel_T_12;" in source
    summation = re.search(r"wire\s+\[7:0\]\s+_lastEnqCancel_T_12\s*=([^;]+);", source)[1]
    assert all(f"enqCancel_{lane} ? _GEN_{lane} : 8'h0" in summation for lane in range(8))
    xs = ucv_paths.source_path_for(ROOT)
    baseline = json.loads((ROOT / "manifest/baseline.json").read_text())
    # Commit is explicitly pinned; no private repository is consulted.
    head = subprocess.check_output(["git", "-C", str(xs), "rev-parse", "HEAD"], text=True).strip()
    assert head == "893e1580b705d81f113c30c7a05734e09a08050e"
    assert not subprocess.check_output(["git", "-C", str(xs), "status", "--porcelain"], text=True).strip()
    checks = {
        "mem/lsqueue/LSQWrapper.scala": [
            "val do_enq = enq.valid && !io.redirect.valid && !io.fromDispatch.recoverStall && io.fromDispatch.iqAccept(i) &&",
            "toLsq.valid := RegNext(do_enq)", "loadQueue.io.enq.req(i).valid      := io.enq.needAlloc(i)(0) && io.enq.req(i).valid",
            "loadQueue.io.redirect            <> io.brqRedirect"],
        "backend/CtrlBlock.scala": ["lsqEnqCtrl.io.redirect := s1_s3_redirect", "io.toMem.lsqEnqIO <> lsqEnqCtrl.io.enqLsq", "io.redirect := s1_s3_redirect"],
        "backend/Backend.scala": ["io.mem.lsqEnqIO <> ctrlBlock.io.toMem.lsqEnqIO", "io.mem.redirect := ctrlBlock.io.redirect"],
        "XSCore.scala": ["backend.io.mem.lsqEnqIO <> memBlock.io.ooo_to_mem.enqLsq", "memBlock.io.redirect := backend.io.mem.redirect"],
        "mem/MemBlock.scala": ["val redirect = RegNextWithEnable(io.redirect)", "lsq.io.enq            <> io.ooo_to_mem.enqLsq", "lsq.io.brqRedirect    <> redirect"],
    }
    evidence = []
    for relative, texts in checks.items():
        path = xs / "src/main/scala/xiangshan" / relative
        text = path.read_text()
        sources[str(path.relative_to(ROOT.parents[1]))] = sha(path)
        for excerpt in texts:
            assert excerpt in text
            evidence.append(dict(source="XiangShan/src/main/scala/xiangshan/" + relative,
                                 line=text[:text.index(excerpt)].count("\n") + 1, excerpt=excerpt))
    rows.append(dict(source="VirtualLoadQueue.sv", line=14881, classification="excluded_by_real_normal_producer_not_arbitrary_interface_unreachable",
                     proof="LsqEnqCtrl registers valid gated by NOT redirect; the same redirect is delayed one edge in MemBlock and reaches both real queues. Thus valid AND redirect = 0 at LSQ in the normal producer path. All eight enqCancel terms are zero; reset initializes lastEnqCancel_next_r=0 and induction keeps it zero, so its change-only write does not execute.",
                     source_commit=head, evidence=evidence,
                     boundary="not a proof for arbitrary direct UNIT-INTERFACE dispatch+redirect; leaf VLQ tests exercise that wider interface separately"))
    gap_keys = {(name, gap["line"]) for name, dep in dependencies.items() for gap in dep["uncovered"]}
    proven = {(row["source"], row["line"]) for row in rows}
    assert proven <= gap_keys
    remaining = sorted(gap_keys - proven)
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="six_exact_mux_defaults_and_one_normal_producer_write_proven",
                  source_sha256=sources, raw_line_audit_sha256=sha(audit_path), auditor_sha256=sha(dest), rows=rows,
                  raw_line_hit=native["closure_line_hit"], raw_line_total=native["closure_line_total"],
                  proven_line_count=len(proven), remaining_not_proven=remaining,
                  limits="No RTL, LCOV or denominator edits. Six arbitrary-input boolean contradictions and one explicitly normal-producer exclusion ONLY. Not general formal proof, not leaf coverage substitution, not functional PASS.")
    output = run / "static-gap-proof.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    prove(parser.parse_args().name)
