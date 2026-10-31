"""Project fixtures for the MMU/TLB UT workspace."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

pytest_plugins = ("ucv.pytest_selftest",)


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from suites.memblock.mmu.native import (
    initialize_inputs, load_bitmap_dut, load_bitmapcache_dut, load_hptw_dut,
    load_l2mq_dut, load_l2pf_dut, load_l2tlb_dut, load_l2tlbwrapper_dut,
    load_llptw_dut, load_pmp_dut, load_tlbn_dut,
    load_ptw_dut, load_ptwcache_dut,
    load_ptwfilter_dut, load_ptwrepeater_dut, load_tlb_dut, load_tlbfa_dut,
    load_wrapper_dut,
)
from suites.memblock.mmu.tlbfa.coverage import TlbfaCoverage
from suites.memblock.mmu.tlbfa.env import TlbfaEnv
from suites.memblock.mmu.wrapper.coverage import WrapperCoverage
from suites.memblock.mmu.wrapper.env import WrapperEnv
from suites.memblock.mmu.tlb.coverage import TlbCoverage
from suites.memblock.mmu.tlb.env import TlbEnv
from suites.memblock.mmu.l2.coverage import (BitmapCacheCoverage, BitmapCoverage, FilterCoverage,
                                   HptwCoverage, L2TlbCoverage, MQCoverage, PFCoverage,
                                   LlptwCoverage, PmpCoverage, PtwCacheCoverage,
                                   PtwCoverage, RepeaterCoverage, TlbnCoverage)
from suites.memblock.mmu.l2.missqueue import MQEnv
from suites.memblock.mmu.l2.l2pf import PFEnv
from suites.memblock.mmu.l2.ptw import FilterEnv, RepeaterEnv
from suites.memblock.mmu.l2.l2tlb import L2TlbEnv
from suites.memblock.mmu.l2.l2tlbwrapper import L2TlbWrapperEnv
from suites.memblock.mmu.tlbn.env import TlbNonBlockEnv
from suites.memblock.mmu.l2.hptw import HptwEnv
from suites.memblock.mmu.l2.ptw_walker import PtwEnv
from suites.memblock.mmu.l2.bitmap import BitmapCacheEnv, BitmapEnv
from suites.memblock.mmu.l2.pmp import PmpEnv
from suites.memblock.mmu.l2.llptw import LlptwEnv
from suites.memblock.mmu.l2.ptwcache import PtwCacheEnv


def _finish(dut) -> None:
    """Verilator writes the coverage database during Finish()."""
    dut.Finish()


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    """Keep Picker's generated dumpfile out of the evidence tree."""
    previous = Path.cwd()
    from ucv.runtime import scratch_root
    workdir = Path(tempfile.mkdtemp(prefix="mmu-pytest-", dir=scratch_root()))
    os.chdir(workdir)
    try:
        yield workdir
    finally:
        os.chdir(previous)
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture
def tlbfa_dut():
    DUT, argv = load_tlbfa_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def tlbfa_coverage():
    return TlbfaCoverage()


@pytest.fixture
def tlbfa_env(tlbfa_dut, tlbfa_coverage):
    return TlbfaEnv(tlbfa_dut, tlbfa_coverage)


@pytest.fixture
def wrapper_dut():
    DUT, argv = load_wrapper_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def wrapper_coverage():
    return WrapperCoverage()


@pytest.fixture
def wrapper_env(wrapper_dut, wrapper_coverage):
    return WrapperEnv(wrapper_dut, wrapper_coverage)


@pytest.fixture
def tlb_dut():
    DUT, argv = load_tlb_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def tlb_coverage():
    return TlbCoverage()


@pytest.fixture
def tlb_env(tlb_dut, tlb_coverage):
    return TlbEnv(tlb_dut, tlb_coverage)


@pytest.fixture
def l2mq_dut():
    DUT, argv = load_l2mq_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def l2mq_coverage():
    return MQCoverage()


@pytest.fixture
def l2mq_env(l2mq_dut, l2mq_coverage):
    return MQEnv(l2mq_dut, l2mq_coverage)


@pytest.fixture
def l2pf_dut():
    DUT, argv = load_l2pf_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def l2pf_coverage():
    return PFCoverage()


@pytest.fixture
def l2pf_env(l2pf_dut, l2pf_coverage):
    return PFEnv(l2pf_dut, l2pf_coverage)


@pytest.fixture
def ptwrepeater_dut():
    DUT, argv = load_ptwrepeater_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def repeater_coverage():
    return RepeaterCoverage()


@pytest.fixture
def repeater_env(ptwrepeater_dut, repeater_coverage):
    return RepeaterEnv(ptwrepeater_dut, repeater_coverage)


@pytest.fixture
def ptwfilter_dut():
    DUT, argv = load_ptwfilter_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def filter_coverage():
    return FilterCoverage()


@pytest.fixture
def filter_env(ptwfilter_dut, filter_coverage):
    return FilterEnv(ptwfilter_dut, filter_coverage)


@pytest.fixture
def l2tlb_dut():
    DUT, argv = load_l2tlb_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def tlbn_coverage():
    return TlbnCoverage()


@pytest.fixture
def tlbn_dut():
    DUT, argv = load_tlbn_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture
def tlbn_env(tlbn_dut, tlbn_coverage):
    return TlbNonBlockEnv(tlbn_dut, tlbn_coverage)


@pytest.fixture(scope="session")
def l2tlb_coverage():
    return L2TlbCoverage()


@pytest.fixture(scope="session")
def l2tlbwrapper_coverage():
    from suites.memblock.mmu.l2.coverage import L2TlbWrapperCoverage
    return L2TlbWrapperCoverage()


@pytest.fixture
def l2tlbwrapper_dut():
    DUT, argv = load_l2tlbwrapper_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture
def l2tlbwrapper_env(l2tlbwrapper_dut, l2tlbwrapper_coverage):
    return L2TlbWrapperEnv(l2tlbwrapper_dut, l2tlbwrapper_coverage)


@pytest.fixture
def l2tlb_env(l2tlb_dut, l2tlb_coverage):
    return L2TlbEnv(l2tlb_dut, l2tlb_coverage)


@pytest.fixture
def hptw_dut():
    DUT, argv = load_hptw_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def hptw_coverage():
    return HptwCoverage()


@pytest.fixture
def hptw_env(hptw_dut, hptw_coverage):
    return HptwEnv(hptw_dut, hptw_coverage)


@pytest.fixture
def ptw_dut():
    DUT, argv = load_ptw_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def ptw_coverage():
    return PtwCoverage()


@pytest.fixture
def ptw_env(ptw_dut, ptw_coverage):
    return PtwEnv(ptw_dut, ptw_coverage)


@pytest.fixture
def bitmapcache_dut():
    DUT, argv = load_bitmapcache_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def bitmapcache_coverage():
    return BitmapCacheCoverage()


@pytest.fixture
def bitmapcache_env(bitmapcache_dut, bitmapcache_coverage):
    return BitmapCacheEnv(bitmapcache_dut, bitmapcache_coverage)


@pytest.fixture
def bitmap_dut():
    DUT, argv = load_bitmap_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def bitmap_coverage():
    return BitmapCoverage()


@pytest.fixture
def bitmap_env(bitmap_dut, bitmap_coverage):
    return BitmapEnv(bitmap_dut, bitmap_coverage)


@pytest.fixture
def pmp_dut():
    DUT, argv = load_pmp_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def pmp_coverage():
    return PmpCoverage()


@pytest.fixture
def env_pmp(pmp_dut, pmp_coverage):
    return PmpEnv(pmp_dut, pmp_coverage)


@pytest.fixture
def llptw_dut():
    DUT, argv = load_llptw_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def llptw_coverage():
    return LlptwCoverage()


@pytest.fixture
def llptw_env(llptw_dut, llptw_coverage):
    return LlptwEnv(llptw_dut, llptw_coverage)


@pytest.fixture
def ptwcache_dut():
    DUT, argv = load_ptwcache_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def ptwcache_coverage():
    return PtwCacheCoverage()


@pytest.fixture
def ptwcache_env(ptwcache_dut, ptwcache_coverage):
    return PtwCacheEnv(ptwcache_dut, ptwcache_coverage)
