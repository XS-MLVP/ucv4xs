#!/usr/bin/env python3
"""Audit line/toggle/branch coverage of a committed toffee run.

Every denominator is retained. Uncovered line/branch/toggle points are
classified per source file; generated-RTL declarative lines are separated from
procedural lines, never deleted or rescaled. Uncovered lines are additionally
grouped into contiguous blocks so each gap can be attributed to a functional
point (missing case enumeration vs. missing functional point).
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERILATOR_COVERAGE = str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage')
METRIC = re.compile(r"^\s+(line|toggle|branch|expr|fsm_state|fsm_arc)\s+:\s+([0-9.]+)%\s+\(\s*([0-9]+)\s*/\s*([0-9]+)\)")
DAT_POINT = re.compile(r"C '(.*)' (\d+)\n?\Z")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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
    """Return {source: {'da': {line: hits}, 'branches': [...]}}."""
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
        if re.match(r"^(wire|reg|logic|input|output|inout|parameter|localparam)\b", text):
            start = index
            while index < len(source) and ";" not in source[index]:
                index += 1
            for line in range(start, min(index + 1, len(source))):
                marked.add(line + 1)
        elif text in ("end", "endmodule", "endcase", "endfunction", "endtask"):
            marked.add(index + 1)
        elif text == "":
            marked.add(index + 1)
        index += 1
    return marked


def enclosing_construct(source: list[str], line: int) -> tuple[str, int]:
    for index in range(min(line, len(source)) - 1, -1, -1):
        text = source[index].strip()
        if re.match(r"^(initial|always|function|task)\b", text):
            return text.split()[0], index + 1
    return "unknown", 0


def dat_points(dat: Path):
    for raw in dat.open("rb"):
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


def classify_toggle(row: dict) -> str:
    name = row["name"]
    if row["construct"] == "initial":
        return "initial_random_state"
    if name.startswith("io_"):
        return "public_port_bit"
    if "state" in name or "coh" in name or "tag" in name or "way" in name:
        return "state_or_tag_bit"
    if "data" in name or "mask" in name:
        return "data_or_mask_bit"
    if "valid" in name or "ready" in name or "resp" in name:
        return "handshake_bit"
    return "other_internal_bit"


def contiguous_blocks(rows: list[dict], limit: int = 400) -> list[dict]:
    blocks = []
    for row in rows:
        if blocks and row["file"] == blocks[-1]["file"] and row["line"] == blocks[-1]["end"] + 1:
            blocks[-1]["end"] = row["line"]
            blocks[-1]["lines"] += 1
        else:
            blocks.append(dict(file=row["file"], start=row["line"], end=row["line"], lines=1))
    return blocks[:limit]


def _audit_one(run: Path, dat: Path, info: Path, functional: dict) -> dict:
    metrics = summary(dat)
    tables = parse_info(info)
    sources = {}
    for source in tables:
        path = Path(source)
        sources[source] = path.read_text().splitlines() if path.is_file() else []

    def role(path: str) -> str:
        name = Path(path).name
        if name.endswith(("_top.sv", "_top.v", "Dut_top.sv")):
            return "picker_harness"
        return "dut"

    per_file = {}
    overall = dict(unique_lines=0, covered_lines=0, uncovered=0, procedural_uncovered=0)
    dut_overall = dict(unique_lines=0, covered_lines=0, uncovered=0, procedural_uncovered=0)
    all_uncovered_procedural = []
    all_uncovered_declarative = []
    for source, table in tables.items():
        text = sources[source]
        da = table["da"]
        declarative = declaration_lines(text)
        uncovered = sorted(line for line, hits in da.items() if not hits)
        procedural = [line for line in uncovered if line not in declarative]
        decl = [line for line in uncovered if line in declarative]
        declarative_in_da = [line for line in da if line in declarative]
        covered = sum(1 for hits in da.values() if hits)
        per_file[source] = dict(
            role=role(source),
            unique_lines=len(da), covered_lines=covered,
            coverage_percent=round(100.0 * covered / len(da), 4) if da else 0.0,
            uncovered=len(uncovered),
            uncovered_procedural=len(procedural),
            uncovered_declarative=len(decl),
            procedural_lines=len(da) - len(declarative_in_da),
            procedural_covered=covered - sum(1 for line in declarative_in_da if da[line]),
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
        if role(source) == "dut":
            dut_overall["unique_lines"] += len(da)
            dut_overall["covered_lines"] += covered
            dut_overall["uncovered"] += len(uncovered)
            dut_overall["procedural_uncovered"] += len(procedural)
            all_uncovered_procedural.extend(
                dict(file=source, line=line, source=text[line - 1].strip())
                for line in procedural if 0 < line <= len(text)
            )
        all_uncovered_declarative.extend(
            dict(file=source, line=line, source=text[line - 1].strip())
            for line in decl if 0 < line <= len(text)
        )
    overall["coverage_percent"] = round(
        100.0 * overall["covered_lines"] / overall["unique_lines"], 4
    ) if overall["unique_lines"] else 0.0
    dut_overall["coverage_percent"] = round(
        100.0 * dut_overall["covered_lines"] / dut_overall["unique_lines"], 4
    ) if dut_overall["unique_lines"] else 0.0

    branch_uncovered = []
    branch_total = 0
    for source, table in tables.items():
        text = sources[source]
        for row in table["branches"]:
            branch_total += 1
            if row["taken"] not in ("0", "-", ""):
                continue
            construct, at = enclosing_construct(text, row["line"])
            branch_uncovered.append(dict(
                file=source, line=row["line"], branch=row["branch"],
                construct=construct, construct_line=at,
                source=text[row["line"] - 1].strip() if 0 < row["line"] <= len(text) else "",
            ))

    toggle_total = toggle_hit = 0
    toggle_dut_total = toggle_dut_hit = 0
    toggle_zero = []
    toggle_dut_zero = []
    for point in dat_points(dat):
        if point["kind"] != "toggle":
            continue
        toggle_total += 1
        if point["count"]:
            toggle_hit += 1
        text = sources.get(point["file"], [])
        construct, at = enclosing_construct(text, point["line"])
        row = dict(name=point["name"], file=point["file"], line=point["line"],
                   construct=construct, construct_line=at)
        row["class"] = classify_toggle(row)
        if point["count"]:
            if role(point["file"]) == "dut":
                toggle_dut_hit += 1
            continue
        if role(point["file"]) == "dut":
            toggle_dut_total += 1
            toggle_dut_zero.append(row)
        else:
            toggle_dut_total += 1
        toggle_zero.append(row)
    # Count DUT-only denominators separately (declared harness points excluded).
    for point in dat_points(dat):
        if point["kind"] == "toggle" and role(point["file"]) == "dut" and point["count"]:
            pass
    toggle_dut_total = sum(1 for point in dat_points(dat)
                           if point["kind"] == "toggle" and role(point["file"]) == "dut")
    toggle_dut_hit = toggle_dut_total - len(toggle_dut_zero)
    toggle_classes = Counter(row["class"] for row in toggle_zero)
    toggle_dut_classes = Counter(row["class"] for row in toggle_dut_zero)

    functional_groups = []
    for group in functional["groups"]:
        functional_groups.append({
            "instance": group["instance"],
            "coverage": group["coverage"],
            "samples": group["samples"],
            "points": [dict(name=point["name"], coverage=point["coverage"],
                            samples=point["samples"])
                       for point in group["points"]],
            "crosses": [dict(name=cross["name"], coverage=cross["coverage"])
                        for cross in group["crosses"]],
        })

    result = {
        "format": "dcache-coverage-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": str(run.relative_to(ROOT)),
        "coverage_dat_sha256": digest(dat),
        "coverage_info_sha256": digest(info),
        "source_files": {source: dict(sha256=digest(Path(source)), lines=len(sources[source]))
                         for source in sources if Path(source).is_file()},
        "verilator_point_metrics": metrics,
        "lcov_lines": overall,
        "lcov_lines_dut_only": dut_overall,
        "lcov_lines_per_file": per_file,
        "uncovered_blocks": contiguous_blocks(all_uncovered_procedural),
        "uncovered_procedural_lines": all_uncovered_procedural,
        "uncovered_declarative_lines": all_uncovered_declarative,
        "branches": {
            "total": branch_total,
            "covered": branch_total - len(branch_uncovered),
            "uncovered": branch_uncovered,
        },
        "toggles": {
            "total": toggle_total,
            "covered": toggle_hit,
            "uncovered": len(toggle_zero),
            "classes": dict(toggle_classes),
            "uncovered_points": toggle_zero,
        },
        "toggles_dut_only": {
            "total": toggle_dut_total,
            "covered": toggle_dut_hit,
            "uncovered": len(toggle_dut_zero),
            "coverage_percent": round(100.0 * toggle_dut_hit / toggle_dut_total, 4)
            if toggle_dut_total else 0.0,
            "classes": dict(toggle_dut_classes),
            "uncovered_points": toggle_dut_zero,
        },
        "functional_coverage": {
            "coverage": functional["coverage"],
            "covered": functional["covered"],
            "groups": functional_groups,
        },
        "limits": (
            "Verilator point summaries are not semantic checks. LCOV DA hits are summed per "
            "line (duplicate shadow points included) and every denominator is retained. "
            "Declarative wire/reg/end lines are separated by source text, not deleted; "
            "procedural lines are still listed if uncovered. Files are kept separate so a "
            "parent DUT does not hide a child's own gaps. Toggle points are raw RTL nets; "
            "unreachable reset-only or tie-off nets are reported, not filtered."
        ),
    }
    return result


def audit(run: Path, report_name: str) -> dict:
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    functional_path = run / "functional-coverage.json"
    functional = json.loads(functional_path.read_text()) if functional_path.is_file() else {
        "coverage": 0.0, "covered": False, "groups": []}
    builds = []
    for dat in sorted(run.glob("native/*/coverage.dat")):
        info = dat.with_suffix(".info")
        if not info.is_file():
            raise FileNotFoundError(f"missing LCOV export for {dat}")
        builds.append(_audit_one(run, dat, info, functional))
    if not builds:
        raise FileNotFoundError(f"no native coverage database under {run}")
    if len(builds) == 1:
        result = builds[0]
    else:
        result = {
            "format": "dcache-coverage-audit-multi-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run": str(run.relative_to(ROOT)),
            "build_count": len(builds),
            "functional_coverage": builds[0]["functional_coverage"],
            "builds": builds,
            "limits": (
                "Each Picker build keeps its own native numerator/denominator; a combined run "
                "must not sum lines across DUTs. Functional coverage is merged by the runner."
            ),
        }
    output = run / report_name
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def markdown(result: dict) -> str:
    if "builds" in result:
        lines = [f"# 覆盖率审计（多 DUT 运行）：{result['run']}", "",
                 f"- 原生构建数：{result['build_count']}",
                 f"- 功能覆盖：{result['functional_coverage']['coverage']:.2f}%", ""]
        for build in result["builds"]:
            name = Path(build["builds"][0]).name if "builds" in build else "build"
            lines.append(f"## {Path(next(iter(build['source_files']))).parent.name}")
            lines.append("")
            lines.append(markdown(build))
            lines.append("")
        return "\n".join(lines)
    lines = [
        f"# 覆盖率审计：{result['run']}",
        "",
        f"- 覆盖率数据 SHA-256：`{result['coverage_dat_sha256']}`",
        "",
        "## Verilator 原生点统计（含工具影子点，不删减）",
        "",
        "| 类型 | 命中 / 总数 | 百分比 |",
        "|---|---:|---:|",
    ]
    for kind, row in result["verilator_point_metrics"]["metrics"].items():
        lines.append(f"| {kind} | {row['hit']} / {row['total']} | {row['percent']:.2f}% |")
    lcov = result["lcov_lines"]
    lines += [
        "",
        "## LCOV 逐行（重复点按行求和，保留全部分母）",
        "",
        f"- 唯一 DA 行：{lcov['unique_lines']}",
        f"- 命中行：{lcov['covered_lines']}（{lcov['coverage_percent']:.2f}%）",
        f"- 未命中：{lcov['uncovered']}，其中过程语句行 {lcov['procedural_uncovered']}",
        f"- DUT-only（排除 Picker harness）：{result['lcov_lines_dut_only']['covered_lines']}"
        f" / {result['lcov_lines_dut_only']['unique_lines']}"
        f"（{result['lcov_lines_dut_only']['coverage_percent']:.2f}%），"
        f"过程语句未覆盖 {result['lcov_lines_dut_only']['procedural_uncovered']}",
        "",
        "| 源文件 | 行命中 / 唯一行 | 过程语句未覆盖 |",
        "|---|---:|---:|",
    ]
    for source, row in result["lcov_lines_per_file"].items():
        name = Path(source).name
        lines.append(
            f"| `{name}` ({row['role']}) | {row['covered_lines']} / {row['unique_lines']} "
            f"({row['coverage_percent']:.2f}%) | {row['uncovered_procedural']} |"
        )
    lines.append("")
    if result["uncovered_procedural_lines"]:
        lines += ["### 未覆盖过程语句行（必须逐项定位）", "", "| 文件:行 | 源码 |", "|---|---|"]
        for row in result["uncovered_procedural_lines"][:400]:
            lines.append(f"| {Path(row['file']).name}:{row['line']} | `{row['source'][:110]}` |")
    else:
        lines.append("未命中行全部是声明/连续赋值/end 行；逐行清单见 JSON。")
    lines += ["", "### 未覆盖连续块", ""]
    for block in result["uncovered_blocks"][:80]:
        lines.append(f"- {Path(block['file']).name}:{block['start']}-{block['end']}（{block['lines']} 行）")
    lines += ["", "## 分支", "", f"- 覆盖 {result['branches']['covered']} / {result['branches']['total']}"]
    for row in result["branches"]["uncovered"][:200]:
        lines.append(
            f"- {Path(row['file']).name}:{row['line']} `{row['branch']}` in "
            f"`{row['construct']}`：`{row['source'][:90]}`"
        )
    if len(result["branches"]["uncovered"]) > 200:
        lines.append(f"- 其余 {len(result['branches']['uncovered']) - 200} 项见 JSON。")
    lines += ["", "## Toggle", "", f"- 覆盖 {result['toggles']['covered']} / {result['toggles']['total']}",
              "- 未覆盖按类："]
    for cls, count in sorted(result["toggles"]["classes"].items()):
        lines.append(f"  - `{cls}`：{count}")
    lines += ["", "逐点信号名、文件与源行见 JSON 的 `toggles.uncovered_points`。", "", "## 功能覆盖", ""]
    for group in result["functional_coverage"]["groups"]:
        lines.append(f"- `{group['instance']}`：{group['coverage']:.2f}%（{group['samples']} samples）")
    lines += ["", result["limits"], ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="run directory under results/")
    parser.add_argument("--report", default="coverage-audit.json")
    args = parser.parse_args()
    run = ROOT / "results" / args.run
    result = audit(run, args.report)
    markdown_path = run / args.report.replace(".json", ".md")
    markdown_path.write_text(markdown(result))
    print(f"wrote {run / args.report} and {markdown_path}")


if __name__ == "__main__":
    main()
