#!/usr/bin/env python3
"""Reconcile the integrated ICache's uncovered points with the module DUT runs.

For every line/branch/toggle point the integrated ICache leaves uncovered, ask
whether the same source point is covered by a byte-identical module DUT.  This
is a ledger, not a filter: the integrated denominator stays unchanged, and the
output keeps three categories separate:

* ``module``     - the same source point is hit by a module run;
* ``structural`` - unreachable or non-executable (dead priority-mux else,
  initial-block else, configuration-pruned logic), classified separately;
* ``open``       - neither; a genuine stimulus gap.

The structural classification is a small, explicit list of source patterns;
everything else that is not module-covered is reported as open.

Usage::

    python3 tools/coverage_ledger.py results/toffee-full-14
    python3 tools/coverage_ledger.py results/toffee-full-14 --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coverage_breakdown import classify

SEP = "\x01"

# Parent source -> file name in the module build (the module DUT's flattened
# top is a renamed copy; every other file keeps its name).
MODULE_FILE = {
    "ICacheWayLookup.sv": "WayLookupDut.v",
    "ICacheReplacer.sv": "ReplacerDut.v",
    "ICachePrefetchPipe.sv": "PrefetchPipeDut.v",
    "ICacheMainPipe.sv": "MainPipeDut.v",
    "ICacheMissUnit.sv": "MissUnitDut.v",
    "ICacheMshr.sv": "ICacheMshr.sv",
}

# Parent source -> module builds that contain the byte-identical file.
MODULE_FOR = {
    "ICacheWayLookup.sv": ("DUTWayLookupDut",),
    "ICacheReplacer.sv": ("DUTReplacerDut",),
    "ICachePrefetchPipe.sv": ("DUTPrefetchPipeDut",),
    "ICacheMainPipe.sv": ("DUTMainPipeDut",),
    "ICacheMissUnit.sv": ("DUTMissUnitDut",),
    "ICacheMetaInterleavedBank.sv": ("DUTMetaBankDut", "DUTMetaArrayDut"),
    "ICacheMetaInterleavedBank_1.sv": ("DUTMetaBankDut", "DUTMetaArrayDut"),
    "ICacheMetaArray.sv": ("DUTMetaArrayDut",),
    "ICacheDataArray.sv": ("DUTDataArrayDut",),
    "ICacheDataBank.sv": ("DUTDataBankDut", "DUTDataArrayDut"),
    "ICacheDataBank_1.sv": ("DUTDataArrayDut",),
    "SRAMTemplate.sv": ("DUTMetaBankDut", "DUTDataBankDut", "DUTMetaArrayDut"),
    "SplittedSRAMTemplate.sv": ("DUTMetaBankDut",),
    "FIFOReg.sv": ("DUTMissUnitDut",),
}
for index in range(1, 14):
    MODULE_FOR[f"ICacheMshr_{index}.sv"] = ("DUTMissUnitDut",)
for index in range(1, 8):
    MODULE_FOR[f"ICacheDataBank_{index}.sv"] = ("DUTDataArrayDut",)
    MODULE_FOR[f"MbistPipeICacheData_bank{index}.sv"] = ("DUTDataArrayDut",)
    MODULE_FOR[f"SRAMTemplate_{index}.sv"] = (
        "DUTDataBankDut", "DUTDataArrayDut", "DUTMetaBankDut", "DUTMetaArrayDut")
MODULE_FOR.update({
    "MbistPipeICacheData_bank0.sv": ("DUTDataBankDut", "DUTDataArrayDut"),
    "MbistPipeICacheTag_bank0.sv": ("DUTMetaBankDut", "DUTMetaArrayDut"),
    "MbistPipeICacheTag_bank1.sv": ("DUTMetaArrayDut",),
    "SRAMTemplate_16.sv": ("DUTMetaBankDut", "DUTMetaArrayDut"),
    "SRAMTemplate_32.sv": ("DUTMetaBankDut", "DUTMetaArrayDut"),
    "SRAMTemplate_8.sv": ("DUTMetaBankDut", "DUTMetaArrayDut"),
    "SRAMTemplate_4.sv": ("DUTDataBankDut", "DUTDataArrayDut"),
    "Queue1_RegMapperInput_5.sv": ("DUTMissUnitDut",),
})


def parse_dat(path: Path):
    for raw in path.open(errors="replace"):
        if not raw.startswith("C "):
            continue
        body = raw[3:]
        try:
            payload, count = body.rsplit("' ", 1)
            count = int(count.strip())
        except ValueError:
            continue
        fields: dict[str, str] = {}
        for segment in payload.split(SEP):
            if not segment:
                continue
            key, _, value = segment.partition("\x02")
            fields[key] = value
        yield count, fields


def load_run(run: Path) -> tuple[str, dict[str, dict]]:
    manifest = json.loads((run / "rtl-coverage-manifest.json").read_text())
    builds: dict[str, dict] = {}
    for native in manifest["native"]:
        points = defaultdict(int)
        for count, fields in parse_dat(Path(native["path"])):
            source = fields.get("f", "")
            if Path(source).stem.endswith("_top"):
                continue
            key = (Path(source).name, fields.get("l", ""), fields.get("n", ""),
                   fields.get("t", ""), fields.get("o", ""))
            points[key] += count
        builds[native["build"]["name"]] = {
            "dut": native.get("dut", ""),
            "points": dict(points),
        }
    parent = next(name for name, data in builds.items() if data["dut"] == "icache")
    return parent, builds


def structural(source: str, point: dict, lines: list[str]) -> bool:
    """Recognise the construction artefacts that cannot execute.

    The rules are deliberately narrow and each is tied to a source shape:

    * ``else`` of an exhaustive priority chain: the enclosing OR includes the
      final ``valid`` bit, so the last ``else`` cannot be taken;
    * ``else`` of ``if (reset)`` inside a ``_RANDOM`` initialization block;
    * arbitration arms for fetch MSHR 2/3, which this configuration never
      allocates (a fetch request touches at most two lines).
    """
    description = point["description"]
    line = point["line"]
    text = lines[line - 1].strip() if 0 < line <= len(lines) else ""
    if description == "else" and re.match(r"else if \(set_touch_ways_", text):
        return True
    if description == "else" and text.startswith("else if (entryUpdate_waySame"):
        return True
    if description == "else":
        window = "\n".join(lines[max(0, line - 25):line])
        if "RANDOMIZE_REG_INIT" in window or "`RANDOM" in window:
            return True
    if source == "Arbiter5_MshrAcquireBundle.sv" and (
            "io_in_2" in text or "io_in_3" in text):
        # The arbiter has four fetch-MSHR inputs and one prefetch input.
        # Fetch MSHRs 2/3 are never allocated: one accepted fetch references
        # at most two cache lines, and main-pipe s1 stalls until its miss
        # completes, so only MSHRs 0/1 can be valid.  Every arm guarded by
        # in_2/in_3 is therefore unreachable in this configuration.
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    parent_name, builds = load_run(args.run)
    parent_points = builds[parent_name]["points"]

    covered_cache: dict[tuple[str, str], set] = {}

    def covered_keys(build_name: str, module_file: str) -> set:
        key = (build_name, module_file)
        if key not in covered_cache:
            covered_cache[key] = {
                (line, column, kind, description)
                for (name, line, column, kind, description), count
                in builds[build_name]["points"].items()
                if name == module_file and count > 0
            }
        return covered_cache[key]

    line_cache: dict[str, list[str]] = {}
    ledger: dict[str, dict] = {}
    open_by_kind = Counter()
    module_by_kind = Counter()
    structural_by_kind = Counter()
    for (name, line, column, kind, description), count in sorted(parent_points.items()):
        if count != 0:
            continue
        candidates = MODULE_FOR.get(name, ())
        module_hit = False
        for build_name in candidates:
            module_file = MODULE_FILE.get(name, name)
            if (line, column, kind, description) in covered_keys(build_name, module_file):
                module_hit = True
                break
        entry = ledger.setdefault(name, {"uncovered": Counter(), "module": Counter(),
                                         "open": [], "structural": []})
        entry["uncovered"][kind] += 1
        if module_hit:
            entry["module"][kind] += 1
            module_by_kind[kind] += 1
            continue
        point = {"line": int(line) if str(line).isdigit() else line,
                 "column": column, "kind": kind, "description": description}
        if kind == "toggle":
            point["class"] = classify(name, description)
        # The parent source path is needed for the source text; recover it
        # from the first point key with this file name.
        if name not in line_cache:
            real = next(src for (src, *_rest) in parent_points if Path(src).name == name)
            path = Path(real)
            if not path.is_file():
                candidates = sorted(Path("rtl/icache").glob(name)) +\
                    sorted(Path("dut").glob(f"*/{name}"))
                path = candidates[0] if candidates else None
            line_cache[name] = (
                path.read_text(errors="replace").splitlines() if path else [])
        if structural(name, point, line_cache[name]):
            entry["structural"].append(point)
            structural_by_kind[kind] += 1
        else:
            entry["open"].append(point)
            open_by_kind[kind] += 1

    payload = {
        "run": str(args.run),
        "parent": parent_name,
        "ledger": {
            name: {
                "uncovered": dict(entry["uncovered"]),
                "module_covered": dict(entry["module"]),
                "structural": entry["structural"],
                "open": entry["open"],
            }
            for name, entry in ledger.items()
        },
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"parent: {parent_name}")
    print(f"uncovered: {dict(sum((Counter(e['uncovered']) for e in ledger.values()), Counter()))}")
    print(f"module-covered: {dict(module_by_kind)}")
    print(f"structural: {dict(structural_by_kind)}")
    print(f"open: {dict(open_by_kind)}")
    print()
    for name, entry in sorted(ledger.items(),
                              key=lambda item: -len(item[1]["open"])):
        if not entry["open"] and not entry["structural"]:
            continue
        print(f"{name}: uncovered {dict(entry['uncovered'])}")
        if entry["structural"]:
            kinds = Counter(p["kind"] for p in entry["structural"])
            print(f"  structural {dict(kinds)}")
        if entry["open"]:
            kinds = Counter(p["kind"] for p in entry["open"])
            print(f"  OPEN {dict(kinds)}")
            for point in entry["open"][:12]:
                print(f"    {point['kind']:7s} {point['line']:5} "
                      f"{point.get('class',''):7s} {point['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
