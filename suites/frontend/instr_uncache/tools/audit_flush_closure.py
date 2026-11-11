#!/usr/bin/env python3
"""Record or verify the structural evidence that DefaultConfig prunes flush.

The unit cannot drive ``InstrUncacheEntry.io.flush``: the only instantiation
ties it to ``false.B`` before elaboration, so firtool removes the port and the
``needFlush`` register.  This tool makes that claim reproducible and auditable:

* the Scala lines that tie and use the signal;
* the active generated closure (file hashes and port lists);
* the full-chip ``Frontend.sv`` instance, which has no flush connection;
* the generation cache identity.

``--write`` refreshes ``docs/spec/verification/evidence/flush-closure.json``.  The default check
mode fails if any recorded fact changed, which is the trigger to re-review the
classification instead of silently trusting an old conclusion.  The tool never
modifies RTL, Scala, generated files, baselines or tool locks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SUITE = __import__('suites.frontend.instr_uncache', fromlist=['ROOT']).ROOT
REPO = SUITE.parents[2]
os.environ.setdefault("UCV_ROOT", str(REPO))
sys.path.insert(0, str(REPO / "src"))

from ucv.config import Project  # noqa: E402
from ucv.runtime import soc_rtl, source_path  # noqa: E402

EVIDENCE = SUITE / "docs/spec/verification/evidence/flush-closure.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module_ports(path: Path) -> list[list[str]]:
    head = path.read_text(encoding="utf-8").split(");", 1)[0]
    ports = []
    for line in head.splitlines():
        match = re.match(r"\s*(input|output)\s+(?:\[[^\]]+\]\s+)?(\w+)\s*,?\s*$", line)
        if match:
            ports.append([match.group(1), match.group(2)])
    return ports


def line_at(path: Path, number: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if number > len(lines):
        raise ValueError(f"{path}: line {number} is past the end")
    return lines[number - 1].strip()


def scala_fact(path: Path, number: int) -> dict:
    return {"file": path.name, "line": number, "text": line_at(path, number)}


def frontend_instance(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((index for index, line in enumerate(lines)
                  if re.match(r"\s*InstrUncache\s+\w+\s*\(\s*$", line)), None)
    if start is None:
        raise ValueError(f"{path}: no InstrUncache instance found")
    end = next(index for index in range(start, len(lines))
               if lines[index].strip() == ");")
    block = "\n".join(lines[start:end + 1])
    name = re.match(r"\s*InstrUncache\s+(\w+)\s*\(", lines[start]).group(1)
    return {
        "file": path.name,
        "instance": name,
        "line": start + 1,
        "block_sha256": hashlib.sha256(block.encode()).hexdigest(),
        "has_flush_connection": ".io_flush" in block,
    }


def sim_frontend_fact(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    index = next(index for index, line in enumerate(lines)
                 if "instrUncache.io <> WireDefault(0.U.asTypeOf(instrUncache.io))" in line)
    return {"file": path.name, "line": index + 1, "text": lines[index].strip()}


def facts() -> dict:
    project = Project(REPO)
    baseline = project.baseline(project.config["baseline"])
    generated = soc_rtl()
    source = source_path()
    generation = json.loads((generated.parent / "generation.json").read_text(encoding="utf-8"))

    frontend_scala = source / "src/main/scala/xiangshan/frontend/Frontend.scala"
    imp_scala = source / "src/main/scala/xiangshan/frontend/instruncache/InstrUncacheImp.scala"
    entry_scala = source / "src/main/scala/xiangshan/frontend/instruncache/InstrUncacheEntry.scala"
    parameters_scala = source / "src/main/scala/xiangshan/Parameters.scala"
    sim_scala = source / "src/main/scala/xiangshan/frontend/simfrontend/SimFrontend.scala"

    top_rtl = SUITE / "rtl/instr_uncache/InstrUncache.sv"
    entry_rtl = SUITE / "rtl/instr_uncache/InstrUncacheEntry.sv"
    arbiter_rtl = SUITE / "rtl/instr_uncache/Arbiter1_InstrUncacheResp.sv"
    frontend_rtl = generated / "Frontend.sv"

    top_text = top_rtl.read_text(encoding="utf-8")
    entry_text = entry_rtl.read_text(encoding="utf-8")
    command = generation["command"]
    has_default_config = any(
        left == "--config" and right == "DefaultConfig"
        for left, right in zip(command, command[1:]))
    return {
        "format": "instr-uncache-flush-closure",
        "version": 1,
        "scope": {
            "suite": "instr_uncache",
            "baseline": baseline["name"],
            "commit": baseline["commit"],
            "design": baseline["design"]["config"],
            "conclusion": "DefaultConfig 下 flush 恒为 0，Entry 的 flush/needFlush 取消路径不可达；"
                          "本证据只证明结构裁剪，不验证 flush 行为。",
        },
        "generation": {
            "cache_key": generated.parent.name,
            "source_cache": source.name,
            "command_has_default_config": has_default_config,
            "baseline_name": generation["spec"]["baseline"]["name"],
            "baseline_commit": generation["spec"]["baseline"]["commit"],
        },
        "scala": {
            "instantiation": scala_fact(frontend_scala, 125),
            "flush_tie": scala_fact(frontend_scala, 266),
            "imp_port": scala_fact(imp_scala, 35),
            "imp_entry_tie": scala_fact(imp_scala, 65),
            "entry_port": scala_fact(entry_scala, 41),
            "entry_register": scala_fact(entry_scala, 58),
            "entry_capture": scala_fact(entry_scala, 59),
            "entry_response_guard": scala_fact(entry_scala, 100),
            "entry_send_exit": scala_fact(entry_scala, 162),
            "enable_sim_frontend_default": scala_fact(parameters_scala, 632),
            "sim_frontend_tie": sim_frontend_fact(sim_scala),
        },
        "rtl": {
            "InstrUncache.sv": {
                "sha256": sha256(top_rtl),
                "port_count": len(module_ports(top_rtl)),
                "has_flush": "flush" in top_text,
                "has_needFlush": "needFlush" in top_text,
                "ports": module_ports(top_rtl),
            },
            "InstrUncacheEntry.sv": {
                "sha256": sha256(entry_rtl),
                "port_count": len(module_ports(entry_rtl)),
                "has_flush": "flush" in entry_text,
                "has_needFlush": "needFlush" in entry_text,
                "ports": module_ports(entry_rtl),
            },
            "Arbiter1_InstrUncacheResp.sv": {
                "sha256": sha256(arbiter_rtl),
                "port_count": len(module_ports(arbiter_rtl)),
            },
            "Frontend.sv": {
                "sha256": sha256(frontend_rtl),
                "instance": frontend_instance(frontend_rtl),
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="refresh docs/spec/verification/evidence/flush-closure.json")
    args = parser.parse_args(argv)
    current = facts()
    if args.write:
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"wrote {EVIDENCE}")
        return 0
    if not EVIDENCE.is_file():
        print(f"missing evidence file: {EVIDENCE}", file=sys.stderr)
        return 1
    recorded = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if current != recorded:
        print("flush closure evidence changed; re-review R-FLUSH and rewrite the file",
              file=sys.stderr)
        for key in ("scope", "generation", "scala", "rtl"):
            if current.get(key) != recorded.get(key):
                print(f"  differs: {key}", file=sys.stderr)
        return 1
    print(f"flush closure evidence matches: {EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
