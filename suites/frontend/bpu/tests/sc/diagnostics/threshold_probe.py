"""Read-only threshold diagnostic using real SC lookup/feedback transactions.

This is not a pytest item or formal functional verdict. No register is written,
and no metadata field is fabricated. Internal thresholds are passively observed
through Bundle/CycleMonitor to evaluate whether boundary stimuli are reachable.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import asyncio
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import sys

from toffee import Bundle
from toffee import Execution
from toffee import Scoreboard
from toffee import XCommClockBackend

from bpuverify.sc.agent.main import ScAgent
from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.transaction.types import ScBatchTraining
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.dut import initialize_dut_inputs
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names


# The current MinimalConfig: five SC tables, 13-bit threshold, four ways.
INITIAL, MINIMUM, MAXIMUM = 1130, 640, 5040
POSITIONS = (4, 5, 6, 7)


def update_thresholds(old, prediction, outcomes):
    """Reference for this probe's four valid conditional MainBTB-hit branches."""
    changes = [0] * 4
    meta = prediction.meta
    for slot, (position, taken) in enumerate(zip(POSITIONS, outcomes, strict=True)):
        valid = meta['tagePredValid'][slot]
        used, predicted = meta['useScPred'][slot], meta['scPred'][slot]
        eligible = valid and (
            not (used and predicted == taken)
            or not (used and valid and predicted == meta['tagePred'][slot])
        )
        wrong = taken != predicted
        if eligible and (wrong or not meta['sumAboveThres'][slot]):
            way = (position & 3) ^ (position >> 2)
            changes[way] += 1 if wrong else -1
    candidates = tuple(value + change for value, change in zip(old, changes, strict=True))
    next_values = tuple(new if MINIMUM <= new <= MAXIMUM else previous
                        for previous, new in zip(old, candidates, strict=True))
    rejected = tuple(i for i, (old_value, candidate, new_value) in enumerate(
        zip(old, candidates, next_values, strict=True))
        if candidate != old_value and new_value == old_value)
    return next_values, rejected


async def probe(args):
    package = args.dut_package.resolve()
    spec = importlib.util.spec_from_file_location(
        'sc_threshold_diagnostic', package/'__init__.py',
        submodule_search_locations=[str(package)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    cls = next(value for key, value in vars(module).items() if key.startswith('DUT'))
    dut = cls(module.xsp.StringVector(['sc', ucv_paths.native_seed()]),
              coverage_filename=str(args.report.with_suffix('.dat')))
    try:
        dut.InitClock('clock')
        initialize_dut_inputs(dut)
        names = memory_signal_names(dut)
        signals = []
        for way in range(4):
            matches = [name for name in names if name.endswith(f'.Sc.scThreshold_{way}_value')]
            assert len(matches) == 1, (way, matches)
            signals.append(memory_signal(dut, matches[0].split('.', 1)[1]))
        observed = None

        def observe(observation):
            nonlocal observed
            observed = observation.value

        phases = []
        async with Execution(XCommClockBackend(dut.GetXClock()), max_batch_ticks=256) as execution:
            agent = await ScAgent(dut).start(execution)
            monitor = CycleMonitor(
                PortBinding(dut.clock, Bundle(thresholds=tuple(signals)), 'sc.threshold_debug'),
                decoder=lambda sample: tuple(value.as_int() for value in sample.thresholds),
            )
            monitor.start(execution, observer=observe)
            checks = Scoreboard(name='sc.threshold_diagnostic')
            try:
                layout = tuple(ScBaseBranch(position, 7) for position in POSITIONS)
                selected = (('lower', MINIMUM, 800), ('upper', MAXIMUM, 3940))
                for phase, boundary, limit in selected:
                    if args.phase != 'both' and args.phase != phase:
                        continue
                    await agent.reset()
                    expected = (INITIAL,) * 4
                    checks.check(expected=expected, actual=observed)
                    rejected_counts = [0] * 4
                    boundary_round = None
                    examples = []
                    rows = set()
                    for step in range(1, limit + 1):
                        # Lower-bound correct feedback uses different real rows
                        # to avoid high-confidence suppression before the clamp.
                        # ScAgent currently preserves picker GuardedPc.addr:
                        # RTL bank selection is addr[0], not a fetch-block bit.
                        pc = 0x4000_0040 + (0x10 * (((step - 1) // 2) % 128)
                                          + (step - 1) % 2 if phase == 'lower' else 0)
                        prediction = await agent.predict_branches(pc, layout)
                        rows.add((pc & 1, prediction.meta['debug']['predBiasIdx']))
                        outcomes = tuple(int(value) if phase == 'lower' else 1 - int(value)
                                         for value in prediction.meta['scPred'])
                        expected, rejected = update_thresholds(expected, prediction, outcomes)
                        feedback = ScBatchTraining(pc, prediction.meta, tuple(
                            ScBranchFeedback(position, outcome, prediction_slot=slot)
                            for slot, (position, outcome) in enumerate(zip(POSITIONS, outcomes, strict=True))
                        ))
                        await agent.train_batch(feedback)
                        checks.check(expected=expected, actual=observed)
                        for way in rejected:
                            rejected_counts[way] += 1
                        if rejected and len(examples) < 4:
                            examples.append({'step': step, 'pc': pc, 'ways': rejected,
                                             'thresholds': observed,
                                             'scPred': prediction.meta['scPred'],
                                             'sumAboveThres': prediction.meta['sumAboveThres']})
                        if expected == (boundary,) * 4:
                            if boundary_round is None:
                                boundary_round = step
                            if all(count >= 4 for count in rejected_counts):
                                break
                    phases.append({'phase': phase, 'attempts': step,
                                   'boundary_round': boundary_round, 'final_thresholds': observed,
                                   'rejected_counts': rejected_counts, 'examples': examples,
                                   'distinct_bank_bias_rows': len(rows)})
                    print(json.dumps(phases[-1]), flush=True)
                result = {
                    'format': 'bpu-sc-threshold-readonly-diagnostic', 'version': 1,
                    'scope': 'real transactions with read-only memory-direct; not a formal pytest verdict',
                    'dut_package': str(package), 'seed': 1,
                    'probe_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                    'selected_phase': args.phase,
                    'pc_convention': 'existing ScAgent/picker GuardedPc.addr domain; addr[0] selects bank',
                    'minimum': MINIMUM, 'maximum': MAXIMUM, 'initial': INITIAL,
                    'metadata_fabricated': False, 'internal_writes': False,
                    'phases': phases,
                    'both_boundaries_reached': len(phases) == 2 and all(row['boundary_round'] is not None for row in phases),
                    'all_four_ways_clamped': all(all(n >= 4 for n in row['rejected_counts']) for row in phases),
                }
                args.report.write_text(json.dumps(result, indent=2) + '\n')
            finally:
                await monitor.aclose()
                await agent.aclose()
    finally:
        dut.Finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dut-package', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--phase', choices=('both', 'lower', 'upper'), default='both')
    asyncio.run(probe(parser.parse_args()))
