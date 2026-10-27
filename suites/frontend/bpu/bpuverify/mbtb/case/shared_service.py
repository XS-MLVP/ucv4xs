"""Semantic intent; agent owns the two launch protocols and passive monitors."""
from bpuverify.mbtb.env.shared_service import shared_service_program
from bpuverify.mbtb.checker.shared_service import Checks
from bpuverify.mbtb.case.resident_scenario import frozen_check


async def check_shared_service(agent,program,coverage,evidence):
    async with shared_service_program(agent,program) as prepared:
        checks=Checks(agent,program,prepared,evidence)
        evidence['source_captures']=prepared['source_captures']
        coverage.reach('genuine-owned-sources')
        async with agent.observe_entry_activity() as trace, agent.observe_entry_shadow() as shadows:
            try:await agent.train_with_first_multi_hit_cleanup(prepared['transaction'])
            finally:
                from bpuverify.mbtb.checker.shared_service import activities
                evidence.update(requests=activities(trace,'write'),services=activities(trace,'read'))
        try:checks.effects(trace,shadows,coverage)
        except Exception as primary:
            await checks.diagnose_consumer()
            try:checks.originals()
            except Exception as secondary:primary.add_note('original preservation: '+str(secondary))
            raise primary
        wanted=checks.wanted_consumers()
        for index in (0,1,1,0):
            pc=(prepared['first'].pc,prepared['neighbor'].pc)[index]
            await agent.submit_predict(pc,expected=frozen_check(wanted[index]))
        coverage.reach('fresh-survivor-and-neighbor')
        checks.originals();agent.reference.raise_failure()
        coverage.reach('originals-and-unrelated-preserved');coverage.finish()
        evidence.update(checks=checks.board.status.checked,reference_checks=agent.reference.board.status.checked,
            reference_failures=agent.reference.board.status.failed,original_metadata_unchanged=True)
