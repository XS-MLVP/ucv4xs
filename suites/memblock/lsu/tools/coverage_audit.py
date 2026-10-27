#!/usr/bin/env python3
"""Audit line/toggle/branch coverage of a committed toffee run.

Every denominator is retained per Picker build. Picker harness files are
reported separately from the real DUT. Uncovered lines are listed with their
source text so each gap can be attributed to a functional point; nothing is
deleted or rescaled.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = __import__("ucv.runtime", fromlist=["toolchain"]).toolchain()
VERILATOR_COVERAGE = LOCK["verilator"]["coverage_processor"]
METRIC = re.compile(r"^\s+(line|toggle|branch|expr|fsm_state|fsm_arc)\s+:\s+([0-9.]+)%\s+\(\s*([0-9]+)\s*/\s*([0-9]+)\)")
DAT_POINT = re.compile(r"C '(.*)' (\d+)\n?\Z")
DECL = re.compile(r"^(wire|reg|logic|input|output|inout|parameter|localparam)\b")
ALWAYS = re.compile(r"^(initial|always|always_ff|always_comb|always_latch|function|task)\b")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_harness(path: str) -> bool:
    name = Path(path).name
    return name.endswith("_top.sv") or name.endswith("_top.v")


def summary(dat: Path) -> dict:
    proc = subprocess.run(
        [VERILATOR_COVERAGE, "--report", "summary", str(dat)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    metrics = {}
    for line in proc.stdout.splitlines():
        match = METRIC.match(line)
        if match:
            kind, percent, hit, total = match.groups()
            metrics[kind] = dict(percent=float(percent), hit=int(hit), total=int(total))
    return dict(metrics=metrics, analyzer=f"{VERILATOR_COVERAGE} --report summary {dat}")


def parse_info(info: Path):
    tables: dict[str, dict] = {}
    current = None
    for row in info.read_text().splitlines():
        if row.startswith("SF:"):
            current = row[3:]
            tables.setdefault(current, {"da": {}, "branches": []})
        elif row.startswith("DA:") and current is not None:
            line, hits = row[3:].split(",")[:2]
            tables[current]["da"][int(line)] = tables[current]["da"].get(int(line), 0) + int(hits)
        elif row.startswith("BRDA:") and current is not None:
            line, block, branch, taken = row[5:].split(",")
            tables[current]["branches"].append(
                dict(line=int(line), block=int(block), branch=branch, taken=taken)
            )
    return tables


def declaration_lines(source: list[str]) -> set[int]:
    marked: set[int] = set()
    index = 0
    while index < len(source):
        text = source[index].strip()
        if DECL.match(text):
            start = index
            while index < len(source) and ";" not in source[index]:
                index += 1
            for line in range(start, min(index + 1, len(source))):
                marked.add(line + 1)
        elif text in ("end", "endmodule", "endcase", "endfunction", "endtask") or text == "":
            marked.add(index + 1)
        index += 1
    return marked


def enclosing_construct(source: list[str], line: int) -> tuple[str, int]:
    for index in range(min(line, len(source)) - 1, -1, -1):
        text = source[index].strip()
        if ALWAYS.match(text):
            return text.split()[0], index + 1
    return "unknown", 0


def dat_points(dat: Path):
    with dat.open("rb") as stream:
        for raw in stream:
            match = DAT_POINT.fullmatch(raw.decode("latin1"))
            if match is None:
                continue
            fields = dict(part.split("\x02", 1) for part in match[1].split("\x01") if "\x02" in part)
            yield dict(
                file=fields.get("f", ""),
                line=int(fields.get("l", 0)),
                kind=fields.get("t", ""),
                name=fields.get("o", ""),
                count=int(match[2]),
            )


def contiguous_blocks(rows: list[dict]) -> list[dict]:
    blocks = []
    for row in rows:
        if blocks and row["file"] == blocks[-1]["file"] and row["line"] == blocks[-1]["end"] + 1:
            blocks[-1]["end"] = row["line"]
            blocks[-1]["lines"] += 1
        else:
            blocks.append(dict(file=row["file"], start=row["line"], end=row["line"], lines=1))
    return blocks


def classify_toggle(row: dict) -> str:
    name = row["name"]
    if row["construct"] == "initial":
        return "initial_random_state"
    if name.startswith("io_"):
        return "public_port_bit"
    if "state" in name or "fsm" in name:
        return "state_bit"
    if "data" in name or "mask" in name:
        return "data_or_mask_bit"
    if "valid" in name or "ready" in name or "resp" in name or "fire" in name:
        return "handshake_bit"
    return "other_internal_bit"


def _audit_one(run: Path, dat: Path, info: Path, functional: dict) -> dict:
    metrics = summary(dat)
    tables = parse_info(info)
    sources = {}
    for source in tables:
        path = Path(source)
        sources[source] = path.read_text().splitlines() if path.is_file() else []

    per_file = {}
    overall = dict(unique_lines=0, covered_lines=0, uncovered=0, procedural_uncovered=0)
    dut_only = dict(unique_lines=0, covered_lines=0, uncovered=0, procedural_uncovered=0)
    uncovered_procedural: list[dict] = []
    uncovered_declarative: list[dict] = []
    for source, table in tables.items():
        text = sources[source]
        da = table["da"]
        declarative = declaration_lines(text)
        uncovered = sorted(line for line, hits in da.items() if not hits)
        procedural = [line for line in uncovered if line not in declarative]
        decl = [line for line in uncovered if line in declarative]
        covered = sum(1 for hits in da.values() if hits)
        role = "picker_harness" if is_harness(source) else "dut"
        per_file[source] = dict(
            role=role,
            unique_lines=len(da), covered_lines=covered,
            coverage_percent=round(100.0 * covered / len(da), 4) if da else 0.0,
            uncovered=len(uncovered),
            uncovered_procedural=len(procedural),
            uncovered_declarative=len(decl),
            uncovered_procedural_lines=[
                dict(line=line, source=text[line - 1].strip()) for line in procedural
                if 0 < line <= len(text)
            ],
            uncovered_declarative_lines=[
                dict(line=line, source=text[line - 1].strip()) for line in decl
                if 0 < line <= len(text)
            ],
        )
        overall["unique_lines"] += len(da)
        overall["covered_lines"] += covered
        overall["uncovered"] += len(uncovered)
        overall["procedural_uncovered"] += len(procedural)
        if role == "dut":
            dut_only["unique_lines"] += len(da)
            dut_only["covered_lines"] += covered
            dut_only["uncovered"] += len(uncovered)
            dut_only["procedural_uncovered"] += len(procedural)
            uncovered_procedural.extend(
                dict(file=source, line=line, source=text[line - 1].strip())
                for line in procedural if 0 < line <= len(text)
            )
        uncovered_declarative.extend(
            dict(file=source, line=line, source=text[line - 1].strip())
            for line in decl if 0 < line <= len(text)
        )
    for row in (overall, dut_only):
        row["coverage_percent"] = round(100.0 * row["covered_lines"] / row["unique_lines"], 4) if row["unique_lines"] else 0.0

    branches = []
    for source, table in tables.items():
        text = sources[source]
        for row in table["branches"]:
            construct, at = enclosing_construct(text, row["line"])
            branches.append(dict(
                file=source, line=row["line"], branch=row["branch"], taken=row["taken"],
                construct=construct, construct_line=at,
                harness=is_harness(source),
                source=text[row["line"] - 1].strip() if 0 < row["line"] <= len(text) else "",
            ))
    branch_uncovered = [row for row in branches if row["taken"] in ("0", "-", "")]

    toggle_total = toggle_hit = 0
    toggle_uncovered: list[dict] = []
    for point in dat_points(dat):
        if point["kind"] != "toggle":
            continue
        toggle_total += 1
        if point["count"]:
            toggle_hit += 1
            continue
        text = sources.get(point["file"], [])
        construct, at = enclosing_construct(text, point["line"])
        row = dict(name=point["name"], file=point["file"], line=point["line"],
                   construct=construct, construct_line=at, harness=is_harness(point["file"]))
        row["class"] = classify_toggle(row)
        toggle_uncovered.append(row)
    toggle_dut_uncovered = [row for row in toggle_uncovered if not row["harness"]]
    toggle_dut_total = sum(1 for point in dat_points(dat)
                           if point["kind"] == "toggle" and not is_harness(point["file"]))
    toggle_dut_hit = toggle_dut_total - len(toggle_dut_uncovered)

    return {
        "format": "lsu-coverage-audit-build-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": str(run.relative_to(ROOT)),
        "coverage_dat_sha256": digest(dat),
        "coverage_info_sha256": digest(info),
        "source_files": {source: dict(sha256=digest(Path(source)), lines=len(sources[source]))
                         for source in sources if Path(source).is_file()},
        "verilator_point_metrics": metrics,
        "lcov_lines": overall,
        "lcov_lines_dut_only": dut_only,
        "lcov_lines_per_file": per_file,
        "uncovered_blocks": contiguous_blocks(uncovered_procedural),
        "uncovered_procedural_lines": uncovered_procedural,
        "uncovered_declarative_lines": uncovered_declarative,
        "branches": {
            "total": len(branches),
            "covered": len(branches) - len(branch_uncovered),
            "uncovered": branch_uncovered,
        },
        "toggles": {
            "total": toggle_total,
            "covered": toggle_hit,
            "uncovered": len(toggle_uncovered),
            "classes": dict(Counter(row["class"] for row in toggle_uncovered)),
            "uncovered_points": toggle_uncovered,
        },
        "toggles_dut_only": {
            "total": toggle_dut_total,
            "covered": toggle_dut_hit,
            "uncovered": len(toggle_dut_uncovered),
            "coverage_percent": round(100.0 * toggle_dut_hit / toggle_dut_total, 4)
            if toggle_dut_total else 0.0,
            "classes": dict(Counter(row["class"] for row in toggle_dut_uncovered)),
            "uncovered_points": toggle_dut_uncovered,
        },
        "functional_coverage": functional,
        "limits": (
            "Verilator point summaries are not semantic checks. LCOV DA hits are summed per "
            "line; every denominator is retained. Declarative wire/reg/end lines are separated "
            "by source text, not deleted. Picker harness files are reported separately from the "
            "real DUT. Toggle points are raw RTL nets; reset-only and tie-off nets are listed, "
            "not filtered."
        ),
    }


def build_key(run: Path, artifact: dict) -> str:
    names = list(artifact.get("build", {}).get("files", {}))
    for name in names:
        parts = Path(name).parts
        if "dut" in parts:
            index = parts.index("dut")
            if index + 1 < len(parts):
                return parts[index + 1]
    return artifact.get("build", {}).get("name", "unknown")


def audit(run: Path, report_name: str) -> dict:
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest.get("state") != "committed" or not manifest.get("coverage_complete"):
        raise SystemExit("run is not a committed, coverage-complete toffee run")
    functional_path = run / "functional-coverage.json"
    functional = json.loads(functional_path.read_text()) if functional_path.is_file() else {
        "coverage": 0.0, "covered": False, "groups": []}
    builds = []
    for artifact in manifest.get("artifacts", []):
        if artifact.get("kind") != "native":
            continue
        dat = Path(artifact["path"])
        info = dat.with_suffix(".info")
        if not info.is_file():
            raise SystemExit(f"missing LCOV export for {dat}")
        record = _audit_one(run, dat, info, functional)
        record["key"] = build_key(run, artifact)
        record["build_id"] = artifact.get("build", {}).get("build_id")
        record["build_name"] = artifact.get("build", {}).get("name")
        builds.append(record)
    if not builds:
        raise SystemExit(f"no native coverage database under {run}")
    result = {
        "format": "lsu-coverage-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": str(run.relative_to(ROOT)),
        "build_count": len(builds),
        "keys": [record["key"] for record in builds],
        "builds": builds,
        "functional_coverage": functional,
        "limits": (
            "Each Picker build keeps its own native numerator/denominator; a combined run must "
            "not sum lines across DUTs. Functional coverage is the runner-merged file and is "
            "attributed to the run, not to a single build, unless the run contains one build."
        ),
    }
    (run / report_name).write_text(json.dumps(result, indent=2) + "\n")
    return result


def markdown(result: dict) -> str:
    lines = [
        f"# LSU 覆盖率审计：{result['run']}",
        "",
        f"- 原生构建数：{result['build_count']}",
        f"- DUT：{', '.join(f'`{key}`' for key in result['keys'])}",
        "",
    ]
    for build in result["builds"]:
        lines.append(f"## {build['key']}（{build['build_name']}）")
        lines.append("")
        lines.append(f"- coverage.dat SHA-256：`{build['coverage_dat_sha256']}`")
        lines.append("")
        lines.append("### Verilator 原生点统计")
        lines.append("")
        lines.append("| 类型 | 命中 / 总数 | 百分比 |")
        lines.append("|---|---:|---:|")
        for kind, row in build["verilator_point_metrics"]["metrics"].items():
            lines.append(f"| {kind} | {row['hit']} / {row['total']} | {row['percent']:.2f}% |")
        lines.append("")
        lines.append("### LCOV 逐行")
        lines.append("")
        lines.append("| 源文件 | 角色 | 命中 / 唯一行 | 过程语句未覆盖 |")
        lines.append("|---|---|---:|---:|")
        for source, row in build["lcov_lines_per_file"].items():
            lines.append(
                f"| `{Path(source).name}` | {row['role']} | {row['covered_lines']} / "
                f"{row['unique_lines']} ({row['coverage_percent']:.2f}%) | "
                f"{row['uncovered_procedural']} |"
            )
        dut = build["lcov_lines_dut_only"]
        lines.append("")
        lines.append(f"- DUT-only 行覆盖：{dut['covered_lines']} / {dut['unique_lines']} "
                     f"({dut['coverage_percent']:.2f}%)，过程语句未覆盖 {dut['procedural_uncovered']}")
        lines.append("")
        if build["uncovered_procedural_lines"]:
            lines.append("### 未覆盖过程语句行")
            lines.append("")
            lines.append("| 文件:行 | 源码 |")
            lines.append("|---|---|")
            for row in build["uncovered_procedural_lines"]:
                lines.append(f"| {Path(row['file']).name}:{row['line']} | `{row['source'][:110]}` |")
            lines.append("")
        lines.append("### 未覆盖连续块")
        lines.append("")
        for block in build["uncovered_blocks"]:
            lines.append(f"- {Path(block['file']).name}:{block['start']}-{block['end']}（{block['lines']} 行）")
        lines.append("")
        lines.append("### 分支")
        lines.append("")
        lines.append(f"- 覆盖 {build['branches']['covered']} / {build['branches']['total']}")
        for row in build["branches"]["uncovered"]:
            lines.append(f"- {Path(row['file']).name}:{row['line']} `{row['branch']}` in "
                         f"`{row['construct']}`：`{row['source'][:90]}`")
        lines.append("")
        lines.append("### Toggle")
        lines.append("")
        lines.append(f"- 全部点：{build['toggles']['covered']} / {build['toggles']['total']}")
        lines.append(f"- DUT-only：{build['toggles_dut_only']['covered']} / "
                     f"{build['toggles_dut_only']['total']} "
                     f"({build['toggles_dut_only']['coverage_percent']:.2f}%)")
        lines.append("- 未覆盖分类：")
        for cls, count in sorted(build["toggles_dut_only"]["classes"].items()):
            lines.append(f"  - `{cls}`：{count}")
        lines.append("")
        lines.append("逐点信号名、文件与源行见 JSON 的 `toggles_dut_only.uncovered_points`。")
        lines.append("")
        lines.append(build["limits"])
        lines.append("")
    lines.append(result["limits"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("--json", default="coverage-audit.json")
    parser.add_argument("--markdown", default="coverage-audit.md")
    args = parser.parse_args()
    run = (ROOT / "results" / args.run).resolve()
    if not run.is_dir():
        raise SystemExit(f"run directory not found: {run}")
    result = audit(run, args.json)
    (run / args.markdown).write_text(markdown(result) + "\n")
    print(f"audited {result['build_count']} build(s); evidence: {run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
