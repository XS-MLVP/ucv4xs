"""Opt-in bounded memoization of pure pin encoders, never model/DUT state."""
from collections import OrderedDict
from dataclasses import fields,is_dataclass
from functools import wraps
from hashlib import sha256
import importlib
import json
from pathlib import Path
import sys

import pytest


TARGETS=(("suites.memblock.lsq.replay.codec","encode"),("suites.memblock.lsq.load_queue.codec","encode"),
         ("suites.memblock.lsq.store_queue.types","encode"),("suites.memblock.lsq.lsq_wrapper.codec","encode"))


def immutable(value):
    if type(value) in (int,bool,str,type(None)):
        return True
    if type(value) is tuple:
        return all(immutable(part) for part in value)
    kind=type(value)
    return (kind.__module__.startswith("suites.memblock.lsq.") and is_dataclass(kind)
            and kind.__dataclass_params__.frozen and all(immutable(getattr(value,f.name)) for f in fields(kind)))


class EncoderCache:
    def __init__(self,function,capacity=64):
        self.function,self.capacity=function,capacity
        self.values=OrderedDict()
        self.identities=OrderedDict()
        self.hits=self.misses=self.uncacheable=0

    def eligible(self,value):
        identity=id(value)
        previous=self.identities.get(identity)
        if previous is not None:
            assert previous[0] is value
            self.identities.move_to_end(identity)
            return previous[1]
        result=immutable(value)
        self.identities[identity]=(value,result)
        if len(self.identities)>self.capacity:self.identities.popitem(last=False)
        return result

    def __call__(self,value):
        if not self.eligible(value):
            self.uncacheable+=1
            return self.function(value)
        key=(type(value),value)
        try:result=self.values[key]
        except KeyError:
            self.misses+=1
            result=self.function(value)
            assert type(result) is dict and all(type(k) is str and type(v) is int for k,v in result.items())
            self.values[key]=result.copy()
            if len(self.values)>self.capacity:self.values.popitem(last=False)
            return result
        self.hits+=1
        self.values.move_to_end(key)
        return result.copy()


def install():
    caches=[];replacements=[]
    for module,name in TARGETS:
        function=getattr(importlib.import_module(module),name)
        caches.append(EncoderCache(function))
    by_identity={id(cache.function):cache for cache in caches}
    for module in tuple(sys.modules.values()):
        if module is None or not getattr(module,"__name__","").startswith("suites.memblock.lsq."):
            continue
        for name,value in tuple(vars(module).items()):
            cache=by_identity.get(id(value))
            if cache is not None:
                replacements.append((module,name,value))
                setattr(module,name,cache)
    return caches,replacements


def restore(replacements):
    for module,name,function in reversed(replacements):setattr(module,name,function)


def pytest_addoption(parser):
    parser.addoption("--lsq-codec-cache",action="store_true",default=False,
                     help="opt-in pure immutable interface encoder cache; never cache checks or model state")


@pytest.hookimpl(wrapper=True,trylast=True)
def pytest_runtest_call(item):
    if not item.config.getoption("--lsq-codec-cache"):
        return (yield)
    factory=item.funcargs.get("dut_factory")
    if factory is None:raise ValueError("codec-cache control requires a real DUT fixture")
    caches,replacements=install()
    try:
        return (yield)
    finally:
        restore(replacements)
        source=Path(__file__)
        rows=[dict(function=cache.function.__module__+"."+cache.function.__name__,hits=cache.hits,misses=cache.misses,
                   uncacheable=cache.uncacheable,capacity=cache.capacity,retained_values=len(cache.values)) for cache in caches]
        report=dict(format="lsq-pure-codec-cache-summary-v1",nodeid=item.nodeid,rows=rows,
            replaced_aliases=[module.__name__+"."+name for module,name,_ in replacements],
            restored_all_aliases=True,implementation_SHA256=sha256(source.read_bytes()).hexdigest(),
            scope="call-phase pure immutable inputs only; full original encoder validations on misses, fresh dicts on hits. No model outputs/checks/DUT samples are cached. Not enabled by default.")
        with (factory.output/"codec-cache-summary.json").open("x") as stream:stream.write(json.dumps(report,indent=2)+"\n")
