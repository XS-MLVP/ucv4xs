"""Restore, then genuinely consume the full restored address after younger work."""
from copy import deepcopy
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.testbenches.shared.coverage.exports import write_functional_coverage
from suites.frontend.bpu.testbenches.ras.model.guarded_lifetime import CFI_BYTES
from suites.frontend.bpu.testbenches.ras.model.guarded_lifetime import retained_return
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT


async def check_guard_lifetime(agent, pc):
    groups = {role: CoverGroupDef('ras_guard_lifetime_v1', (
        CoverPointDef('class', {str(cfi): Bin.values(str(cfi)) for cfi in CFI_BYTES}),
    )).instantiate(f'kunminghu_v3.ras.guard-lifetime.{role}') for role in ('reached', 'checked')}
    try:
        await agent.reset()
        await agent.act(2, start_pc=0x40001000, position=3)
        checkpoint = agent.snapshot()
        frozen = deepcopy(checkpoint.redirect_meta)
        await agent.act(2, start_pc=0x40002000, position=5)
        restored = await agent.recover(checkpoint.redirect_meta, action=2, cfi_pc=pc)
        groups['reached'].sample({'class': str(pc)}, metadata={'original': frozen})
        expected = retained_return(pc)
        assert restored.top == expected
        await agent.act(2, start_pc=0x40003000, position=7)
        returned = await agent.act(1)
        assert returned.top == expected
        assert checkpoint.redirect_meta == frozen
        groups['checked'].sample({'class': str(pc)}, metadata={'top': returned.top})
    finally:
        write_functional_coverage(CoverageDatabase(groups.values()),
            output_directory(REPO_ROOT, 'ras') / 'functional-coverage-guard-lifetime.json')
