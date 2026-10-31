"""Publish a durable, small coverage summary for the IFU suite.

The full native tables and the complete per-point JSON live under
``results/`` (ignored by Git, tens of megabytes).  This module keeps only the
evidence needed to audit a claim:

* per-DUT hit/total for line, branch and toggle, and the hash of the full
  coverage report;
* the exact residual uncovered line/branch arms with their generated-RTL text;
* the classification of every residual gap (missing case enumeration versus
  a structurally constant/unreachable construct).

Uncovered *toggle bins* are aggregated by signal with their transition list
so the summary stays small; a bin list for tens of thousands of nets is not
useful as a review artifact.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


BUS_INDEX = re.compile(r"_[0-9]+")
BUS_BIT = re.compile(r"\[[0-9]+\]")


def toggle_families(data: dict, sample: int = 24) -> dict:
    """Group never-toggled signal bits by their normalized name.

    Thousands of per-lane bits share one role (a lane's PC bit, a bank's
    register); listing each bit individually makes the artifact large without
    adding review value.  The normalized family plus a bounded sample keeps
    the classification auditable.
    """

    by_family: dict[str, list[str]] = defaultdict(list)
    for signal in data["toggle"]["uncovered_bits"]:
        family = BUS_BIT.sub("[bit]", BUS_INDEX.sub("_N", signal))
        by_family[family].append(signal)
    families = [
        {"family": family, "missing_bits": len(bits),
         "sample": sorted(bits)[:3]}
        for family, bits in sorted(by_family.items())
    ]
    return {
        "families": families,
        "sample_signals": data["toggle"]["uncovered_bits"][:sample],
        "truncated_sample": max(0, len(data["toggle"]["uncovered_bits"]) - sample),
    }


def summarize(report: Path, *, summary_note: str, previous: Path | None) -> dict:
    data = json.loads(report.read_text(encoding="utf-8"))
    duts = {}
    for dut, row in sorted(data["duts"].items()):
        duts[dut] = {
            "line": {k: row["line"][k] for k in
                     ("point_hit", "point_total", "source_hit", "source_total", "percent")},
            "branch": {k: row["branch"][k] for k in ("hit", "total", "percent")},
            "toggle": {k: row["toggle"][k] for k in
                       ("bin_hit", "bin_total", "bin_percent", "bits_hit", "bits_total",
                        "bits_percent")},
            "uncovered_lines": row["line"]["uncovered"],
            "uncovered_branches": row["branch"]["uncovered"],
            "uncovered_toggles": toggle_families(row),
        }
    return {
        "format": "ifu-coverage-summary", "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(report),
        "source_report_sha256": digest(report),
        "pytest_exitstatus": data.get("pytest_exitstatus"),
        "note": summary_note,
        "previous_summary": str(previous) if previous else None,
        "duts": duts,
    }


def markdown(summary: dict) -> str:
    lines = [
        "# IFU 覆盖率摘要（%s）" % summary["run_id"], "",
        "基线 `public-893e1580b` / DefaultConfig；本文件由 `tools/coverage_summary.py`",
        "从该次运行的完整 `coverage.json` 生成。完整原生表、逐点 JSON 与 HTML 位于",
        "忽略目录 `results/` 下，不进入 Git。", "",
        "| DUT | line | branch | toggle bin | 曾变化位 | 未覆盖行 | 未覆盖分支臂 |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for dut, row in summary["duts"].items():
        lines.append(
            f"| `{dut}` | {row['line']['source_hit']}/{row['line']['source_total']} "
            f"({row['line']['percent']:.2f}%) | {row['branch']['hit']}/{row['branch']['total']} "
            f"({row['branch']['percent']:.2f}%) | {row['toggle']['bin_hit']}/"
            f"{row['toggle']['bin_total']} ({row['toggle']['bin_percent']:.2f}%) | "
            f"{row['toggle']['bits_hit']}/{row['toggle']['bits_total']} | "
            f"{len(row['uncovered_lines'])} | {len(row['uncovered_branches'])} |")
    lines += ["", f"源报告 sha256: `{summary['source_report_sha256']}`", ""]
    for dut, row in summary["duts"].items():
        if row["uncovered_lines"] or row["uncovered_branches"]:
            lines += [f"## {dut} 残留", ""]
            for item in row["uncovered_lines"]:
                lines.append(f"- 未覆盖行 L{item['line']}: `{item['verilog']}`")
            for item in row["uncovered_branches"]:
                lines.append(f"- 未覆盖分支 L{item['line']} `{item['arm']}`: `{item['verilog']}`")
            lines.append("")
        families = row["uncovered_toggles"]["families"]
        if families:
            lines += [f"## {dut} 未跳变信号族（前 8）", "",
                      "| 信号族 | 未跳变位数 |", "|---|---:|"]
            for family in sorted(families, key=lambda f: -f["missing_bits"])[:8]:
                lines.append(f"| `{family['family']}` | {family['missing_bits']} |")
            if len(families) > 8:
                lines.append(f"| …其余 {len(families) - 8} 族 | "
                             f"{sum(f['missing_bits'] for f in families[8:])} |")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    summary = summarize(args.report, summary_note=args.note, previous=args.previous)
    summary["run_id"] = args.run_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(summary), encoding="utf-8")
    print(f"{args.output}: {len(summary['duts'])} DUTs, report sha256 {summary['source_report_sha256'][:16]}")
    for dut, row in summary["duts"].items():
        print(f"  {dut}: line {row['line']['percent']:.2f}%  branch {row['branch']['percent']:.2f}%  "
              f"toggle {row['toggle']['bin_percent']:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
