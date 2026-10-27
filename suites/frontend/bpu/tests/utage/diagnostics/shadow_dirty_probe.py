"""Read-only memory-direct diagnostic; excluded from formal RTL coverage.

Build unchanged MicroTage with picker --rw mem_direct and trace enabled,
then run this script with --dut-package pointing at that package. Functional
regressions intentionally rely on public transactions, not these registers.
"""

from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

from toffee import Bundle
from toffee import Execution
from toffee import XCommClockBackend

from bpuverify.utage.agent.main import UtageAgent
from bpuverify.utage.coverage.catalog import utage_shadow_persistence_coverage_model
from bpuverify.utage.coverage.catalog import utage_shadow_ring_coverage_model
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.dut import initialize_dut_inputs
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from bpuverify.utage.case.shadow_ring_scenario import check_shadow_eviction
from bpuverify.utage.case.shadow_ring_scenario import check_shadow_ring_mode


async def probe(args):
    package = args.dut_package.resolve()
    spec = importlib.util.spec_from_file_location(
        "utage_memory_diagnostic", package / "__init__.py", submodule_search_locations=[str(package)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    cls = next(value for key, value in vars(module).items() if key.startswith("DUT"))
    dut = cls(module.xsp.StringVector(["utage", ucv_paths.native_seed()]),
              coverage_filename=str(args.report.with_suffix(".dat")))
    try:
        dut.InitClock("clock")
        initialize_dut_inputs(dut)
        names = memory_signal_names(dut)
        suffix = "" if args.table == 0 else "_1"
        ending = f"MicroTageTable{suffix}.wbuffer.enqPtr_value"
        matches = [name for name in names if name.endswith(ending)]
        assert len(matches) == 1, matches
        # Strip only the synthetic TOP name, not the native model hierarchy.
        prefix = matches[0].split(".", 1)[1].removesuffix("enqPtr_value")
        signals = {
            key: memory_signal(dut, prefix + name)
            for key, name in {
                "enq": "enqPtr_value", "clean": "t1_cleanId", "has_hit": "t1_hasHit",
                "has_write": "bypassHit", "train_index": "t1_trainIndex",
                **{f"dirty_{slot}": f"statusEntries_{slot}_dirty" for slot in range(8)},
                **{f"index_{slot}": f"entries_{slot}_index" for slot in range(8)},
                **{f"counter_{slot}": f"entries_{slot}_entryData_bits_takenCtr_value" for slot in range(8)},
            }.items()
        }
        trace = []
        previous = None

        def observe(observation):
            nonlocal previous
            current = {key: value.as_int() for key, value in observation.value.items()}
            if (previous is not None and not previous["reset"] and not current["reset"]
                    and previous["has_write"] and previous["has_hit"]
                    and previous["clean"] == previous["enq"]):
                slot = previous["enq"]
                assert current["enq"] == (slot + 1) % 8, (previous, current)
                assert current[f"index_{slot}"] == previous["train_index"], (previous, current)
                assert current[f"dirty_{slot}"] == 0, (previous, current)
                trace.append({
                    "tick": observation.event.tick, "slot": slot,
                    "write_index": previous["train_index"], "clean_id": previous["clean"],
                    "old_counter": previous[f"counter_{slot}"], "new_counter": current[f"counter_{slot}"],
                    "old_dirty": previous[f"dirty_{slot}"], "new_dirty": current[f"dirty_{slot}"],
                    "has_write": previous["has_write"], "has_hit": previous["has_hit"],
                })
            previous = current

        async with Execution(XCommClockBackend(dut.GetXClock()), max_batch_ticks=256) as execution:
            agent = await UtageAgent(dut).start(execution)
            monitor = CycleMonitor(PortBinding(dut.clock, Bundle(reset=dut.reset, **signals), "utage.shadow_debug"))
            monitor.start(execution, observer=observe)
            try:
                adjacent = args.mode == "adjacent"
                run = await check_shadow_ring_mode(agent, utage_shadow_ring_coverage_model(),
                                                   table=args.table, bank=0, adjacent=adjacent)
                states, mismatches = await check_shadow_eviction(
                    agent, utage_shadow_persistence_coverage_model(), run,
                    table=args.table, bank=0, adjacent=adjacent,
                )
                assert trace, "No same-slot clean/enqueue collision was observed"
                result = {
                    "format": "microtage-shadow-dirty-diagnostic", "table": args.table, "mode": args.mode,
                    "seed": 1, "dut_package": str(package), "internal_prefix": prefix,
                    "same_slot_collisions": trace, "after_counters": [state[-1] for state in states],
                    "persistence_mismatches": mismatches,
                }
                args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print(json.dumps({"table": args.table, "mode": args.mode, "collisions": len(trace),
                                  "after_counters": result["after_counters"], "first_collision": trace[0]}))
            finally:
                await monitor.aclose()
                await agent.aclose()
    finally:
        dut.Finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dut-package", type=Path, required=True)
    parser.add_argument("--table", type=int, choices=(0, 1), default=0)
    parser.add_argument("--mode", choices=("adjacent", "serial"), default="adjacent")
    parser.add_argument("--report", type=Path, required=True)
    asyncio.run(probe(parser.parse_args()))
