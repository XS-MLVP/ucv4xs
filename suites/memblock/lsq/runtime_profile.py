"""Opt-in, per-call cProfile summaries for existing real Picker DUT cases."""
import cProfile
from hashlib import sha256
import json
from pathlib import Path
import pstats
import time

import pytest


def pytest_addoption(parser):
    parser.addoption("--lsq-runtime-profile",action="store_true",default=False,
                     help="retain compact call-time cProfile summaries; no binary profile or cycle trace")


@pytest.hookimpl(wrapper=True,tryfirst=True)
def pytest_runtest_call(item):
    if not item.config.getoption("--lsq-runtime-profile"):
        return (yield)
    factory=item.funcargs.get("dut_factory")
    if factory is None:
        raise ValueError("LSQ runtime profile requires an existing real-DUT fixture")
    profiler=cProfile.Profile()
    wall,cpu=time.perf_counter(),time.process_time()
    profiler.enable()
    try:
        return (yield)
    finally:
        profiler.disable()
        wall,cpu=time.perf_counter()-wall,time.process_time()-cpu
        stats=pstats.Stats(profiler)
        rows=[dict(file=key[0],line=key[1],function=key[2],primitive_calls=value[0],calls=value[1],
                   own_seconds=value[2],cumulative_seconds=value[3]) for key,value in stats.stats.items()]
        source=Path(__file__)
        report=dict(format="lsq-runtime-profile-summary-v1",nodeid=item.nodeid,phase="pytest_runtest_call",
            wall_seconds=wall,process_CPU_seconds=cpu,total_calls=stats.total_calls,primitive_calls=stats.prim_calls,
            own_time_total=stats.total_tt,top_own=sorted(rows,key=lambda row:row["own_seconds"],reverse=True)[:50],
            top_cumulative=sorted(rows,key=lambda row:row["cumulative_seconds"],reverse=True)[:50],
            observer_SHA256=sha256(source.read_bytes()).hexdigest(),
            limits="Profile overhead changes timings. Cumulative times overlap; never sum them. Call phase excludes fixture boot/teardown and native coverage merge. No execution/check/actor method is changed.")
        output=factory.output/"runtime-profile-summary.json"
        with output.open("x") as stream:stream.write(json.dumps(report,indent=2)+"\n")
