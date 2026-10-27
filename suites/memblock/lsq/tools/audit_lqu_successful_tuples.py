#!/usr/bin/env python3
"""Positive-only s2 witnesses, supplementing the independent LQU trace audit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name):
    run = ROOT / "results" / name
    trace_audit = json.loads((run / "trace-audit.json").read_text())
    assert trace_audit["status"] == "evidence_audited_with_failures" and trace_audit["dut_acceptance"] == "NOT_PASS"
    proofs = {}
    for path in sorted((run / "cases").rglob("load_queue_uncache.jsonl")):
        previous = None
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if previous and row["checked"] and not row["input"]["reset"]:
                owners = {owner["uid"]: owner for owner in previous.get("change", {}).get("before", [])}
                for lane, match in enumerate(previous.get("change", {}).get("matches", [])):
                    if not match:
                        continue
                    prefix = f"io_bypass_{lane}_s2Resp_"
                    assert row["after"][prefix + "valid"]
                    assert row["after"][prefix + "bits_data"] == match["data"] * ((1 << 64) + 1)
                    assert row["after"][prefix + "bits_derr"] == match["error"] and row["after"][prefix + "bits_nderr"] == match["nderr"]
                    owner = owners[match["uid"]]
                    key = f"{owner['slot']}:{int(owner['load']['entry']['nc'])}:{lane}"
                    proofs.setdefault(key, {"journal": str(path.relative_to(run)), "journal_sha256": sha(path),
                                            "s1_tick": previous["post_tick"], "s2_checked_tick": row["post_tick"], "uid": match["uid"]})
            previous = row
    assert set(proofs) == {f"{slot}:{nc}:{lane}" for slot in range(16) for nc in range(2) for lane in range(3)}
    result = {"scope": "all 96 entry/type/bypass-lane tuples completed successful s2 data/error comparison; no failed output used as positive proof", "tuples": 96, "proofs": proofs}
    output = run / "successful-bypass-tuples.json"
    if output.exists():
        assert json.loads(output.read_text()) == result
    else:
        output.write_text(json.dumps(result, indent=2) + "\n")
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(__file__, dest)
    receipt = {"run": name, "status": "96_successful_s2_tuple_witnesses", "trace_audit_sha256": sha(run / "trace-audit.json"),
               "tuples_sha256": sha(output), "auditor_sha256": sha(dest),
               "limits": "uses owner/match facts already independently validated by trace audit; positive results only, does not waive eight failing tests"}
    receipt_path = run / "successful-bypass-tuples-audit.json"
    if receipt_path.exists():
        assert json.loads(receipt_path.read_text()) == receipt
    else:
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
