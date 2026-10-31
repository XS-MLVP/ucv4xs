"""WbqEnv environment for the writeback_queue DUT."""
from __future__ import annotations

from suites.memblock.dcache.execution import pulse_reset, refresh, set_reset, step


class WbqEnv:
    def __init__(self, dut, coverage=None):
        self.dut = dut
        self.coverage = coverage
        self.req = {
            "ready": dut.io_req_ready,
            "valid": dut.io_req_valid,
            "param": dut.io_req_bits_param,
            "voluntary": dut.io_req_bits_voluntary,
            "hasData": dut.io_req_bits_hasData,
            "corrupt": dut.io_req_bits_corrupt,
            "addr": dut.io_req_bits_addr,
            "data": dut.io_req_bits_data,
        }
        self.release = []
        for index in range(2):
            prefix = f"io_mem_release_{index}"
            self.release.append({
                "ready": getattr(dut, prefix + "_ready"),
                "valid": getattr(dut, prefix + "_valid"),
                "opcode": getattr(dut, prefix + "_bits_opcode"),
                "param": getattr(dut, prefix + "_bits_param"),
                "size": getattr(dut, prefix + "_bits_size"),
                "source": getattr(dut, prefix + "_bits_source"),
                "address": getattr(dut, prefix + "_bits_address"),
                "data": getattr(dut, prefix + "_bits_data"),
                "corrupt": getattr(dut, prefix + "_bits_corrupt"),
            })
        self.grant = []
        for index in range(2):
            prefix = f"io_mem_grant_{index}"
            self.grant.append({
                "ready": getattr(dut, prefix + "_ready"),
                "valid": getattr(dut, prefix + "_valid"),
                "source": getattr(dut, prefix + "_bits_source"),
            })
        self.conflict = [{
            "valid": getattr(dut, f"io_miss_req_conflict_check_{index}_valid"),
            "bits": getattr(dut, f"io_miss_req_conflict_check_{index}_bits"),
        } for index in range(4)]
        self.block = [getattr(dut, f"io_block_miss_req_{index}") for index in range(4)]

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
        self.req["valid"].Set(0)
        for grant in self.grant:
            grant["valid"].Set(0)
        for index in range(4):
            self.conflict[index]["valid"].Set(0)
        for index in range(2):
            # Hold the C beat until the test has sampled it.
            self.release[index]["ready"].Set(0)

    def drive(self, addr: int, data: int = 0, *, has_data: bool = True,
              param: int = 0, voluntary: bool = True, corrupt: bool = False) -> None:
        self._idle()
        self.req["valid"].Set(1)
        self.req["param"].Set(param)
        self.req["voluntary"].Set(1 if voluntary else 0)
        self.req["hasData"].Set(1 if has_data else 0)
        self.req["corrupt"].Set(1 if corrupt else 0)
        self.req["addr"].Set(addr)
        self.req["data"].Set(data)

    def fire(self) -> None:
        step(self)
        self.req["valid"].Set(0)

    def wait_release(self, channel: int, limit: int = 8) -> dict | None:
        pins = self.release[channel]
        for _ in range(limit):
            if self.value(pins["valid"]):
                return {
                    "opcode": self.value(pins["opcode"]),
                    "param": self.value(pins["param"]),
                    "size": self.value(pins["size"]),
                    "source": self.value(pins["source"]),
                    "address": self.value(pins["address"]),
                    "data": self.value(pins["data"]),
                    "corrupt": self.value(pins["corrupt"]),
                }
            step(self)
        return None

    def issue_and_wait(self, addr: int, data: int = 0, *, has_data: bool = True,
                       param: int = 0, voluntary: bool = True,
                       corrupt: bool = False) -> tuple[dict, int]:
        self.drive(addr, data, has_data=has_data, param=param,
                   voluntary=voluntary, corrupt=corrupt)
        refresh(self)
        assert self.value(self.req["ready"]) == 1
        self.fire()
        info = None
        chosen = 0
        for _ in range(16):
            for channel in (0, 1):
                pins = self.release[channel]
                if self.value(pins["valid"]):
                    info = {
                        "opcode": self.value(pins["opcode"]),
                        "param": self.value(pins["param"]),
                        "size": self.value(pins["size"]),
                        "source": self.value(pins["source"]),
                        "address": self.value(pins["address"]),
                        "data": self.value(pins["data"]),
                        "corrupt": self.value(pins["corrupt"]),
                    }
                    chosen = channel
                    break
            if info is not None:
                break
            step(self)
        assert info is not None, "release must appear on one C channel"
        # Drain every C beat of this response (ReleaseData uses two beats).
        self.release[chosen]["ready"].Set(1)
        for _ in range(6):
            step(self)
        self.release[chosen]["ready"].Set(0)
        if self.coverage is not None:
            self.coverage.sample_release(info, chosen, voluntary)
        return info, chosen

    def ack(self, channel: int, source: int | None = None) -> None:
        grant = self.grant[channel]
        grant["valid"].Set(1)
        grant["source"].Set(source if source is not None
                            else self.value(self.release[channel]["source"]))
        for _ in range(8):
            if self.value(grant["ready"]):
                break
            step(self)
        step(self)
        grant["valid"].Set(0)

    def drain(self, cycles: int = 3) -> None:
        for _ in range(cycles):
            step(self)

    def block_probe(self, address: int) -> list[int]:
        for index in range(4):
            self.conflict[index]["valid"].Set(1)
            self.conflict[index]["bits"].Set(address)
        refresh(self)
        values = [self.value(signal) for signal in self.block]
        for index in range(4):
            self.conflict[index]["valid"].Set(0)
        return values
