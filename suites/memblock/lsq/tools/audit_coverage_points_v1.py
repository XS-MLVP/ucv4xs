#!/usr/bin/env python3
"""Cross-check native Verilator coverage point records.

The default report is summary-only.  It proves that line/toggle/branch point
records carry source mapping and that an independent record parser reproduces
the locked ``verilator_coverage`` totals for every native build.  It keeps
per-build denominators and hashes of missing-point inventories, but does not
persist a full point/source list or any cycle trace.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERILATOR_COVERAGE = str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage')
SUMMARY_RE = re.compile(
    r"^\s+(line|toggle|branch|expr|fsm_state|fsm_arc)\s+:\s+"
    r"([0-9.]+)%\s+\(\s*([0-9]+)\s*/\s*([0-9]+)\)"
)
COUNT_RE = re.compile(rb"' (-?\d+)\s*$")
KINDS = ("line", "toggle", "branch")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def records(path: Path) -> list[dict]:
    result = []
    for raw in path.read_bytes().splitlines():
        if not raw.startswith(b"C '"):
            continue
        body = raw[3:]
        match = COUNT_RE.search(body)
        if not match:
            continue
        hit = int(match.group(1))
        fields = {}
        for part in body[: match.start()].split(b"\x01"):
            if len(part) >= 2 and part[1:2] == b"\x02":
                fields[part[:1].decode("ascii")] = part[2:].decode("utf-8", "replace")
        kind = fields.get("t")
        if kind not in KINDS:
            continue
        fields["hit"] = hit
        result.append(fields)
    return result


def point_key(point: dict) -> tuple:
    return tuple(point.get(key, "") for key in ("f", "l", "n", "t", "o", "S", "h"))


def digest_points(points: list[dict]) -> str:
    canonical = "\n".join(
        json.dumps(point_key(point), ensure_ascii=False, separators=(",", ":"))
        for point in sorted(points, key=point_key)
    ).encode()
    return sha256_bytes(canonical)


def analyzer_summary(path: Path) -> tuple[dict, str]:
    command = [VERILATOR_COVERAGE, "--report", "summary", str(path)]
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    metrics = {}
    for line in proc.stdout.splitlines():
        match = SUMMARY_RE.match(line)
        if match:
            kind, percent, hit, total = match.groups()
            metrics[kind] = dict(percent=float(percent), hit=int(hit), total=int(total))
    return metrics, proc.stdout


def summarize(path: Path, build: dict, artifact: dict) -> dict:
    parsed = records(path)
    analyzer, stdout = analyzer_summary(path)
    by_kind = {}
    all_fields_present = True
    for kind in KINDS:
        points = [point for point in parsed if point["t"] == kind]
        covered = [point for point in points if point["hit"] > 0]
        missing = [point for point in points if point["hit"] <= 0]
        fields_ok = all(all(key in point for key in ("f", "l", "h")) for point in points)
        all_fields_present &= fields_ok
        expected = analyzer.get(kind)
        assert expected is not None, (path, kind, stdout)
        actual = dict(hit=len(covered), total=len(points), percent=round(100 * len(covered) / len(points), 4) if points else 0.0)
        assert actual["hit"] == expected["hit"] and actual["total"] == expected["total"], (path, kind, actual, expected)
        by_kind[kind] = dict(
            hit=actual["hit"], total=actual["total"], percent=actual["percent"],
            uncovered=len(missing), source_mapping_fields_present=fields_ok,
            missing_point_inventory_SHA256=digest_points(missing),
        )
    assert all_fields_present
    return dict(
        build_id=build["build_id"], dut_export=build["name"],
        coverage_dat_SHA256=sha256_file(path),
        coverage_artifact_SHA256=artifact["sha256"],
        coverage_artifact_matches_dat=sha256_file(path) == artifact["sha256"],
        point_record_format="SystemC::Coverage-3 C record with f/l/n/t/o/[S]/h fields and trailing hit count",
        point_record_count=len(parsed), source_mapping_present=True,
        analyzer=" ".join([VERILATOR_COVERAGE, "--report", "summary", str(path)]),
        analyzer_stdout_SHA256=sha256_bytes(stdout.encode()),
        analyzer_stdout_bytes=len(stdout.encode()),
        raw_parser_matches_analyzer=True, metrics=by_kind,
    )


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    builds = []
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        path = Path(artifact["path"])
        assert path.name == "coverage.dat" and path.is_file()
        builds.append(summarize(path, artifact["build"], artifact))
    assert builds
    assert all(row["coverage_artifact_matches_dat"] for row in builds)
    assert all(row["raw_parser_matches_analyzer"] for row in builds)
    report = dict(
        format="lsq-verilator-coverage-points-v1", run=name, native_builds=len(builds),
        all_native_builds_have_source_mapped_line_toggle_branch=True,
        all_native_builds_parser_match_locked_analyzer=True,
        per_build_denominators_only=True, builds=builds,
        source="committed native coverage.dat; locked Verilator 5.052 summary cross-check",
        limits="This report proves point availability, source mapping fields, and per-build denominator integrity; it is not a functional or semantic PASS. Missing-point hashes are retained instead of a full point/source inventory under summary-only retention. Full line/toggle/branch gap classification and directed补例 remain separate work. No metric is merged across DUTs, leaves, historical runs, or result directories.",
    )
    output = run / "coverage-points-summary-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "builds"}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
