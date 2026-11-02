"""Every MemBlock loader forwards the CLI-recorded seed at its native boundary."""
from types import SimpleNamespace

import pytest

from suites.memblock.dcache import native as dcache
from suites.memblock.lsu import native as lsu
from suites.memblock.mmu import native as mmu
from suites.memblock.sbuffer import native as sbuffer

MODULES=(dcache,lsu,mmu,sbuffer)
LEGACY={dcache:'DCACHE_VERILATOR_SEED',lsu:'LSU_VERILATOR_SEED',
        mmu:'MMU_VERILATOR_SEED',sbuffer:'SBUFFER_VERILATOR_SEED'}
LOADERS=(
    *[(dcache,dcache.load_dut,(key,)) for key in dcache.DUTS],
    *[(lsu,lsu.load_dut,(key,)) for key in lsu.DUTS],
    *[(mmu,getattr(mmu,name),()) for name in sorted(vars(mmu)) if name.startswith('load_')],
    (sbuffer,sbuffer.load_sbuffer_data_dut,()),(sbuffer,sbuffer.load_sbuffer_dut,()),
)


def label(case):
    module,load,args=case
    return module.__name__.split('.')[-2]+'.'+(args[0] if args else load.__name__)


def fake_package(monkeypatch,module):
    class Native:
        def __init__(self,arguments):
            self.arguments=list(arguments)

    class Package:
        def __getattr__(self,name):
            if name.startswith('DUT'):
                return Native
            raise AttributeError(name)

    monkeypatch.setattr(module,'_load_package',lambda *_:Package())
    monkeypatch.setattr(module.xsp,'StringVector',list)


@pytest.mark.parametrize('case',LOADERS,ids=label)
def test_all_native_loader_defaults_use_the_current_cli_seed_per_call(monkeypatch,case):
    module,load,args=case
    fake_package(monkeypatch,module)
    monkeypatch.setenv(LEGACY[module],'19')
    for seed in ('7','11'):
        monkeypatch.setenv('UCV_SEED',seed)
        cls,argv=load(*args)
        assert cls(argv).arguments[-1]==f'+verilator+seed+{seed}'


@pytest.mark.parametrize('module',MODULES,ids=lambda m:m.__name__.split('.')[-2])
@pytest.mark.parametrize('explicit', (None,0,4294967295))
def test_native_seed_default_legacy_fallback_and_explicit_override(monkeypatch,module,explicit):
    fake_package(monkeypatch,module)
    _,load,args=next(case for case in LOADERS if case[0] is module)
    monkeypatch.delenv('UCV_SEED',raising=False)
    monkeypatch.delenv(LEGACY[module],raising=False)
    cls,argv=load(*args,**({} if explicit is None else dict(seed=explicit)))
    assert cls(argv).arguments[-1]==f'+verilator+seed+{1 if explicit is None else explicit}'
    monkeypatch.setenv(LEGACY[module],'23')
    cls,argv=load(*args)
    assert cls(argv).arguments[-1]=='+verilator+seed+23'
    monkeypatch.setenv('UCV_SEED','5')
    cls,argv=load(*args,seed=3)
    assert cls(argv).arguments[-1]=='+verilator+seed+3'


@pytest.mark.parametrize('module',MODULES,ids=lambda m:m.__name__.split('.')[-2])
@pytest.mark.parametrize('bad',(-1,4294967296,True,1.0,'7'))
def test_invalid_explicit_native_seed_does_not_reach_the_constructor(monkeypatch,module,bad):
    fake_package(monkeypatch,module)
    _,load,args=next(case for case in LOADERS if case[0] is module)
    with pytest.raises(ValueError,match='seed'):
        load(*args,seed=bad)
