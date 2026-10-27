"""Integrated directory capacity and pointer redecoding through genuine feedback."""
from copy import deepcopy
import json
from toffee import CheckContext, Scoreboard, ScoreboardMode
from bpuverify.bpu.checker.ittage import check_metadata
from bpuverify.bpu.checker.ittage_region import DirectoryPhrChecks, RegionChecker
from bpuverify.bpu.coverage.ittage import DirectoryCoverage
from bpuverify.bpu.env.bypass.program import ProgramEnvironment
from bpuverify.bpu.model.ittage import IttageContextModel
from bpuverify.bpu.model.ittage_region import directory_program
from bpuverify.bpu.monitor.ittage_region import RegionMonitor
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback

async def check_directory(agent, output):
    plan = directory_program()
    phr = DirectoryPhrChecks(scope='real region capacity, reuse and pointer replacement')
    coverage = DirectoryCoverage()
    regions, monitor = RegionChecker(coverage), RegionMonitor(agent)
    board, residents, observed = Scoreboard('bpu.ittage_region_residents'), [], []
    async with agent.observe_phr(phr) as observation:
        env = ProgramEnvironment(agent, phr, observation, {})

        async def stop():
            await env.wait(agent.set_ready(prediction=False, meta=True), 'stop younger region work', 8)
            await env.wait(observation.drain(), 'drain accepted region work', 256)
            regions.raise_failure()

        async def capture(row):
            await stop()
            await env.wait(agent.set_ready(prediction=True, meta=True), 'region context capture', 8)
            actual = await env.capture(row, 'genuine region context')
            regions.raise_failure()
            meta = actual.meta.resolve['phr']
            # This expected physical history was advanced from public input by
            # the full PHR checker, not seeded from an observed history dump.
            history = (phr.reference.physical_read(meta['phrPtr']) & ~8191) | meta['phrLowBits']
            board.check(expected=0, actual=history, context=CheckContext(board.name, ScoreboardMode.DIRECT,
                sequence_id=actual.meta_tick, request=dict(point='planned zero-history region key', pc=row['pc'])))
            return actual

        async def check_residents():
            for resident in reversed(residents):
                actual = await capture(resident['input'])
                regions.check_consumer(resident, actual, phr, board)

        monitor.start(regions)
        try:
            await env.bootstrap(tuple(dict(pc=row['pc']) for row in plan))
            await env.wait(agent.configure_predictors(ittage=True, settle=True), 'enable real target provider', 32)
            for row in plan:
                model, actual = IttageContextModel(), await capture(row)
                check_metadata(board, model, actual, phase='cold-region-context')
                board.check(expected=1, actual=actual.meta.resolve['ittage']['allocate']['valid'])
                target = row['target']
                pointer, offset = None, target & ((1 << 19) - 1)
                if target >> 19 != row['pc'] >> 19:
                    predicted = deepcopy(regions.model).allocate(target << 1)
                    pointer = predicted.pointer
                    observed.append(dict(role=row['role'], pointer=pointer, reused=predicted.reused,
                        evicted_region=predicted.evicted_region, region=target >> 19))
                feedback = BpuBatchTraining(row['pc'], actual.meta.resolve,
                    (BpuBranchFeedback(row['position'], target, 3, taken=1, mispredict=1),))
                model.advance(actual.meta.resolve['ittage']['allocate'], target, mispredict=True)
                regions.plan_feedback(feedback, actual)
                await env.wait(agent.train_batch_with_prediction_pause(feedback), 'genuine region allocation feedback', 256)
                residents.append(dict(input=row, model=model, pointer=pointer, offset=offset))
                await check_residents()
            await stop()
            summary = regions.summary()
            phr.summary()
            fills = [row for row in observed if row['role'] == 'fill']
            board.check(expected=list(range(16)), actual=[row['pointer'] for row in fills])
            board.check(expected=True, actual=all(not row['reused'] and row['evicted_region'] is None for row in fills))
            reuse = next(row for row in observed if row['role'] == 'reuse')
            board.check(expected=(True, None), actual=(reuse['reused'], reuse['evicted_region']))
            partial = next(row for row in observed if row['role'] == 'reuse-partial')
            board.check(expected=(3, True, None), actual=(partial['pointer'], partial['reused'], partial['evicted_region']))
            replacements = [row for row in observed if row['role'].startswith('replace-')]
            board.check(expected=True, actual=all(not row['reused'] and row['evicted_region'] is not None for row in replacements))
            board.check(expected=2, actual=len({row['pointer'] for row in replacements}))
            board.check(expected=20, actual=len(summary['writes']))
            coverage.require()
            result = dict(passed=True, contexts=len(residents), observed_allocations=observed,
                directory_checks=summary, public_checks=board.status.checked,
                full_FTQ_legality_proven=False, full_prediction_hash_or_SRAM_reference_claimed=False)
            (output / 'ittage-region-directory-summary.json').write_text(json.dumps(result, indent=2) + '\n')
            return result
        except BaseException as error:
            (output / 'ittage-region-directory-failure.json').write_text(json.dumps(dict(
                failure=repr(error), completed_contexts=len(residents), current_input=row if 'row' in locals() else None,
                region_observation=regions.diagnostics()), indent=2) + '\n')
            raise
        finally:
            await monitor.aclose()
            coverage.write(output)
