#!/usr/bin/env python3
"""Narrow static proof for six guarded mux defaults; never edits RTL/LCOV."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(name):
    run = ROOT / "results" / name
    path = ROOT / "dut/load_queue_uncache/LoadQueueUncacheDut.v"
    source = path.read_text()
    pinned = json.loads((ROOT / "rtl/load_queue_uncache/source.json").read_text())["files"]["LoadQueueUncache.sv"]
    assert sha(path) == pinned
    rows = []
    for lane, guard in enumerate(("_GEN_33", "_GEN_34", "_GEN_35")):
        suffix = "" if not lane else "_" + str(lane)
        nc, mmio = "_respNCMatch_T" + suffix, "_respMMIOMatch_T" + suffix
        for vector, kind, size in ((nc, "nc", 16), (mmio, "mmio", 16), (guard, None, 32)):
            match = re.search(r"wire\s+\[" + str(size - 1) + r":0\]\s+" + vector + r"\s*=\s*\{([^}]+)\};", source)
            assert match, vector
            members = [item.strip() for item in match[1].split(",")]
            expected = ([f"{kind}Match_{lane}_{i}" for i in reversed(range(16))] if kind else
                        [f"{k}Match_{lane}_{i}" for k in ("nc", "mmio") for i in reversed(range(16))])
            assert members == expected
        start = source.index(f"if (|{guard}) begin")
        end = source.index("s2RespValid" + suffix + " <=", start)
        block = source[start:end]
        for target, width in (("s1RespData" + suffix, 64), (f"io_bypass_{lane}_s1Resp_bits_paddr_r", 48)):
            expression = re.search(r"\b" + target + r"\s*<=([^;]+);", block)
            assert expression, target
            text = expression[1]
            assert re.match(r"\s*\(\|" + nc + r"\)\s*\?", text)
            assert re.search(r":\s*\(\|" + mmio + r"\)\s*\?", text)
            assert re.search(r":\s*" + str(width) + r"'h0\s*$", text)
            offset = source.index(block) + expression.start(1) + text.rfind(":")
            line = source.count("\n", 0, offset) + 1
            truth = [{"nc_any": a, "mmio_any": b, "write_enabled": a or b, "default_selected": not a and not b,
                      "default_written": (a or b) and not a and not b} for a in (False, True) for b in (False, True)]
            assert not any(row["default_written"] for row in truth)
            rows.append({"line": line, "target": target, "lane": lane, "guard": guard, "nc_vector": nc, "mmio_vector": mmio,
                         "classification": "structurally_unreachable_guarded_default", "truth_table": truth,
                         "proof": "guard reduces concatenation of the SAME 16 NC and 16 MMIO matches; writing default requires (NCany OR MMIOany) AND NOT NCany AND NOT MMIOany, contradiction for arbitrary inputs"})
    assert {row["line"] for row in rows} == {2816, 3012, 3088, 3284, 3360, 3556}
    audit = json.loads((run / "line-audit.json").read_text())
    native = next(row for row in audit["native"] if row["dut"] == "load_queue_uncache")
    gaps = {row["line"] for row in native["uncovered"]}
    assert set(row["line"] for row in rows) <= gaps
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(__file__, dest)
    report = {"run": name, "status": "six_guarded_defaults_proven", "source": str(path.relative_to(ROOT)), "source_sha256": pinned,
              "line_audit_sha256": sha(run / "line-audit.json"), "auditor_sha256": sha(dest), "rows": rows,
              "raw_line_hit": native["line_hit"], "raw_line_total": native["line_total"], "remaining_not_proven": sorted(gaps - {row["line"] for row in rows}),
              "limits": "six exact mux defaults only; keeps raw DA denominator, not a whole-DUT formal proof, no RTL or coverage edits"}
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
