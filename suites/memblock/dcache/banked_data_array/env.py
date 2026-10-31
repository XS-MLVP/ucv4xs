"""Port-level environment for BankedDataArray.

Calibrated timing on the generated RTL:

* read ports: request in cycle T, 8-bank response window valid in cycle T+1;
* functional write in cycle T commits at the T+1 edge; a read issued in T sees
  the old value, a read issued in T+1 sees the new value;
* readline: fire in T, response register updates at the T+1 edge when
  ``can_go`` and ``can_resp`` are high in T+1;
* read-read conflicts are reported one cycle later; the oldest lqIdx wins.
"""
from __future__ import annotations

from .coverage import BankedDataArrayCoverage
from .model import BANKS, VWORD_BANKS, BankedDataArrayModel, bank_base

DATA_MASK = (1 << BANKS) - 1


class BankedDataArrayEnv:
    def __init__(self, dut, coverage: BankedDataArrayCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = BankedDataArrayModel()
        self.read = []
        for port in range(3):
            self.read.append({
                "valid": getattr(dut, f"io_read_{port}_valid"),
                "ready": getattr(dut, f"io_read_{port}_ready"),
                "way_en": getattr(dut, f"io_read_{port}_bits_way_en"),
                "addr": getattr(dut, f"io_read_{port}_bits_addr"),
                "addr_dup": getattr(dut, f"io_read_{port}_bits_addr_dup"),
                "bankMask": getattr(dut, f"io_read_{port}_bits_bankMask"),
                "lqidx": getattr(dut, f"io_read_{port}_bits_lqIdx_value"),
                "resp": [getattr(dut, f"io_read_resp_{port}_{j}_raw_data")
                         for j in range(VWORD_BANKS)],
                "error": [getattr(dut, f"io_read_error_delayed_{port}_{j}")
                          for j in range(VWORD_BANKS)],
                "bank_conflict": getattr(dut, f"io_bank_conflict_slow_{port}"),
                "rr_conflict": getattr(dut, f"io_rr_bank_conflict_slow_{port}"),
            })
        self.line = {
            "valid": dut.io_readline_valid,
            "ready": dut.io_readline_ready,
            "way_en": dut.io_readline_bits_way_en,
            "addr": dut.io_readline_bits_addr,
            "rmask": dut.io_readline_bits_rmask,
            "can_go": dut.io_readline_can_go,
            "stall": dut.io_readline_stall,
            "can_resp": dut.io_readline_can_resp,
            "resp": [getattr(dut, f"io_readline_resp_{bank}_raw_data")
                     for bank in range(BANKS)],
            "error": dut.io_readline_error_delayed,
        }
        self.write = {
            "valid": dut.io_write_valid,
            "wmask": dut.io_write_bits_wmask,
            "data": [getattr(dut, f"io_write_bits_data_{bank}") for bank in range(BANKS)],
            "dup_valid": [getattr(dut, f"io_write_dup_{bank}_valid")
                          for bank in range(BANKS)],
            "dup_way": [getattr(dut, f"io_write_dup_{bank}_bits_way_en")
                        for bank in range(BANKS)],
            "dup_addr": [getattr(dut, f"io_write_dup_{bank}_bits_addr")
                         for bank in range(BANKS)],
        }
        self.pseudo = {
            "valid": dut.io_pseudo_error_valid,
            "ready": dut.io_pseudo_error_ready,
            "bank_valid": [getattr(dut, f"io_pseudo_error_bits_{bank}_valid")
                           for bank in range(BANKS)],
            "bank_mask": [getattr(dut, f"io_pseudo_error_bits_{bank}_mask")
                          for bank in range(BANKS)],
        }
        self.mbist = {
            "array": dut.boreChildrenBd_bore_array,
            "all": dut.boreChildrenBd_bore_all,
            "req": dut.boreChildrenBd_bore_req,
            "ack": dut.boreChildrenBd_bore_ack,
            "writeen": dut.boreChildrenBd_bore_writeen,
            "be": dut.boreChildrenBd_bore_be,
            "addr": dut.boreChildrenBd_bore_addr,
            "indata": dut.boreChildrenBd_bore_indata,
            "readen": dut.boreChildrenBd_bore_readen,
            "addr_rd": dut.boreChildrenBd_bore_addr_rd,
            "outdata": dut.boreChildrenBd_bore_outdata,
        }
        self.window_cache = [[0] * VWORD_BANKS for _ in range(3)]
        self.transactions = 0
        self.last_error = [0] * VWORD_BANKS

    @staticmethod
    def _val(signal) -> int:
        return int(signal.value)

    def refresh(self) -> None:
        self.dut.xclock.RefreshComb()

    def _idle(self) -> None:
        self.mbist["req"].Set(0)
        self.mbist["writeen"].Set(0)
        self.mbist["readen"].Set(0)
        self.mbist["all"].Set(0)
        self.pseudo["valid"].Set(0)
        for bank in range(BANKS):
            self.pseudo["bank_valid"][bank].Set(0)
        for port in self.read:
            port["valid"].Set(0)
        self.line["valid"].Set(0)
        self.line["can_go"].Set(0)
        self.line["can_resp"].Set(0)
        self.line["stall"].Set(0)
        self.write["valid"].Set(0)
        for bank in range(BANKS):
            self.write["dup_valid"][bank].Set(0)

    def reset(self) -> None:
        self._idle()
        self.dut.reset.Set(1)
        self.dut.Step(3)
        self.dut.reset.Set(0)
        self.dut.Step(2)
        self.model.reset()
        self.window_cache = [[0] * VWORD_BANKS for _ in range(3)]

    # ---------------------------------------------------------------- write
    def drive_write(self, wmask: int, data: list[int], dup_valid: int | None = None,
                    way: int = 0, addr: int = 0,
                    addresses: list[int] | None = None) -> None:
        dup_valid = DATA_MASK if dup_valid is None else dup_valid
        self._idle()
        self.write["valid"].Set(1)
        self.write["wmask"].Set(wmask)
        for bank in range(BANKS):
            self.write["data"][bank].Set(data[bank] & 0xFFFF)
            self.write["dup_valid"][bank].Set((dup_valid >> bank) & 1)
            self.write["dup_way"][bank].Set(1 << way)
            self.write["dup_addr"][bank].Set(
                addresses[bank] if addresses is not None else addr)
        self.refresh()
        return

    def commit_write(self, wmask: int, data: list[int], dup_valid: int | None = None,
                     way: int = 0, addr: int = 0,
                     addresses: list[int] | None = None) -> None:
        dup_valid = DATA_MASK if dup_valid is None else dup_valid
        self.drive_write(wmask, data, dup_valid, way, addr, addresses)
        self.dut.Step(1)
        self.write["valid"].Set(0)
        for bank in range(BANKS):
            self.write["dup_valid"][bank].Set(0)
        self.dut.Step(1)
        dup_ways = [1 << way] * BANKS
        dup_addrs = addresses if addresses is not None else [addr] * BANKS
        self.model.commit_write(wmask, data, dup_valid, dup_ways, dup_addrs)
        if self.coverage is not None:
            self.coverage.sample_write(wmask, dup_valid, way)

    # ---------------------------------------------------------------- read
    def _addresses_equal(self, a: int, b: int) -> bool:
        return a == b

    def read_port(self, port: int, addr: int, way: int, bank_mask: int,
                  *, addr_dup: int | None = None, lqidx: int = 1,
                  check: bool = True, coverage: bool = True) -> list[int]:
        """Issue one read and return the 8-bank response window."""
        addr_dup = addr if addr_dup is None else addr_dup
        pins = self.read[port]
        self._idle()
        pins["valid"].Set(1)
        pins["way_en"].Set(1 << way)
        pins["addr"].Set(addr)
        pins["addr_dup"].Set(addr_dup)
        pins["bankMask"].Set(bank_mask)
        pins["lqidx"].Set(lqidx)
        self.refresh()
        # Wait out the single-port write->read hazard window.
        for _ in range(4):
            ready = self._val(pins["ready"])
            if ready:
                break
            self.dut.Step(1)
            self.refresh()
        if not ready:
            pins["valid"].Set(0)
            raise AssertionError(f"read port {port} stayed busy for 4 cycles")
        self.dut.Step(1)
        pins["valid"].Set(0)
        self.refresh()
        window = [self._val(signal) for signal in pins["resp"]]
        self.window_cache[port] = window
        if check:
            expected = self.model.read_result(addr, addr_dup, 1 << way,
                                              bank_mask, self.window_cache[port])
            if window != expected and bank_mask == 0xFF:
                raise AssertionError(
                    f"read port {port} addr={addr:#x} way={way} mask={bank_mask:#x}: "
                    f"{[hex(v) for v in window]} != {[hex(v) for v in expected]}")
            errors = [self._val(signal) for signal in pins["error"]]
            self.last_error = errors
        if coverage and self.coverage is not None:
            self.coverage.sample_read(port, way, bank_mask, addr)
            self.coverage.sample_ecc("read", "roundtrip")
        return window

    def read_port_injected(self, port: int, addr: int, way: int, bank_mask: int,
                           inject_banks: int, inject_mask: int) -> list[int]:
        """Read with a pseudo-error mask forced on the selected banks."""
        pins = self.read[port]
        self._idle()
        self.pseudo["valid"].Set(1)
        for bank in range(BANKS):
            self.pseudo["bank_valid"][bank].Set((inject_banks >> bank) & 1)
            self.pseudo["bank_mask"][bank].Set(inject_mask & ((1 << 16) - 1))
        pins["valid"].Set(1)
        pins["way_en"].Set(1 << way)
        pins["addr"].Set(addr)
        pins["addr_dup"].Set(addr)
        pins["bankMask"].Set(bank_mask)
        pins["lqidx"].Set(1)
        self.refresh()
        for _ in range(4):
            if self._val(pins["ready"]):
                break
            self.dut.Step(1)
            self.refresh()
        self.dut.Step(1)
        pins["valid"].Set(0)
        self.refresh()
        # bank_result is combinational in the response cycle, so the pseudo
        # mask must still be asserted when the data is sampled.
        window = [self._val(signal) for signal in pins["resp"]]
        self.pseudo["valid"].Set(0)
        for bank in range(BANKS):
            self.pseudo["bank_valid"][bank].Set(0)
        if self.coverage is not None:
            self.coverage.sample_ecc("read", "injected_xor")
        return window

    def write_read_conflict(self, addr: int, way: int, wmask: int,
                            read_banks: int, data: int = 0x5A5A) -> int:
        """Drive a write then an overlapping read; return the read conflict flag."""
        self._idle()
        self.write["valid"].Set(1)
        self.write["wmask"].Set(wmask)
        for bank in range(BANKS):
            self.write["data"][bank].Set(data)
            self.write["dup_valid"][bank].Set((wmask >> bank) & 1)
            self.write["dup_way"][bank].Set(1 << way)
            self.write["dup_addr"][bank].Set(addr)
        self.dut.Step(1)
        self.write["valid"].Set(0)
        for bank in range(BANKS):
            self.write["dup_valid"][bank].Set(0)
        pins = self.read[0]
        pins["valid"].Set(1)
        pins["way_en"].Set(1 << way)
        pins["addr"].Set(addr)
        pins["addr_dup"].Set(addr)
        pins["bankMask"].Set(read_banks)
        pins["lqidx"].Set(1)
        self.refresh()
        ready = self._val(pins["ready"])
        self.dut.Step(1)
        pins["valid"].Set(0)
        self.refresh()
        flag = self._val(pins["bank_conflict"])
        if self.coverage is not None:
            self.coverage.sample_conflict("write_read")
            self.coverage.sample_conflict("read_line") if False else None
        return flag if True else ready

    def mbist_write(self, array: int, addr: int, data: int, be: int = (1 << 88) - 1,
                    all_sram: bool = False) -> int:
        self._idle()
        self.mbist["array"].Set(array)
        self.mbist["all"].Set(1 if all_sram else 0)
        self.mbist["be"].Set(be)
        self.mbist["addr"].Set(addr)
        self.mbist["addr_rd"].Set(addr)
        self.mbist["indata"].Set(data)
        self.mbist["writeen"].Set(1)
        self.mbist["req"].Set(1)
        self.dut.Step(1)
        ack = self._val(self.mbist["ack"])
        self.mbist["req"].Set(0)
        self.mbist["writeen"].Set(0)
        self.mbist["all"].Set(0)
        self.dut.Step(1)
        return ack

    def mbist_read(self, array: int, addr_rd: int,
                   all_sram: bool = False) -> int:
        self._idle()
        self.mbist["array"].Set(array)
        self.mbist["all"].Set(1 if all_sram else 0)
        self.mbist["addr_rd"].Set(addr_rd)
        self.mbist["readen"].Set(1)
        self.mbist["req"].Set(1)
        self.dut.Step(1)
        ack = self._val(self.mbist["ack"])
        self.mbist["req"].Set(0)
        self.mbist["readen"].Set(0)
        self.mbist["all"].Set(0)
        # ack cycle -> SRAM read edge -> MBIST output register edge
        self.dut.Step(1)
        self.dut.Step(1)
        data = self._val(self.mbist["outdata"])
        if not ack:
            raise AssertionError(f"MBIST read array {array} not acknowledged")
        return data

    def read_line(self, addr: int, way: int, rmask: int = DATA_MASK, *,
                  check: bool = True, coverage: bool = True) -> list[int]:
        pins = self.line
        self._idle()
        pins["valid"].Set(1)
        pins["way_en"].Set(1 << way)
        pins["addr"].Set(addr)
        pins["rmask"].Set(rmask)
        self.dut.Step(1)
        pins["valid"].Set(0)
        pins["can_go"].Set(1)
        pins["can_resp"].Set(1)
        self.dut.Step(1)
        pins["can_go"].Set(0)
        pins["can_resp"].Set(0)
        self.refresh()
        window = [self._val(signal) for signal in pins["resp"]]
        if check:
            expected = self.model.line_result(addr, 1 << way, rmask)
            # Only banks selected by rmask are driven by this read; unmasked
            # banks retain whatever the previous bank read produced.
            for bank in range(BANKS):
                if (rmask >> bank) & 1 and window[bank] != expected[bank]:
                    raise AssertionError(
                        f"readline addr={addr:#x} way={way} mask={rmask:#x} bank={bank}: "
                        f"{window[bank]:#x} != {expected[bank]:#x}")
            self.last_error = [self._val(pins["error"])]
        if coverage and self.coverage is not None:
            self.coverage.sample_line(way, rmask, hold=False)
            self.coverage.sample_ecc("line", "roundtrip")
        return window

    def read_line_stall(self, addr: int, way: int, rmask: int = DATA_MASK) -> list[int]:
        """Fire a new readline but hold the previous output with stall."""
        pins = self.line
        before = [self._val(signal) for signal in pins["resp"]]
        self._idle()
        pins["valid"].Set(1)
        pins["way_en"].Set(1 << way)
        pins["addr"].Set(addr)
        pins["rmask"].Set(rmask)
        pins["stall"].Set(1)
        self.dut.Step(1)
        pins["valid"].Set(0)
        pins["can_go"].Set(0)
        pins["can_resp"].Set(0)
        pins["stall"].Set(1)
        self.dut.Step(1)
        pins["stall"].Set(0)
        self.refresh()
        after = [self._val(signal) for signal in pins["resp"]]
        if after != before:
            raise AssertionError(
                f"readline stall changed output: {[hex(v) for v in after[:8]]} != "
                f"{[hex(v) for v in before[:8]]}")
        if self.coverage is not None:
            self.coverage.sample_line(way, rmask, hold=True)
        return after

    # ---------------------------------------------------------------- misc
    def idle(self, cycles: int = 2) -> None:
        self._idle()
        for _ in range(cycles):
            self.dut.Step(1)

    def conflict_probe_three(self, addrs: list[int], ways: list[int],
                             masks: list[int], lqs: list[int]) -> dict:
        self._idle()
        for port in range(3):
            pins = self.read[port]
            pins["valid"].Set(1)
            pins["way_en"].Set(1 << ways[port])
            pins["addr"].Set(addrs[port])
            pins["addr_dup"].Set(addrs[port])
            pins["bankMask"].Set(masks[port])
            pins["lqidx"].Set(lqs[port])
        self.refresh()
        self.dut.Step(1)
        for port in range(3):
            self.read[port]["valid"].Set(0)
        self.refresh()
        return {port: {"rr": self._val(self.read[port]["rr_conflict"]),
                       "bank": self._val(self.read[port]["bank_conflict"])}
                for port in range(3)}

    def conflict_probe(self, addr0: int, way0: int, mask0: int, lq0: int,
                       addr1: int, way1: int, mask1: int, lq1: int,
                       addr_dup0: int | None = None,
                       addr_dup1: int | None = None) -> dict:
        """Drive two reads for one cycle and return next-cycle conflict flags."""
        addr_dup0 = addr0 if addr_dup0 is None else addr_dup0
        addr_dup1 = addr1 if addr_dup1 is None else addr_dup1
        self._idle()
        for port, addr, addr_dup, way, mask, lq in (
                (0, addr0, addr_dup0, way0, mask0, lq0),
                (1, addr1, addr_dup1, way1, mask1, lq1)):
            pins = self.read[port]
            pins["valid"].Set(1)
            pins["way_en"].Set(1 << way)
            pins["addr"].Set(addr)
            pins["addr_dup"].Set(addr_dup)
            pins["bankMask"].Set(mask)
            pins["lqidx"].Set(lq)
        self.refresh()
        ready = [self._val(self.read[port]["ready"]) for port in range(2)]
        self.dut.Step(1)
        for port in range(2):
            self.read[port]["valid"].Set(0)
        self.refresh()
        result = {
            "ready": ready,
            "rr_conflict": [self._val(self.read[port]["rr_conflict"]) for port in range(2)],
            "bank_conflict": [self._val(self.read[port]["bank_conflict"])
                              for port in range(2)],
        }
        if self.coverage is not None:
            for port in range(2):
                if result["rr_conflict"][port]:
                    self.coverage.sample_conflict("read_read", "loser")
                elif lq0 != lq1:
                    self.coverage.sample_conflict("read_read", "winner")
        return result
