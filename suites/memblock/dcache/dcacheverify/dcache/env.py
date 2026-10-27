"""Environment helpers for the integrated DCache top-level UT.

The generated DCache contains tag/meta SRAMs whose reset clears all 256 sets in
256 cycles; every test must first let that sweep finish. A load is driven in S0
and its response fields are only meaningful in S2 (two cycles after acceptance).
A refill is answered on the L2 D channel with two GrantData beats of size 6.
"""
from __future__ import annotations

from .coverage import DCacheCoverage

SWEEP_CYCLES = 300
GRANT_DATA = 5
GRANT_SIZE = 6
BEATS = 2


class DcacheEnv:
    def __init__(self, dut, coverage: DCacheCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.channels = []
        for index in range(2):
            prefix = f"auto_client_nodes_out_{index}"
            self.channels.append({
                "a_valid": getattr(dut, prefix + "_a_valid"),
                "a_ready": getattr(dut, prefix + "_a_ready"),
                "a_opcode": getattr(dut, prefix + "_a_bits_opcode"),
                "a_param": getattr(dut, prefix + "_a_bits_param"),
                "a_size": getattr(dut, prefix + "_a_bits_size"),
                "a_source": getattr(dut, prefix + "_a_bits_source"),
                "a_address": getattr(dut, prefix + "_a_bits_address"),
                "b_valid": getattr(dut, prefix + "_b_valid"),
                "b_ready": getattr(dut, prefix + "_b_ready"),
                "b_param": getattr(dut, prefix + "_b_bits_param"),
                "b_address": getattr(dut, prefix + "_b_bits_address"),
                "b_data": getattr(dut, prefix + "_b_bits_data"),
                "c_valid": getattr(dut, prefix + "_c_valid"),
                "c_ready": getattr(dut, prefix + "_c_ready"),
                "c_opcode": getattr(dut, prefix + "_c_bits_opcode"),
                "c_param": getattr(dut, prefix + "_c_bits_param"),
                "c_size": getattr(dut, prefix + "_c_bits_size"),
                "c_source": getattr(dut, prefix + "_c_bits_source"),
                "c_address": getattr(dut, prefix + "_c_bits_address"),
                "c_data": getattr(dut, prefix + "_c_bits_data"),
                "d_valid": getattr(dut, prefix + "_d_valid"),
                "d_ready": getattr(dut, prefix + "_d_ready"),
                "d_opcode": getattr(dut, prefix + "_d_bits_opcode"),
                "d_size": getattr(dut, prefix + "_d_bits_size"),
                "d_source": getattr(dut, prefix + "_d_bits_source"),
                "d_sink": getattr(dut, prefix + "_d_bits_sink"),
                "d_denied": getattr(dut, prefix + "_d_bits_denied"),
                "d_corrupt": getattr(dut, prefix + "_d_bits_corrupt"),
                "d_data": getattr(dut, prefix + "_d_bits_data"),
                "e_valid": getattr(dut, prefix + "_e_valid"),
                "e_ready": getattr(dut, prefix + "_e_ready"),
                "e_sink": getattr(dut, prefix + "_e_bits_sink"),
            })
        self.loads = []
        for lane in range(3):
            self.loads.append({
                "req_valid": getattr(dut, f"io_lsu_load_{lane}_req_valid"),
                "req_ready": getattr(dut, f"io_lsu_load_{lane}_req_ready"),
                "vaddr": getattr(dut, f"io_lsu_load_{lane}_req_bits_vaddr"),
                "vaddr_dup": getattr(dut, f"io_lsu_load_{lane}_req_bits_vaddr_dup"),
                "mask": getattr(dut, f"io_lsu_load_{lane}_req_bits_mask"),
                "cmd": getattr(dut, f"io_lsu_load_{lane}_req_bits_cmd"),
                "instrtype": getattr(dut, f"io_lsu_load_{lane}_req_bits_instrtype"),
                "lqidx": getattr(dut, f"io_lsu_load_{lane}_req_bits_lqIdx_value"),
                "s1_paddr_lsu": getattr(dut, f"io_lsu_load_{lane}_s1_paddr_dup_lsu"),
                "s1_paddr_dc": getattr(dut, f"io_lsu_load_{lane}_s1_paddr_dup_dcache"),
                "s1_kill": getattr(dut, f"io_lsu_load_{lane}_s1_kill"),
                "s2_kill": getattr(dut, f"io_lsu_load_{lane}_s2_kill"),
                "is128": getattr(dut, f"io_lsu_load_{lane}_is128Req"),
                "resp_data": getattr(dut, f"io_lsu_load_{lane}_resp_bits_data"),
                "resp_miss": getattr(dut, f"io_lsu_load_{lane}_resp_bits_miss"),
                "resp_handled": getattr(dut, f"io_lsu_load_{lane}_resp_bits_handled"),
                "resp_mshr": getattr(dut, f"io_lsu_load_{lane}_resp_bits_mshr_id"),
                # Hit line's stored prefetch source: 0 = demand, >1 = installed by
                # L1 prefetch and not yet cleared by a demand access.
                "resp_meta_prefetch": getattr(
                    dut, f"io_lsu_load_{lane}_resp_bits_meta_prefetch"),
                # "miss queue could not take this miss" — must agree with handled=0.
                "s2_mq_nack": getattr(dut, f"io_lsu_load_{lane}_s2_mq_nack"),
                # Only two wakeup ports exist at the DCache top (load 0/1).
                "wakeup_valid": (getattr(dut, f"io_lsu_loadWakeup_{lane}_valid")
                                 if lane < 2 else None),
                "wakeup_mshr": (getattr(dut, f"io_lsu_loadWakeup_{lane}_bits_mshrId")
                                if lane < 2 else None),
            })
        self.store = {
            "req_valid": dut.io_lsu_store_req_valid,
            "req_ready": dut.io_lsu_store_req_ready,
            "vaddr": dut.io_lsu_store_req_bits_vaddr,
            "addr": dut.io_lsu_store_req_bits_addr,
            "data": dut.io_lsu_store_req_bits_data,
            "mask": dut.io_lsu_store_req_bits_mask,
            "id": dut.io_lsu_store_req_bits_id,
            "hit_valid": dut.io_lsu_store_main_pipe_hit_resp_valid,
            "hit_id": dut.io_lsu_store_main_pipe_hit_resp_bits_id,
            "replay_valid": dut.io_lsu_store_replay_resp_valid,
            "replay_id": dut.io_lsu_store_replay_resp_bits_id,
        }
        self.atomics = {
            "req_valid": dut.io_lsu_atomics_req_valid,
            "req_ready": dut.io_lsu_atomics_req_ready,
            "cmd": dut.io_lsu_atomics_req_bits_cmd,
            "vaddr": dut.io_lsu_atomics_req_bits_vaddr,
            "addr": dut.io_lsu_atomics_req_bits_addr,
            "word_idx": dut.io_lsu_atomics_req_bits_word_idx,
            "amo_data": dut.io_lsu_atomics_req_bits_amo_data,
            "amo_mask": dut.io_lsu_atomics_req_bits_amo_mask,
            "amo_cmp": dut.io_lsu_atomics_req_bits_amo_cmp,
            "resp_valid": dut.io_lsu_atomics_resp_valid,
            "resp_data": dut.io_lsu_atomics_resp_bits_data,
            "resp_miss": dut.io_lsu_atomics_resp_bits_miss,
            "resp_replay": dut.io_lsu_atomics_resp_bits_replay,
            "resp_denied": dut.io_lsu_atomics_resp_bits_tl_error_tl_denied,
            "resp_corrupt": dut.io_lsu_atomics_resp_bits_tl_error_tl_corrupt,
            "resp_id": dut.io_lsu_atomics_resp_bits_id,
            "block_lr": dut.io_lsu_atomics_block_lr,
        }
        self.cmo = {
            "req_valid": dut.io_cmoOpReq_valid,
            "req_ready": dut.io_cmoOpReq_ready,
            "opcode": dut.io_cmoOpReq_bits_opcode,
            "address": dut.io_cmoOpReq_bits_address,
            "resp_valid": dut.io_cmoOpResp_valid,
            "resp_denied": dut.io_cmoOpResp_bits_denied,
            "resp_corrupt": dut.io_cmoOpResp_bits_corrupt,
            "resp_ready": dut.io_cmoOpResp_ready,
            "d_ready": [getattr(dut, f"auto_client_nodes_out_{i}_d_ready")
                        for i in range(2)],
        }
        self.error = {
            "valid": dut.io_error_valid,
            "paddr": dut.io_error_bits_paddr,
            "report": dut.io_error_bits_report_to_beu,
        }
        self.prefetch = {
            "valid": dut.io_prefetch_req_valid,
            "ready": dut.io_prefetch_req_ready,
            "paddr": dut.io_prefetch_req_bits_paddr,
            "vaddr": dut.io_prefetch_req_bits_vaddr,
            "pf_source": dut.io_prefetch_req_bits_pf_source_value,
        }
        self.lq_empty = dut.io_lqEmpty
        # "no store data pending inside the MSHR array" — used to prove a store
        # miss is really installed and then retired.
        self.mshr_store_empty = dut.io_mshr_store_empty
        self.pending_miss = None
        self.cycles = 0

    @staticmethod
    def _val(signal) -> int:
        return int(signal.value)

    def refresh(self) -> None:
        self.dut.xclock.RefreshComb()

    def _idle(self) -> None:
        for load in self.loads:
            load["req_valid"].Set(0)
            load["s1_kill"].Set(0)
            load["s2_kill"].Set(0)
            load["is128"].Set(0)
        self.store["req_valid"].Set(0)
        self.atomics["req_valid"].Set(0)
        self.cmo["req_valid"].Set(0)
        self.cmo["resp_ready"].Set(1)
        self.prefetch["valid"].Set(0)
        for channel in self.channels:
            channel["c_ready"].Set(0)

    def reset(self) -> None:
        self._idle()
        for index in range(2):
            channel = self.channels[index]
            # a_ready is held low except while service_miss is recording an
            # Acquire; b_ready/c_ready are DCache outputs and must not be driven.
            channel["a_ready"].Set(0)
            channel["e_ready"].Set(1)
            channel["d_valid"].Set(0)
        self.lq_empty.Set(1)
        self.dut.reset.Set(1)
        for _ in range(5):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        for _ in range(SWEEP_CYCLES):
            self.dut.Step(1)
        self.pending_miss = None

    # ---------------------------------------------------------------- loads
    def drive_load(self, lane: int, vaddr: int, paddr: int, mask: int = 0xFF,
                   cmd: int = 0, instrtype: int = 0, lqidx: int = 1) -> None:
        load = self.loads[lane]
        load["req_valid"].Set(1)
        load["vaddr"].Set(vaddr)
        load["vaddr_dup"].Set(vaddr)
        load["mask"].Set(mask)
        load["cmd"].Set(cmd)
        load["instrtype"].Set(instrtype)
        load["lqidx"].Set(lqidx)
        load["s1_paddr_lsu"].Set(paddr)
        load["s1_paddr_dc"].Set(paddr)

    def stop_load(self, lane: int) -> None:
        self.loads[lane]["req_valid"].Set(0)

    def load_response(self, lane: int) -> dict:
        load = self.loads[lane]
        return {
            "data": self._val(load["resp_data"]),
            "miss": self._val(load["resp_miss"]),
            "handled": self._val(load["resp_handled"]),
            "mshr": self._val(load["resp_mshr"]),
            "meta_prefetch": self._val(load["resp_meta_prefetch"]),
            "nack": self._val(load["s2_mq_nack"]),
        }

    def wait_load_accept(self, lane: int, limit: int = 8) -> bool:
        load = self.loads[lane]
        for _ in range(limit):
            if self._val(load["req_ready"]):
                return True
            self.dut.Step(1)
            self.refresh()
        return False

    def load_once(self, lane: int, vaddr: int, paddr: int, *, mask: int = 0xFF,
                  context: str = "load") -> dict:
        """Issue a load, wait for S2 and return its response fields."""
        self.drive_load(lane, vaddr, paddr, mask)
        if not self.wait_load_accept(lane):
            self.stop_load(lane)
            raise AssertionError(f"{context}: load not accepted")
        self.dut.Step(1)  # S0 fire
        self.stop_load(lane)
        # `s2_mq_nack` is a combinational S2 pulse, so OR it over the pipeline
        # rather than sampling one cycle and hoping to catch it.
        nack_any = 0
        for _ in range(1):
            self.dut.Step(1)
            self.refresh()
            nack_any |= self._val(self.loads[lane]["s2_mq_nack"])
        response = self.load_response(lane)
        response["nack_any"] = nack_any
        if self.coverage is not None:
            self.coverage.sample_load(context, mask, response)
        return response

    # ---------------------------------------------------------------- refill
    def service_miss(self, expected_addr: int | None = None, *,
                     data_beats: list[int] | None = None,
                     denied: bool = False, corrupt: bool = False,
                     context: str = "refill") -> dict:
        """Answer one pending AcquireBlock with two GrantData beats."""
        beats = data_beats or [0] * BEATS
        accepted = None
        for index, channel in enumerate(self.channels):
            channel["a_ready"].Set(1)
        for _ in range(16):
            for index, channel in enumerate(self.channels):
                if self._val(channel["a_valid"]) and self._val(channel["a_ready"]):
                    accepted = {
                        "channel": index,
                        "opcode": self._val(channel["a_opcode"]),
                        "param": self._val(channel["a_param"]),
                        "size": self._val(channel["a_size"]),
                        "source": self._val(channel["a_source"]),
                        "addr": self._val(channel["a_address"]),
                    }
                    break
            if accepted:
                break
            self.dut.Step(1)
            self.refresh()
        if accepted is None:
            raise AssertionError(f"{context}: no AcquireBlock observed")
        if expected_addr is not None and accepted["addr"] != expected_addr:
            raise AssertionError(
                f"{context}: Acquire addr {accepted['addr']:#x} != {expected_addr:#x}")
        if accepted["opcode"] not in (6, 7):
            raise AssertionError(f"{context}: unexpected Acquire opcode {accepted['opcode']}")
        channel = self.channels[accepted["channel"]]
        # Complete the A handshake before driving D: TileLink requires at least
        # one cycle between A and its response, and the MissQueue uses the A
        # fire cycle to arm its refill capture.
        channel["d_valid"].Set(0)
        self.dut.Step(1)
        self.refresh()
        for beat in range(BEATS):
            channel["d_valid"].Set(1)
            channel["d_opcode"].Set(GRANT_DATA)
            channel["d_size"].Set(GRANT_SIZE)
            channel["d_source"].Set(accepted["source"])
            channel["d_sink"].Set(0)
            channel["d_denied"].Set(1 if denied else 0)
            channel["d_corrupt"].Set(1 if corrupt else 0)
            channel["d_data"].Set(beats[beat] if beat < len(beats) else 0)
            self.dut.Step(1)
            if not self._val(channel["d_ready"]):
                raise AssertionError(f"{context}: D not ready for beat {beat}")
        channel["d_valid"].Set(0)
        for other in self.channels:
            other["a_ready"].Set(0)
        self.dut.Step(1)
        if self.coverage is not None:
            self.coverage.sample_refill(accepted, denied, corrupt)
        return accepted

    # ------------------------------------------------------------- prefetch
    def issue_prefetch(self, vaddr: int, paddr: int, pf_source: int = 2,
                       limit: int = 8) -> bool:
        """Hand one L1 hardware-prefetch request to MainPipe.

        `pf_source` 2/3/5 are the "from L1 prefetch" values
        (`isFromL1Prefetch(value) = value > L1_HW_PREFETCH_CLEAR`), so the refill
        installs the line with a non-zero prefetch flag.
        """
        self.prefetch["valid"].Set(1)
        self.prefetch["vaddr"].Set(vaddr)
        self.prefetch["paddr"].Set(paddr)
        self.prefetch["pf_source"].Set(pf_source)
        accepted = False
        for _ in range(limit):
            self.refresh()
            if self._val(self.prefetch["ready"]):
                accepted = True
                self.dut.Step(1)
                break
            self.dut.Step(1)
        self.prefetch["valid"].Set(0)
        self.refresh()
        return accepted

    def wait_wakeup(self, lane: int = 0, limit: int = 24, *,
                    optional: bool = False) -> bool:
        """Wait for a load-wakeup pulse; timeout fails closed unless `optional`."""
        signal = self.loads[lane]["wakeup_valid"]
        if signal is None:
            raise AssertionError(f"lane {lane} has no wakeup port")
        for _ in range(limit):
            if self._val(signal):
                return True
            self.dut.Step(1)
            self.refresh()
        if optional:
            return False
        raise AssertionError(f"lane {lane}: no wakeup within {limit} cycles")

    def see_wakeup(self, lane: int = 0) -> bool:
        signal = self.loads[lane]["wakeup_valid"]
        return bool(self._val(signal)) if signal is not None else True

    # ---------------------------------------------------------------- store
    def drive_store(self, vaddr: int, paddr: int, data: int, mask: int,
                    store_id: int = 1) -> None:
        self.store["req_valid"].Set(1)
        self.store["vaddr"].Set(vaddr)
        self.store["addr"].Set(paddr)
        self.store["data"].Set(data)
        self.store["mask"].Set(mask)
        self.store["id"].Set(store_id)

    def stop_store(self) -> None:
        self.store["req_valid"].Set(0)

    def wait_store_hit(self, limit: int = 10, *,
                       optional: bool = False) -> dict | None:
        """Wait for the store's Upd/Replay response.

        Timeouts fail closed: a store that never answers must not look like a
        response with all-zero fields.  `optional=True` is only for cases whose
        contract allows "no response" (assert the absence explicitly).
        """
        for _ in range(limit):
            if self._val(self.store["hit_valid"]) or self._val(self.store["replay_valid"]):
                result = {
                    "hit": self._val(self.store["hit_valid"]),
                    "hit_id": self._val(self.store["hit_id"]),
                    "replay": self._val(self.store["replay_valid"]),
                    "replay_id": self._val(self.store["replay_id"]),
                }
                if self.coverage is not None:
                    self.coverage.sample_store(result)
                return result
            self.dut.Step(1)
            self.refresh()
        if optional:
            return None
        raise AssertionError(
            f"store got no Upd/Replay response within {limit} cycles "
            f"(offered id={self._val(self.store['id'])}, "
            f"ready={self._val(self.store['req_ready'])})")

    # -------------------------------------------------------------- atomics
    def issue_atomic(self, vaddr: int, paddr: int, cmd: int, amo_data: int,
                     amo_mask: int = 0xFFFF, amo_cmp: int = 0,
                     word_idx: int = 0) -> bool:
        self.atomics["cmd"].Set(cmd)
        self.atomics["vaddr"].Set(vaddr)
        self.atomics["addr"].Set(paddr)
        self.atomics["word_idx"].Set(word_idx)
        self.atomics["amo_data"].Set(amo_data)
        self.atomics["amo_mask"].Set(amo_mask)
        self.atomics["amo_cmp"].Set(amo_cmp)
        self.atomics["req_valid"].Set(1)
        self.refresh()
        ready = bool(self._val(self.atomics["req_ready"]))
        self.dut.Step(1)
        self.refresh()
        self.atomics["req_valid"].Set(0)
        return ready

    def wait_atomic_response(self, limit: int = 24, *,
                             optional: bool = False) -> dict | None:
        """Wait for one AMO response; timeout fails closed unless `optional`."""
        for _ in range(limit):
            if self._val(self.atomics["resp_valid"]):
                return {
                    "data": self._val(self.atomics["resp_data"]),
                    "miss": self._val(self.atomics["resp_miss"]),
                    "replay": self._val(self.atomics["resp_replay"]),
                    "denied": self._val(self.atomics["resp_denied"]),
                    "corrupt": self._val(self.atomics["resp_corrupt"]),
                    "id": self._val(self.atomics["resp_id"]),
                }
            self.dut.Step(1)
            self.refresh()
        if optional:
            return None
        raise AssertionError(
            f"atomic got no response within {limit} cycles "
            f"(cmd={self._val(self.atomics['cmd'])}, "
            f"vaddr={self._val(self.atomics['vaddr']):#x})")

    # ------------------------------------------------------------------- CMO
    def issue_cmo(self, opcode: int, address: int, limit: int = 12) -> dict:
        self.cmo["opcode"].Set(opcode)
        self.cmo["address"].Set(address)
        self.cmo["req_valid"].Set(1)
        self.refresh()
        ready = bool(self._val(self.cmo["req_ready"]))
        self.dut.Step(1)
        self.refresh()
        self.cmo["req_valid"].Set(0)
        for channel in self.channels:
            channel["a_ready"].Set(1)
        accepted = None
        for _ in range(limit):
            for index, channel in enumerate(self.channels):
                if self._val(channel["a_valid"]):
                    accepted = {
                        "channel": index,
                        "opcode": self._val(channel["a_opcode"]),
                        "param": self._val(channel["a_param"]),
                        "size": self._val(channel["a_size"]),
                        "source": self._val(channel["a_source"]),
                        "address": self._val(channel["a_address"]),
                    }
            if accepted is not None:
                break
            self.dut.Step(1)
            self.refresh()
        if accepted is not None:
            # Complete the A handshake and let the CMO unit enter s_wresp.
            for channel in self.channels:
                channel["a_ready"].Set(1)
            self.dut.Step(1)
            self.refresh()
            for channel in self.channels:
                channel["a_ready"].Set(0)
        return {"ready": ready, "accepted": accepted}

    def complete_cmo(self, accepted: dict, denied: bool = False,
                     corrupt: bool = False, limit: int = 12, *,
                     optional: bool = False) -> dict | None:
        channel = self.channels[accepted["channel"]]
        channel["d_valid"].Set(1)
        channel["d_opcode"].Set(8)  # CBOAck
        channel["d_size"].Set(6)
        channel["d_source"].Set(0)
        channel["d_sink"].Set(0)
        channel["d_denied"].Set(1 if denied else 0)
        channel["d_corrupt"].Set(1 if corrupt else 0)
        channel["d_data"].Set(0)
        sent = False
        for _ in range(limit):
            self.refresh()
            if not sent and self._val(channel["d_ready"]):
                self.dut.Step(1)
                self.refresh()
                channel["d_valid"].Set(0)
                sent = True
            if self._val(self.cmo["resp_valid"]):
                response = {
                    "denied": self._val(self.cmo["resp_denied"]),
                    "corrupt": self._val(self.cmo["resp_corrupt"]),
                }
                channel["d_valid"].Set(0)
                self.dut.Step(1)
                self.refresh()
                return response
            self.dut.Step(1)
            self.refresh()
            if self._val(self.cmo["resp_valid"]):
                response = {
                    "denied": self._val(self.cmo["resp_denied"]),
                    "corrupt": self._val(self.cmo["resp_corrupt"]),
                }
                channel["d_valid"].Set(0)
                self.dut.Step(1)
                self.refresh()
                return response
        channel["d_valid"].Set(0)
        if optional:
            return None
        raise AssertionError(
            f"CMO got no response within {limit} cycles "
            f"(opcode={accepted['opcode']}, address={accepted['address']:#x})")

    def idle(self, cycles: int = 2) -> None:
        self._idle()
        for _ in range(cycles):
            self.dut.Step(1)
        self.refresh()
