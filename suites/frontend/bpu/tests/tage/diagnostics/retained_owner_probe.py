"""Normal-driver retained-owner diagnostic, never collected as a formal test.

The metadata is genuinely captured before tag migration. Taken base prediction
prevents useful updates, isolating counter ownership from the known useful
misassociation defect. This is standalone evidence, not FTQ qualification.
"""
from suites.frontend.bpu.tage.case.retained_owner import check_case
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from toffee import CheckContext
from toffee import Execution
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import XCommClockBackend
from suites.frontend.bpu.tage.agent.main import TageAgent
from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.transaction.types import TageLookup
from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.runtime.dut import DutFactory
from suites.frontend.bpu.tage.driver.feedback import expected_tage_feedback
from suites.frontend.bpu.tage.driver.feedback import observed_tage_feedback
from suites.frontend.bpu.tage.model.shadow import advance_tage_shadow
from suites.frontend.bpu.tage.model.shadow import expected_tage_cross_owner_writes
from suites.frontend.bpu.tage.checker.assertions import fill_useful_set
from suites.frontend.bpu.tage.case.way_migration_scenario import cell
from suites.frontend.bpu.tage.case.way_migration_scenario import prepare_unprotected_highest_ways
from suites.frontend.bpu.tage.case.way_migration_scenario import protect
from suites.frontend.bpu.tage.case.way_migration_scenario import snapshot

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ('feature-points.json', 'rtl-coverage-manifest.json', 'rtl-line-coverage.json', 'verification-report.html')












async def run(arguments):
    stage = arguments.stage.resolve()
    if stage == ROOT or ROOT in stage.parents:
        raise ValueError('diagnostic stage must be outside the formal verification repository')
    stage.mkdir(parents=True, exist_ok=True)
    protected = {name:sha256((ROOT/'results'/name).read_bytes()).hexdigest() for name in REPORTS}
    raw = stage/'probe-retained-owner-coverage.dat'
    report = dict(format='bpu-tage-retained-owner-readonly', version=1, formal_credit=False,
        integrated_ftq_qualification_proven=False, strict_xfail_registered=False, raw_file=str(raw), cases=[])
    factory = DutFactory()
    try:
        dut = factory.create('tage', coverage_name=str(raw))
        async with Execution(XCommClockBackend(dut.GetXClock()), max_batch_ticks=256) as execution:
            agent = await TageAgent(dut).start(execution)
            try:
                for bank in arguments.banks:
                    for origin in arguments.origins:
                        for depth in arguments.depths:
                            for mode in arguments.modes:
                                result = await check_case(agent, bank=bank, origin=origin, depth=depth, mode=mode)
                                report['cases'].append(result)
                                print(f'PASS bank={bank} origin={origin} depth={depth} mode={mode}', flush=True)
            finally:
                await agent.aclose()
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        factory.close()
        assert protected == {name:sha256((ROOT/'results'/name).read_bytes()).hexdigest() for name in REPORTS}
        report.update(formal_reports_preserved_byte_for_byte=True, protected_sha256=protected,
            source_sha256={str(path.relative_to(ROOT)):sha256(path.read_bytes()).hexdigest() for path in (
                Path(__file__).resolve(), ROOT/'tage/agent/main.py', ROOT/'tage/model/shadow.py',
                ROOT/'tage/monitor/shadow.py', ROOT/'rtl/tage/WriteBuffer.sv')})
        (stage/'retained-owner-result.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--banks', type=int, nargs='+', choices=range(4), default=list(range(4)))
    parser.add_argument('--origins', type=int, nargs='+', choices=range(2), default=list(range(2)))
    parser.add_argument('--depths', type=int, nargs='+', choices=range(4), default=list(range(4)))
    parser.add_argument('--modes', nargs='+', choices=('pending', 'clean'), default=['pending', 'clean'])
    asyncio.run(run(parser.parse_args()))
