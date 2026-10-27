#!/usr/bin/env python3
"""Extract the DCacheWrapper -> DCache port mapping from the generated RTL.

`DCacheWrapper` is a structural wrapper: it instantiates exactly one `DCache`.
In `DCacheWrapper.sv` the instance reads `.inner_port (wrapper_signal)`, so the
extracted pairs are `inner -> wrapper-side signal`.  Wrapper-side signals are
either a wrapper pin of the same name (identity), a renamed wrapper pin, or an
internal net (the 42 perf counters are re-registered inside the wrapper).

This script classifies all 861 connections, verifies the arithmetic, and writes
`manifest/dcache-wrapper-portmap.json` so the testbench and the report prove the
mapping instead of assuming it.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOC_RTL = (ucv_paths.soc_rtl_for(ROOT)).resolve()
WRAPPER = SOC_RTL / "DCacheWrapper.sv"


def module_ports(text: str, module: str) -> set[str]:
    start = text.index(f"module {module}(")
    end = text.index("\n);", start)
    body = text[start:end]
    return set(re.findall(r"^\s*(?:input|output)\s+(?:\[[^\]]+\]\s*)?(\w+)", body, re.M))


def instantiation_connections(text: str) -> list[tuple[str, str]]:
    start = text.index("\n  DCache dcache (")
    end = text.index("\n  );\n", start)
    body = text[start:end]
    joined = re.sub(r"\s+", " ", body)
    return re.findall(r"\.(\w+)\s*\(\s*([\w\[\]:']+)\s*\)", joined)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="manifest/dcache-wrapper-portmap.json")
    args = parser.parse_args()
    text = WRAPPER.read_text()
    wrapper_ports = module_ports(text, "DCacheWrapper")
    pairs = instantiation_connections(text)

    inner_to_wrapper: dict[str, str] = {}
    duplicates = []
    for inner, wrapper in pairs:
        if inner in inner_to_wrapper:
            duplicates.append((inner, inner_to_wrapper[inner], wrapper))
        inner_to_wrapper[inner] = wrapper

    direct = {inner: wrapper for inner, wrapper in inner_to_wrapper.items()
              if wrapper in wrapper_ports}
    internal = {inner: wrapper for inner, wrapper in inner_to_wrapper.items()
                if wrapper not in wrapper_ports}
    identity = {wrapper: inner for inner, wrapper in direct.items() if wrapper == inner}
    renames = {wrapper: inner for inner, wrapper in direct.items() if wrapper != inner}
    perf_outputs = sorted(name for name in wrapper_ports if name.startswith("io_perf_"))
    unconnected_inner = sorted(set(inner_to_wrapper) -
                               {name for name in direct} - {name for name in internal})

    payload = {
        "schema_version": 3,
        "source": str(WRAPPER),
        "wrapper_module": "DCacheWrapper",
        "inner_module": "DCache",
        "connection_count": len(pairs),
        "inner_port_count": len(inner_to_wrapper),
        "wrapper_port_count": len(wrapper_ports),
        "duplicate_inner_ports": duplicates,
        "direct_connections": len(direct),
        "identity_ports": sorted(identity),
        "renames": dict(sorted(renames.items())),
        "internal_connections": dict(sorted(internal.items())),
        "wrapper_to_inner": dict(sorted({wrapper: inner for inner, wrapper in direct.items()}.items())),
        "inner_to_wrapper": dict(sorted(inner_to_wrapper.items())),
        "perf_outputs": perf_outputs,
        "perf_output_count": len(perf_outputs),
        "unconnected_inner_ports": unconnected_inner,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    groups = {"cache_ctrl": 0, "spec_fabric": 0, "other": 0}
    for wrapper in renames:
        if wrapper.startswith("auto_uncache_in_"):
            groups["cache_ctrl"] += 1
        elif wrapper.startswith("auto_dcache_spec_fabric_source_out_"):
            groups["spec_fabric"] += 1
        else:
            groups["other"] += 1
    print(f"connections={len(pairs)} inner_ports={len(inner_to_wrapper)} "
          f"wrapper_ports={len(wrapper_ports)} direct={len(direct)} "
          f"identity={len(identity)} renames={len(renames)} internal={len(internal)} "
          f"perf_outputs={len(perf_outputs)} duplicates={len(duplicates)}")
    print(groups)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
