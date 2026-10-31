"""ProbeEnv environment for the probe_queue DUT."""
from __future__ import annotations

from suites.memblock.dcache.execution import pulse_reset, refresh, set_reset, step


class ProbeEnv:
    def __init__(self, dut, coverage=None):
        self.dut = dut
        self.coverage = coverage
        self.probe = {
            "ready": dut.io_mem_probe_ready,
            "valid": dut.io_mem_probe_valid,
            "param": dut.io_mem_probe_bits_param,
            "address": dut.io_mem_probe_bits_address,
            "data": dut.io_mem_probe_bits_data,
        }
        self.pipe = {
            "valid": dut.io_pipe_req_valid,
            "ready": dut.io_pipe_req_ready,
            "param": dut.io_pipe_req_bits_probe_param,
            "need_data": dut.io_pipe_req_bits_probe_need_data,
            "vaddr": dut.io_pipe_req_bits_vaddr,
            "addr": dut.io_pipe_req_bits_addr,
            "id": dut.io_pipe_req_bits_id,
        }
        self.lrsc = {
            "valid": dut.io_lrsc_locked_block_valid,
            "bits": dut.io_lrsc_locked_block_bits,
        }
        self.update_resv = dut.io_update_resv_set

    @staticmethod
    def value(signal) -> int:
        return int(signal.value)

    def reset(self) -> None:
        self._idle()
        set_reset(self, 1)
        step(self, 3)
        set_reset(self, 0)
        step(self, 2)

    def _idle(self) -> None:
        self.probe["valid"].Set(0)
        self.pipe["ready"].Set(1)
        self.lrsc["valid"].Set(0)
        self.update_resv.Set(0)

    def send(self, address: int, param: int, vaddr: int = 0, data: int = 0) -> None:
        self._idle()
        self.probe["valid"].Set(1)
        self.probe["param"].Set(param)
        self.probe["address"].Set(address)
        self.probe["data"].Set(data)
        self.vaddr = vaddr

    def accept(self) -> bool:
        ready = bool(self.value(self.probe["ready"]))
        step(self)
        self.probe["valid"].Set(0)
        return ready

    def watch_pipe(self, limit: int = 6) -> dict | None:
        for _ in range(limit):
            if self.value(self.pipe["valid"]):
                return {
                    "param": self.value(self.pipe["param"]),
                    "need_data": self.value(self.pipe["need_data"]),
                    "addr": self.value(self.pipe["addr"]),
                    "id": self.value(self.pipe["id"]),
                }
            step(self)
        return None
