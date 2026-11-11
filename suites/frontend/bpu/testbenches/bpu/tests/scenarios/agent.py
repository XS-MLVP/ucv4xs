"""BPU fixture facade for the existing owned composition scenario API."""

from suites.frontend.bpu.testbenches.bpu.env.agent.main import BpuAgent


class BpuScenarioAgent(BpuAgent):
    """Keep scenario composition on the test side of the transaction agent."""

    async def compare_early_composition(self, *, pc: int, probe: str):
        """Run an owned composition program and return detached witness data."""
        self._require_started()
        from suites.frontend.bpu.testbenches.bpu.tests.scenarios.composition import early_composition
        return await early_composition(self, pc=pc, probe=probe)

    async def compare_redirect_training(self, *, pc: int, distinguish_origin: bool = False):
        """Co-launch associated feedback/recovery; never expose their checker."""
        self._require_started()
        if type(distinguish_origin) is not bool:
            raise ValueError('origin discrimination requires a bool')
        from suites.frontend.bpu.testbenches.bpu.tests.scenarios.composition import redirect_training
        return await redirect_training(self, pc=pc, distinguish_origin=distinguish_origin)

    async def check_unpublished_ittage(self, *, pc: int, position: int, target: int,
                                     coverage, evidence):
        """Exercise late feedback and publish only detached metadata evidence."""
        self._require_started()
        from suites.frontend.bpu.testbenches.bpu.tests.scenarios.composition import unpublished_ittage
        await unpublished_ittage(self, pc=pc, position=position, target=target,
                                coverage=coverage, evidence=evidence)
