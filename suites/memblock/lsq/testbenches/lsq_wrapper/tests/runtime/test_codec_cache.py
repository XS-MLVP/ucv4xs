"""Pure-adapter boundaries; real-DUT equivalence is checked separately."""
from dataclasses import replace
import importlib

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec_cache import EncoderCache
from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec_cache import TARGETS
from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec_cache import immutable
from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec_cache import install
from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec_cache import restore


# Parameter IDs are archived case identities, not old package import aliases.
@pytest.mark.parametrize("module,name",TARGETS,
    ids=['lsqverify.'+name+'-encode' for name in
         ('replay.codec','load_queue.codec','store_queue.types','lsq_wrapper.codec')])
def test_pure_encoder_preserves_full_values_order_mutation_and_invalid_shape(module,name):
    provider=importlib.import_module(module)
    function=getattr(provider,name)
    if module=="suites.memblock.lsq.testbenches.replay.env.codec":
        from suites.memblock.lsq.testbenches.replay.transactions import Inputs
        packet=Inputs();invalid=replace(packet,enqueues=())
    elif module=="suites.memblock.lsq.testbenches.load_queue.env.codec":
        from suites.memblock.lsq.testbenches.load_queue.transactions import Inputs
        packet=Inputs();invalid=replace(packet,loads=())
    elif module=="suites.memblock.lsq.testbenches.store_queue.transactions":
        from suites.memblock.lsq.testbenches.store_queue.transactions import Inputs
        packet=Inputs();invalid=replace(packet,addresses=())
    else:
        from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs
        packet=Inputs();invalid=replace(packet,loads=())
    cached=EncoderCache(function,capacity=2)
    expected=function(packet)
    assert immutable(packet)
    left=cached(packet)
    assert list(left.items())==list(expected.items())
    left["reset"]=123
    again=cached(packet)
    assert list(again.items())==list(expected.items()) and again is not left
    assert cached.hits==1
    for value in (False,True,False):
        request=replace(packet,reset=value)
        assert list(cached(request).items())==list(function(request).items())
    assert len(cached.values)<=2 and len(cached.identities)<=2
    def failure(call):
        try:call(invalid)
        except Exception as exc:return type(exc),exc.args
        raise AssertionError("invalid shape unexpectedly accepted")
    assert failure(function)==failure(cached)==failure(cached)


def test_mutable_input_not_memoized_and_return_change_cannot_contaminate():
    from suites.memblock.lsq.testbenches.load_queue.env.codec import encode
    from suites.memblock.lsq.testbenches.load_queue.transactions import Inputs
    packet=replace(Inputs(),loads=list(Inputs().loads))
    cached=EncoderCache(encode)
    first=cached(packet)
    packet.loads[0]=replace(packet.loads[0],paddr=0x12345678)
    second=cached(packet)
    assert first!=second and second==encode(packet)
    assert cached.uncacheable==2 and cached.hits==cached.misses==len(cached.values)==0


def test_plugin_installs_only_pure_aliases_and_always_restores():
    caches,replacements=install()
    try:
        assert len(caches)==4 and replacements
        assert all(isinstance(getattr(module,name),EncoderCache) for module,name,_ in replacements)
        assert all(original.__name__=="encode" for _,_,original in replacements)
    finally:restore(replacements)
    assert all(getattr(module,name) is original for module,name,original in replacements)
