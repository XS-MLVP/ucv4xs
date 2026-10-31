import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from suites.memblock.dcache.dcache.env import DcacheEnv
from suites.memblock.dcache.dcache.coverage import DCacheCoverage
from suites.memblock.dcache.execution import step

def refill_line(dc, base):
    beats = [int.from_bytes(bytes(((base + beat * 32 + i) & 0xFF) for i in range(32)), "little") for beat in range(2)]
    dc.load_once(0, base, base, context="lane0 cold")
    dc.service_miss(base, data_beats=beats, context="prime")
    for _ in range(6):
        step(dc)
    # Dirty the line so eviction must write it back.
    dc.drive_store(base, base, int.from_bytes(bytes([0x5A] * 64), "little"),
                   mask=0xFFFFFFFFFFFFFFFF, store_id=4)
    for _ in range(3):
        step(dc)
    dc.stop_store()
    dc.wait_store_hit(8)
    for _ in range(3):
        step(dc)
    return beats

def test_probe_ack(dut_factory):
    dut = dut_factory("dcache")
    dc = DcacheEnv(dut, DCacheCoverage())
    dc.reset()
    base = 0x8000
    beats = [int.from_bytes(bytes(((base + beat * 32 + i) & 0xFF) for i in range(32)), "little") for beat in range(2)]
    dc.load_once(0, base, base, context="lane0 cold")
    dc.service_miss(base, data_beats=beats, context="probe prime")
    for _ in range(8):
        dut.Step(1)
    channel = dc.channels[0]
    channel["b_valid"].Set(1)
    channel["b_param"].Set(0)
    channel["b_address"].Set(base)
    response = None
    for _ in range(24):
        dut.Step(1)
        dc.refresh()
        if int(channel["c_valid"].value):
            response = {
                "opcode": int(channel["c_opcode"].value),
                "param": int(channel["c_param"].value),
                "size": int(channel["c_size"].value),
                "address": int(channel["c_address"].value),
            }
            break
    channel["b_valid"].Set(0)
    assert response is not None, "probe must produce a C-channel acknowledgement"
    assert response["opcode"] in (4, 5), response
    assert response["address"] == base, response
