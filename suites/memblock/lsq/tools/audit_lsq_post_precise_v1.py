import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Post-compaction actual gates and current resource/source audit, not signoff."""
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import sys

from lsq_evidence_archive_v1 import ROOT, RESULTS, digest, staged


def main():
    selected=("lsq-progress-regression-12","lsq-s4-precise-03","lsq-local-reset-retained-02")
    commands=(("tools/audit_progress_summary_v13.py",),
              ("tools/audit_lsq_s4_precise_summary_v3.py","lsq-s4-precise-03"),
              ("tools/audit_lsq_s4_precise_coverage_v2.py","lsq-s4-precise-03"),
              ("tools/audit_lsq_local_reset_v2.py","lsq-local-reset-retained-02"),
              ("tools/audit_lsq_local_reset_coverage_v1.py","lsq-local-reset-retained-02"))
    checks=[]
    with ExitStack() as stack:
        for name in sorted((*selected,"lsq-s4-precise-02","lsq-local-reset-retained-01")):
            stack.enter_context(staged(RESULTS/name))
        for args in commands:
            r=subprocess.run([sys.executable,"-B",*args],cwd=ROOT,capture_output=True,text=True)
            assert r.returncode==0,(args,r.stdout,r.stderr)
            result=json.loads(r.stdout)
            checks.append(dict(command=[sys.executable,"-B",*args],exit_code=r.returncode,status=result["status"],tests=result["tests"],auditor_SHA256=digest(ROOT/args[0])))
    # The staging context must remove every temporary restored native/report.
    for name in selected:
        index=json.loads((RESULTS/name/"storage-index-v1.json").read_text())
        assert all(not (RESULTS/name/e["path"]).exists() for e in index["files"])
    retired=json.loads((RESULTS/"retire-native-predecessors-post-precise-v1.json").read_text())
    assert all(not (ROOT/e["path"]).exists() for e in retired["files"])
    rtl=ucv_paths.soc_rtl_for(ROOT);rtl_count=0
    for line in(ROOT/"manifest/lsq-rtl.sha256").read_text().splitlines():
        h,name=line.split();assert digest(rtl/name)==h;rtl_count+=1
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ucv_paths.source_path_for(ROOT),text=True).strip()
    clean=subprocess.check_output(["git","status","--short","--untracked-files=no"],cwd=ucv_paths.source_path_for(ROOT),text=True).strip()
    assert head=="893e1580b705d81f113c30c7a05734e09a08050e" and not clean and rtl_count==53
    reference=json.loads((RESULTS/selected[0]/"source-evidence.json").read_text())["files"]
    refs={p:h for p,h in reference.items() if p.startswith("lsqverify/")}
    assert all(digest(ROOT/p)==h for p,h in refs.items())
    broken=[]
    docs=[ROOT/"README.md",ROOT/"docs/ut-plan.md",*(ROOT/"docs/reports"/n for n in("lsq-progress-regression-12-20261019.md","lsq-s4-precise-20261019.md","lsq-local-reset-20261019.md"))]
    import re
    for doc in docs:
        for target in re.findall(r"\]\(([^)]+)\)",doc.read_text()):
            if target.startswith(("http:","https:","#")):continue
            if not (doc.parent/target.split("#")[0]).exists():broken.append(dict(document=str(doc.relative_to(ROOT)),target=target))
    # Historical documents may reference intentionally retired raw paths, but
    # all newly delivered report links above must be directly readable.
    new_report_names={"lsq-progress-regression-12-20261019.md","lsq-s4-precise-20261019.md","lsq-local-reset-20261019.md"}
    assert not [b for b in broken if Path(b["document"]).name in new_report_names]
    logical=physical=files=0;inodes=set();raw=waves=0
    for path in RESULTS.rglob("*"):
        if not path.is_file() or path.is_symlink():continue
        s=path.stat();files+=1;logical+=s.st_size
        key=(s.st_dev,s.st_ino)
        if key not in inodes:inodes.add(key);physical+=s.st_blocks*512
        if "cases" in path.parts:
            raw+=path.suffix==".jsonl";waves+=path.suffix in(".fst",".vcd")
    assert raw==waves==0
    report=dict(status="POST_PRECISE_AND_LOCAL_RESET_EVIDENCE_AUDITED_OVERALL_STILL_ACTIVE_NOT_SIGNOFF",actual_post_compaction_gates=checks,
                fixed_open_source_HEAD=head,open_source_tracked_tree_clean=True,fixed_RTL_SHA_files=rtl_count,unchanged_shared_reference_files=len(refs),
                results_actual_files=files,results_logical_bytes=logical,results_unique_allocated_bytes=physical,disk_free_bytes=shutil.disk_usage(ROOT).free,
                uncompressed_case_JSONL=raw,waveforms=waves,temporary_native_restorations_left=0,retired_predecessor_native_paths_restored=0,
                newly_delivered_report_links_all_readable=True,historical_document_broken_paths=broken,auditor_SHA256=digest(Path(__file__)),
                limits="Audited actual partial deliveries only. Regression12 still221 FAILs; 84 preciseS4 and15 retained-reset profiles do not replace whole normal random/other128/old-generation/late-ack/serial reset/final request audit. Main journals remain streamed summaries, not unretained raw offline replay.")
    out=RESULTS/"post-precise-end-audit-v1.json"
    with out.open("x") as f:f.write(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="actual_post_compaction_gates"},indent=2))


if __name__=="__main__":main()
