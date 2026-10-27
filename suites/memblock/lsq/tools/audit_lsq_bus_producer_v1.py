import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Narrow, archived open-source constraints for the observed Wrapper bus bug.

This is NOT a complete Backend reachability proof, re-elaboration or an actual
Uncache co-simulation. It records why NC/non-NC coexistence is not excluded by
the inspected public admission source; exact external SID scheduling is separate.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from audit_sq_initial import ROOT, sha


def audit(name):
    run = ROOT / "results" / name
    public = ucv_paths.source_path_for(ROOT)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=public, text=True).strip()
    assert revision == "893e1580b705d81f113c30c7a05734e09a08050e"
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=public, text=True)
    assert not status
    sources = {
        "src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala": [(273, 340)],
        "src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala": [(76, 145), (170, 197)],
        "src/main/scala/xiangshan/mem/lsqueue/VirtualStoreQueue.scala": [(283, 330)],
        "src/main/scala/xiangshan/cache/dcache/Uncache.scala": [(255, 263), (344, 390), (405, 409), (493, 499)],
        "src/main/scala/xiangshan/Parameters.scala": [(183, 193)],
    }
    evidence = []
    for relative, regions in sources.items():
        source = public / relative
        copy = run / "producer-source" / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        if copy.exists():
            assert sha(copy) == sha(source)
        else:
            shutil.copy2(source, copy)
        lines = source.read_text().splitlines()
        evidence.append(dict(source="XiangShan/" + relative, sha256=sha(source), archived=str(copy.relative_to(run)),
                             regions=[dict(first=first, last=last, text="\n".join(f"{n}: {lines[n - 1]}" for n in range(first, last + 1))) for first, last in regions]))
    unc = (public / "src/main/scala/xiangshan/cache/dcache/Uncache.scala").read_text()
    assert "val e0_reject = (do_uarch_drain && !skidOccupied) ||" in unc
    assert "(!e0_canMerge && !e0_invalidVec.asUInt.orR) || e0_rejectVec.reduce(_ || _)" in unc
    assert "q0_canSent := q0_res._2 && (io.enableOutstanding || uState === s_idle)" in unc
    wrapper = (public / "src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala").read_text()
    assert wrapper.count("when(io.uncache.resp.fire){") == 2
    raw = (ucv_paths.soc_rtl_for(ROOT) / 'LsqWrapper.sv').read_text()
    assert "else if ((pendingstate == 2'h1 | pendingstate == 2'h2) & io_uncache_resp_valid)" in raw
    bus_audit = json.loads((run / "bus-history-audit-v3.json").read_text())
    failures = []
    for case in bus_audit["cases"]:
        if not any(v["issue"] == "LSQ-BUS-OWNERSHIP-001" for v in case.get("violations", [])):
            continue
        trace = [json.loads(line) for line in (run / case["journal"]).read_text().splitlines()]
        requests = case["requests"]
        assert set(requests) == {"store", "load0"} and requests["load0"]["tick"] < requests["store"]["tick"]
        assert requests["load0"]["nc"] and not requests["store"]["nc"]
        addresses = [trace[-1]["after"]["io_uncache_req_bits_addr"]]
        allocated = False
        for row in trace:
            if row["before"]["io_uncache_req_valid"] and row["input"]["bus"]["ready"]:
                addresses.append(row["before"]["io_uncache_req_bits_addr"])
            if any(d["valid"] for d in row["input"]["dispatch"]):
                allocated = True
                enabled = [d for d in row["input"]["dispatch"] if d["valid"]]
                assert [d["need_alloc"] for d in enabled] == [2, 1, 1]
                assert [d["rob"]["value"] for d in enabled] == [0, 1, 2]
            if allocated and not row["input"]["reset"]:
                assert row["input"]["pending"]["value"] == 0 and row["input"]["bus"]["outstanding"]
        assert len({addr // 64 for addr in addresses}) == 3
        failures.append(dict(nodeid=case["nodeid"], journal_sha256=case["sha256"], three_distinct_64B_blocks=addresses,
                             global_rob_head_stays_at_old_store=0, actual_old_nc_load_req_tick=requests["load0"]["tick"],
                             actual_serial_io_store_req_tick=requests["store"]["tick"]))
    assert len(failures) == 4
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, fixed_public_commit=revision, tracked_public_tree_clean=True, sources=evidence, failure_cases=failures,
                  findings=[
                      "The actual global ROB stays at older Store0; two younger NC Loads are not retired. Store request comes through real VSQ/PSQ, no external readiness/preCommit forcing.",
                      "Load entry NC request eligibility is independent of waiting for ROB head; ordinary MMIO head constraints are not borrowed for NC.",
                      "Open Uncache admission rejects drains/full/same-block conflicts; the inspected e0 source has no blanket non-NC waits for all NC responses condition. Three original addresses use distinct blocks and capacity2 of16.",
                      "enableOutstanding permits multiple to-bus transactions. Independent response/SID direction can return an older NC Load while Wrapper is serially occupied by an IO Store.",
                      "Pinned Wrapper SV1507-1508 and Chisel291-299 clear serial state on any response, without matching direction/owner. Actual four failing raw histories expose the next Load req.valid before the IO Store own response."
                  ], auditor_sha256=sha(dest),
                  limits="Narrow public-interface/inspected-source domain evidence, not full Backend/ISA reachability, exact external allocator priority/SID timing reproduction, native Uncache co-simulation, or Chisel-to-generated-RTL re-elaboration. No third request fire or architecture damage was observed in these strict-stop traces. No admission constraint was removed from a test to make it pass.")
    output = run / "producer-domain-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("run", "fixed_public_commit", "tracked_public_tree_clean", "findings", "limits")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
