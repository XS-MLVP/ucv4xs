"""MMU pytest root: explicit plugin registration only."""
from pathlib import Path

from suites.memblock.mmu.testbenches.shared.env.pytest_plugins.fixtures import isolated_workdir

ROOT = Path(__file__).resolve().parent

pytest_plugins = (
    'ucv.pytest_selftest',
    'suites.memblock.mmu.testbenches.tlbfa.tests.fixtures',
    'suites.memblock.mmu.testbenches.wrapper.tests.fixtures',
    'suites.memblock.mmu.testbenches.tlb.tests.fixtures',
    'suites.memblock.mmu.testbenches.l2mq.tests.fixtures',
    'suites.memblock.mmu.testbenches.l2pf.tests.fixtures',
    'suites.memblock.mmu.testbenches.ptwrepeater.tests.fixtures',
    'suites.memblock.mmu.testbenches.l2tlb.tests.fixtures',
    'suites.memblock.mmu.testbenches.tlbn.tests.fixtures',
    'suites.memblock.mmu.testbenches.l2tlbwrapper.tests.fixtures',
    'suites.memblock.mmu.testbenches.hptw.tests.fixtures',
    'suites.memblock.mmu.testbenches.ptw.tests.fixtures',
    'suites.memblock.mmu.testbenches.bitmap.tests.fixtures',
    'suites.memblock.mmu.testbenches.pmp.tests.fixtures',
    'suites.memblock.mmu.testbenches.llptw.tests.fixtures',
    'suites.memblock.mmu.testbenches.ptwcache.tests.fixtures',
)
