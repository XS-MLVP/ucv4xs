"""Cross-region lifecycle under coherent PHR and independent directory checking."""
from suites.frontend.bpu.bpu.case.ittage_feedback import PC, check_target_feedback
from suites.frontend.bpu.bpu.checker.ittage_region import RegionChecker
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.model.ittage_region import feedback_targets
from suites.frontend.bpu.bpu.monitor.ittage_region import RegionMonitor


async def check_region_feedback(agent, root, output):
    phr = BpuPhrChecker(scope='real cross-region ITTAGE target feedback')
    regions, monitor = RegionChecker(), RegionMonitor(agent)
    async with agent.observe_phr(phr):
        monitor.start(regions)
        try:
            result = await check_target_feedback(agent, root, targets=feedback_targets(PC),
                diagnostics=output, region_checker=regions, coherent_checker=phr)
            regions.summary()
            phr.summary()
            return result
        finally:
            await monitor.aclose()
