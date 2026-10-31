"""Reproduce coverage phase errors without modifying RTL or formal reports.

This is a compiler diagnostic, not a BPU functional testcase. The C++ fixture
uses normal WriteBuffer ports; internal state is inspected read-only. Counters
are cleared only after preparation in the isolated model, never in formal DUTs.
"""
from __future__ import annotations
from suites.frontend.icache import ROOT as _SUITE_ROOT

import argparse
from datetime import datetime
from datetime import timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from suites.frontend.icache.coverage.rtl import POINT
from suites.frontend.icache.coverage.rtl import _metadata

ROOT = _SUITE_ROOT
MODES = ("single", "adjacent", "spaced", "retarget", "saturating")
POINTS = {
    "cross_row_counter": ("v_line", 1424, "elsif"),
    "provider_hit": ("v_branch", 1425, "if"),
    "saturation_hold": ("v_branch", 1426, "if"),
    "counter_step": ("v_branch", 1426, "else"),
    "cross_row_identity": ("v_line", 1535, "elsif"),
}


def expected_counts(mode: str, *, through: int | None = None) -> dict[str, int]:
    if mode not in MODES:
        raise ValueError(f"unknown diagnostic sequence: {mode}")
    if through not in (None, 0, 1) or mode == "single" and through == 1:
        raise ValueError(f"invalid diagnostic prefix: {mode}/{through}")
    updates = 1 if mode in {"single", "retarget"} or through == 0 else 2
    holds = int(mode == "saturating" and through != 0)
    return {
        "cross_row_counter": updates,
        "provider_hit": updates,
        "saturation_hold": holds,
        "counter_step": updates - holds,
        "cross_row_identity": updates,
    }


def read_counts(path: Path) -> dict[str, int]:
    counters = {}
    for record in path.read_text(encoding="utf-8").splitlines():
        match = POINT.match(record)
        if match is None:
            continue
        fields = _metadata(match[1])
        kind, _, module = fields.get("page", "").partition("/")
        if module != "WriteBuffer" or kind not in {"v_line", "v_branch"}:
            continue
        key = kind, int(fields["l"]), fields.get("o", "")
        if key in POINTS.values():
            if key in counters:
                raise ValueError(f"duplicate diagnostic coverage point: {key}")
            counters[key] = int(match[2])
    missing = set(POINTS.values()) - counters.keys()
    if missing:
        raise ValueError(f"missing diagnostic coverage points: {sorted(missing)}")
    return {name: counters[key] for name, key in POINTS.items()}


def audit(verilator: Path, directory: Path, *, optimize: bool = True) -> dict:
    env = os.environ.copy()
    # Let each binary select its own compiled-in installation, not an ambient
    # root referring to a different Verilator version.
    env.pop("VERILATOR_ROOT", None)
    version = subprocess.check_output([str(verilator), "--version"], env=env, text=True).strip()
    match = re.search(r"Verilator ([0-9]+)\.([0-9]+)", version)
    if match is None:
        raise ValueError(f"unrecognized Verilator version: {version}")
    model = directory / "model"
    command = [str(verilator), "-O3" if optimize else "-O0",
               "--cc", "--exe", "--build", "--coverage",
               "--public-flat-rw", "--Mdir", str(model), "--prefix", "VWriteBufferDebug",
               "--top-module", "WriteBuffer", "-Wno-fatal", "-j", "4"]
    if tuple(map(int, match.groups())) >= (5, 52):
        command.extend(("--no-coverage-expr", "--no-coverage-fsm"))
    if not optimize:
        command.extend(("-CFLAGS", "-DREPRO_NONINLINE"))
    command.extend((str(ROOT / "rtl/tage/WriteBuffer.sv"),
                    str(ROOT / "tools/coverage_phase_repro.cpp")))
    directory.mkdir(parents=True)
    with (directory / "build.log").open("w", encoding="utf-8") as output:
        subprocess.run(command, env=env, check=True, stdout=output, stderr=subprocess.STDOUT)
    cases = []
    for mode in MODES:
        data = directory / (mode + ".dat")
        observation = json.loads(subprocess.check_output(
            [str(model / "VWriteBufferDebug"), mode, str(data)], env=env, text=True
        ))
        expected = expected_counts(mode)
        actual = read_counts(data)
        prefixes = []
        for index in range(len(observation["updates"])):
            prefix_data = Path(str(data) + f".step-{index}")
            prefix_expected = expected_counts(mode, through=index)
            prefix_actual = read_counts(prefix_data)
            prefixes.append({"transfer": index, "expected": prefix_expected,
                             "actual": prefix_actual,
                             "correct": prefix_expected == prefix_actual,
                             "raw_file": str(prefix_data)})
        cases.append({"mode": mode, "observation": observation,
                      "expected": expected, "actual": actual,
                      "prefixes": prefixes,
                      "correct": expected == actual and all(p["correct"] for p in prefixes),
                      "raw_file": str(data)})
    return {"verilator": str(verilator), "version": version, "optimized": optimize,
            "command": command, "cases": cases,
            "correct": all(case["correct"] for case in cases)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verilator", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--o0-control", action="store_true")
    parser.add_argument("--expect-correct", action="store_true")
    args = parser.parse_args()
    work = args.workdir or Path(tempfile.mkdtemp(prefix="bpu-coverage-phase-"))
    source = ROOT / "rtl/tage/WriteBuffer.sv"
    lines = source.read_text(encoding="utf-8").splitlines()
    for number, prefix in {
        1424: "if (_GEN_66) begin", 1425: "if (hit) begin",
        1426: "if (_updateCnt_T_8)", 1535: "if (_GEN_66) begin",
    }.items():
        if not lines[number - 1].strip().startswith(prefix):
            raise ValueError(f"diagnostic source changed at {source}:{number}")
    source_hash = sha256(source.read_bytes()).hexdigest()
    runs = []
    for index, binary in enumerate(args.verilator):
        binary = binary.absolute()
        runs.append(audit(binary, work / f"verilator-{index}"))
        if args.o0_control:
            runs.append(audit(binary, work / f"verilator-{index}-o0", optimize=False))
    assert sha256(source.read_bytes()).hexdigest() == source_hash
    report = {
        "format": "bpu-coverage-phase-audit", "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source.relative_to(ROOT)), "source_sha256": source_hash,
        "scope": "isolated original WriteBuffer; no formal DUT/report mutation",
        "point_locations": {name: list(key) for name, key in POINTS.items()},
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for run in runs:
        print(run["version"], "optimized=" + str(run["optimized"]),
              "coverage_correct=" + str(run["correct"]))
    if args.expect_correct and not all(run["correct"] for run in runs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
