"""Normal-transaction, read-only alternate-slot probe; not a pytest verdict.

Native details are intentionally confined to this diagnostic. Formal scenarios
must use an agent-owned bounded monitor, independent state expectations, coverage
bins and negative controls before treating these mux hits as functional closure.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import asyncio
from collections import deque
from dataclasses import asdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

from toffee import Bundle
from toffee import Execution
from toffee import Scoreboard
from toffee import XCommClockBackend

from bpuverify.tage.agent.main import TageAgent
from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.dut import initialize_dut_inputs
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names

ROOT = Path(__file__).resolve().parents[3]


async def prepare_table_two_alternate(agent, pc, direction):
    """Protect earlier residents, then allocate table3 above a real table2 hit."""
    target = None
    for position in range(16):
        cold = await agent.predict(pc, position, 1-direction, base_conf=1)
        assert cold.meta['hasProvider'] == 0
        await agent.train(TageTraining(pc, position, direction, 1-direction, cold.meta, 1))
        allocated = await agent.predict(pc, position, 1-direction, base_conf=1)
        assert allocated.meta['hasProvider'] == 1 and allocated.meta['hasAlt'] == 0
        table = allocated.meta['providerTableIdx']
        for _ in range(4):
            actual_prediction = allocated.taken if allocated.valid else 1-direction
            await agent.train(TageTraining(pc, position, direction, 1-direction,
                                          allocated.meta, int(actual_prediction != direction)))
            allocated = await agent.predict(pc, position, 1-direction, base_conf=1)
        assert allocated.meta['providerTakenCtr_value'] == (7 if direction else 0)
        assert allocated.meta['providerUsefulCtr_value'] == 3
        if table == 2:
            target = position
            break
    assert target is not None, 'normal allocations did not reach table2'
    await agent.train(TageTraining(pc, target, 1-direction, direction, allocated.meta, 1))
    result = await agent.predict(pc, target, direction, base_conf=1)
    assert result.meta['providerTableIdx'] == 3 and result.meta['hasAlt'] == 1, result
    assert result.meta['providerTakenCtr_value'] == (3 if direction else 4), result
    assert result.meta['providerUsefulCtr_value'] == 0, result
    return target, result


async def probe(args):
    report_path = args.report.resolve()
    protected = tuple(ROOT/'results'/name for name in (
        'feature-points.json', 'rtl-coverage-manifest.json',
        'rtl-line-coverage.json', 'verification-report.html'))
    if report_path in protected:
        raise ValueError('diagnostic output cannot overwrite a formal report')
    before = {str(path): sha256(path.read_bytes()).hexdigest()
              for path in protected if path.is_file()}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    raw = report_path.with_name('probe-'+report_path.stem+'-coverage.dat')
    package = args.dut_package.resolve()
    spec = importlib.util.spec_from_file_location(
        'tage_alternate_slot_diagnostic', package/'__init__.py',
        submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    cls = next(value for key, value in vars(module).items() if key.startswith('DUT'))
    dut = cls(module.xsp.StringVector(['tage', ucv_paths.native_seed()]), coverage_filename=str(raw))
    checks = Scoreboard('tage.alternate_slot_diagnostic')
    captured, rows = deque(maxlen=6), []
    try:
        dut.InitClock('clock')
        initialize_dut_inputs(dut)
        names = memory_signal_names(dut)
        suffixes = ('alt_takenCtr_value', 'alt_1_takenCtr_value', 'alt_2_takenCtr_value',
                    'alt_3_takenCtr_value', '_alt_T_11', '_alt_T_20')
        found = {suffix: tuple(name for name in names if name.endswith('.Tage.'+suffix))
                 for suffix in suffixes}
        if any(len(matches) != 1 for matches in found.values()):
            raise RuntimeError(f'alternate probe needs exact memory-direct bindings: {found}')
        # Bundle field names may not begin with an underscore.
        signals = {'observed_'+suffix: memory_signal(dut, matches[0].split('.', 1)[1])
                   for suffix, matches in found.items()}
        async with Execution(XCommClockBackend(dut.GetXClock()), max_batch_ticks=256) as execution:
            agent = await TageAgent(dut).start(execution)
            monitor = CycleMonitor(
                PortBinding(dut.clock, Bundle(**signals), 'tage.alternate_readonly'),
                decoder=lambda sample: {key: getattr(sample, key).as_int() for key in signals})
            monitor.start(execution, observer=lambda observation: captured.append(
                {'tick': observation.event.tick, 'value': observation.value}))
            try:
                for direction in (0, 1):
                    await agent.reset()
                    position, reference = await prepare_table_two_alternate(agent, args.pc, direction)
                    resident_keys = ('hasProvider', 'hasAlt', 'providerTableIdx',
                                     'providerWayIdx', 'providerTakenCtr_value', 'providerUsefulCtr_value')
                    expected_resident = {key: reference.meta[key] for key in resident_keys}
                    for slot in range(4):
                        for base_conf in (0, 1):
                            branches = (None,)*slot + (TageBaseBranch(position, 1-direction, base_conf),)
                            result = await agent.predict_branches(args.pc, branches)
                            meta = result.metas[slot]
                            internal = captured[-1]['value']
                            suffix = f'alt_{slot}_takenCtr_value' if slot else 'alt_takenCtr_value'
                            expected = {'resident': expected_resident,
                                        'output': (1, direction, 0, 1, direction),
                                        'alternate_counter': 6 if direction else 1}
                            actual = {'resident': {key: meta[key] for key in resident_keys},
                                      'output': (result.valids[slot], result.takens[slot], meta['useProvider'],
                                                 meta['altConf'], meta['altOrBasePred']),
                                      'alternate_counter': internal['observed_'+suffix]}
                            if slot in (1, 2):
                                expected['table2_selected'] = 1
                                actual['table2_selected'] = internal[f'observed__alt_T_{11 if slot == 1 else 20}']
                            checks.check(expected=expected, actual=actual)
                            rows.append({'direction': direction, 'prediction_slot': slot,
                                         'base_conf': base_conf, 'meta': meta,
                                         'valid': result.valids[slot], 'taken': result.takens[slot],
                                         'internal_tail': list(captured)})
            finally:
                await monitor.aclose()
                await agent.aclose()
    finally:
        dut.Finish()
    assert before == {str(path): sha256(path.read_bytes()).hexdigest() for path in protected if path.is_file()}
    report = {'format': 'bpu-tage-alternate-slots-readonly-probe', 'version': 1,
              'scope': 'normal transactions and read-only memory-direct, not formal pytest or functional coverage',
              'probe_script': str(Path(__file__).resolve()),
              'probe_script_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'dut_package': str(package), 'seed': 1, 'pc': args.pc,
              'internal_capability': found, 'readonly_internal_bindings': list(signals),
              'observations': rows, 'checks': asdict(checks.status), 'raw_file': str(raw),
              'formal_reports_preserved_byte_for_byte': True, 'protected_sha256': before}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(rows)} alternate-slot cases checked; formal reports preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dut-package', type=Path, default=ROOT/'dut/tage')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--pc', type=lambda value: int(value, 0), default=0x40000000)
    asyncio.run(probe(parser.parse_args()))
