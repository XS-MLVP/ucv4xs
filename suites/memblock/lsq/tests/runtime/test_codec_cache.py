"""Pure-adapter boundaries; real-DUT equivalence is checked separately."""
from dataclasses import replace
import importlib

import pytest

from lsqverify.codec_cache import EncoderCache,TARGETS,immutable,install,restore


@pytest.mark.parametrize("module,name",TARGETS)
def test_pure_encoder_preserves_full_values_order_mutation_and_invalid_shape(module,name):
    provider=importlib.import_module(module)
    function=getattr(provider,name)
    if module=="lsqverify.replay.codec":
        from lsqverify.replay.types import Inputs
        packet=Inputs();invalid=replace(packet,enqueues=())
    elif module=="lsqverify.load_queue.codec":
        from lsqverify.load_queue.types import Inputs
        packet=Inputs();invalid=replace(packet,loads=())
    elif module=="lsqverify.store_queue.types":
        from lsqverify.store_queue.types import Inputs
        packet=Inputs();invalid=replace(packet,addresses=())
    else:
        from lsqverify.lsq_wrapper.types import Inputs
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
    from lsqverify.load_queue.codec import encode
    from lsqverify.load_queue.types import Inputs
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
