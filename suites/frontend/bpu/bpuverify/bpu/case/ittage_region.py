"""Cross-region lifecycle under coherent PHR and independent directory checking."""
from bpuverify.bpu.case.ittage_feedback import PC, check_target_feedback
from bpuverify.bpu.checker.ittage_region import RegionChecker
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.model.ittage_region import feedback_targets
from bpuverify.bpu.monitor.ittage_region import RegionMonitor


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
