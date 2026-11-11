"""Environment helpers for the integrated DCache top-level UT.

The generated DCache contains tag/meta SRAMs whose reset clears all 256 sets in
256 cycles; every test must first let that sweep finish. A load is driven in S0
and its response fields are only meaningful in S2 (two cycles after acceptance).
A refill is answered on the L2 D channel with two GrantData beats of size 6.
"""
from __future__ import annotations

from dataclasses import dataclass

from suites.memblock.dcache.testbenches.dcache.coverage import DCacheCoverage
from suites.memblock.dcache.testbenches.dcache.env.tilelink import LegacyL2Responder

SWEEP_CYCLES = 300
GRANT_DATA = 5
GRANT_SIZE = 6
BEATS = 2
ADDRESS_BITS = 48
SOURCE_BITS = 6
BLOCK_SIZE = 64
RELEASE_OPCODES = (6, 7)          # Release, ReleaseData
RELEASE_BEATS = {6: 1, 7: 2}      # accepted C beats per message
DATA_BEATS = {6: 0, 7: 2}         # data payloads: none / both halves of a line


@dataclass(frozen=True)
class ProbeResponse:
    """Immutable C-channel probe acknowledgement."""

    channel: int
    opcode: int
    param: int
    size: int
    address: int
    data: int


@dataclass(frozen=True)
class ProbeHandshake:
    """B-channel acceptance plus the C response observed for that probe."""

    accepted: bool
    b_ready_before: int
    cycles_to_accept: int
    response: ProbeResponse | None


@dataclass(frozen=True)
class ReleaseBeat:
    """Immutable observation of one offered C-channel beat.

    This is *only* an observation.  It carries no acceptance token, so it can
    never be used to acknowledge a release; ``wait_release`` returns a
    ``ReleaseMessage`` after the complete message has really fired.
    """

    channel: int
    opcode: int
    size: int
    source: int
    address: int


@dataclass(frozen=True)
class ReleaseMessage:
    """Complete, accepted C release identity.

    ``token`` is issued by the environment and registered only after every C
    beat of the message was accepted.  ``generation`` invalidates messages from
    an earlier reset.  Only this type may be acknowledged, and only once.
    """

    beat: ReleaseBeat
    beats: tuple[int, ...]        # data payloads; empty for a no-data Release
    param: int
    token: int
    generation: int

    @property
    def channel(self) -> int:
        return self.beat.channel

    @property
    def opcode(self) -> int:
        return self.beat.opcode

    @property
    def size(self) -> int:
        return self.beat.size

    @property
    def source(self) -> int:
        return self.beat.source

    @property
    def address(self) -> int:
        return self.beat.address


@dataclass(frozen=True)
class ErrorReport:
    """Immutable `io_error` snapshot for denied/corrupt refills."""

    valid: int
    paddr: int
    report: int



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
        self.last_refill = None
        self._release_generation = 0
        self._release_tokens: dict[int, ReleaseMessage] = {}
        self._acked_tokens: set[int] = set()
        self._release_token_seq = 0

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
        self.last_refill = None
        self._release_generation += 1
        self._release_tokens.clear()
        self._acked_tokens.clear()

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

    @staticmethod
    def _validate_lane(lane: int) -> None:
        if type(lane) is not int or not 0 <= lane < 3:
            raise ValueError(f"load lane must be 0..2: {lane!r}")

    def load_accept_ready(self, lane: int) -> bool:
        """Pre-edge ready for one load lane (a request may fire this cycle)."""
        self._validate_lane(lane)
        return bool(self._val(self.loads[lane]["req_ready"]))

    def load_nack_pulse(self, lane: int) -> bool:
        """Combinational S2 miss-queue nack pulse for one lane."""
        self._validate_lane(lane)
        return bool(self._val(self.loads[lane]["s2_mq_nack"]))

    def store_accept_ready(self) -> bool:
        """Pre-edge ready for the store request channel."""
        return bool(self._val(self.store["req_ready"]))

    def drive_lq_state(self, empty: bool) -> None:
        """Drive the parent-visible LQ-empty control input."""
        self.lq_empty.Set(1 if empty else 0)

    def mshr_store_empty_state(self) -> bool:
        """Whether the MSHR array currently holds no store data."""
        return bool(self._val(self.mshr_store_empty))

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
                      context: str = "refill", capture_c: bool = False,
                      grant_data: bool = True) -> dict:
        """Service exactly one recorded Acquire using pre-edge fire semantics.

        Both Grant and GrantData are legal AcquirePerm responses in this TL
        implementation. The no-data option exercises the full-overwrite path;
        a demand AcquireBlock must still receive two data beats.
        """
        self.last_refill=None
        responder=LegacyL2Responder(self.channels,self.dut.Step,self.refresh)
        self.last_refill=responder.run(expected_addr,
            tuple(data_beats) if data_beats is not None else (0,0),
            denied=denied,corrupt=corrupt,capture_c=capture_c,grant_data=grant_data)
        accepted=self.last_refill.acquire.legacy()
        if self.coverage is not None:
            self.coverage.sample_refill(accepted,denied,bool(corrupt or denied) if grant_data else False)
        return accepted

    def refill_with_releases(self,expected_addr,*,data_beats,context="refill/eviction"):
        """Return complete immutable C messages, not deduplicated first beats."""
        self.service_miss(expected_addr,data_beats=data_beats,context=context,capture_c=True)
        return self.last_refill

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

    # --------------------------------------------------------------- probe
    def transmit_probe(self, channel: int, address: int, param: int = 0,
                       need_data: bool = False, limit: int = 24) -> ProbeHandshake:
        """Offer one B-channel probe, hold it until B ready, then wait for C.

        The B payload is held unchanged across ready-low cycles.  The C fields
        are sampled before the edge that may consume them.  All domain checks
        run before the first pin write: channel 0/1, 48-bit line-aligned
        address, param 0..2 and a real bool ``need_data``.
        """
        if type(channel) is not int or channel not in (0, 1):
            raise ValueError(f"probe channel must be 0 or 1: {channel!r}")
        if type(address) is not int:
            raise TypeError(f"probe address must be an int: {address!r}")
        if not 0 <= address < (1 << ADDRESS_BITS):
            raise ValueError(
                f"probe address must be {ADDRESS_BITS}-bit: {address:#x}")
        if address & (BLOCK_SIZE - 1):
            raise ValueError(f"probe address must be cache-line aligned: {address:#x}")
        if type(param) is not int or param not in (0, 1, 2):
            raise ValueError(f"probe param must be 0..2: {param!r}")
        if type(need_data) is not bool:
            raise TypeError(f"probe need_data must be bool: {need_data!r}")
        if type(limit) is not int or limit < 1:
            raise ValueError(f"probe limit must be a positive int: {limit!r}")
        pins = self.channels[channel]
        pins["b_valid"].Set(1)
        pins["b_param"].Set(param)
        pins["b_address"].Set(address)
        pins["b_data"].Set(1 if need_data else 0)
        accept_cycles = 0
        ready_before = 0
        accepted = False
        for _ in range(8):
            self.refresh()
            ready_before = self._val(pins["b_ready"])
            if ready_before:
                self.dut.Step(1)
                accept_cycles += 1
                accepted = True
                break
            self.dut.Step(1)
            accept_cycles += 1
        pins["b_valid"].Set(0)
        response = None
        for _ in range(limit):
            self.refresh()
            if self._val(pins["c_valid"]):
                response = ProbeResponse(
                    channel=channel,
                    opcode=self._val(pins["c_opcode"]),
                    param=self._val(pins["c_param"]),
                    size=self._val(pins["c_size"]),
                    address=self._val(pins["c_address"]),
                    data=self._val(pins["c_data"]),
                )
                break
            self.dut.Step(1)
        return ProbeHandshake(accepted, ready_before, accept_cycles, response)

    # ------------------------------------------------------------- release
    def _ensure_release_state(self) -> None:
        """Lazy ledger for harnesses that construct the env without __init__."""
        if not hasattr(self, "_release_generation"):
            self._release_generation = 0
            self._release_tokens = {}
            self._acked_tokens = set()
            self._release_token_seq = 0

    def hold_release_channels(self, ready: bool) -> None:
        """Drive C-channel ready for both L2 channels (release backpressure)."""
        if type(ready) is not bool:
            raise TypeError(f"release ready must be bool: {ready!r}")
        for channel in self.channels:
            channel["c_ready"].Set(1 if ready else 0)

    def _read_c_beat(self, index: int) -> ReleaseBeat:
        channel = self.channels[index]
        return ReleaseBeat(
            channel=index,
            opcode=self._val(channel["c_opcode"]),
            size=self._val(channel["c_size"]),
            source=self._val(channel["c_source"]),
            address=self._val(channel["c_address"]),
        )

    def _require_c_signal(self, index: int, name: str):
        """A required C field must be really bound; never default it to zero."""
        signal = self.channels[index].get(name)
        if signal is None:
            raise AssertionError(
                f"channel {index}: required C field {name!r} is not bound; "
                "a missing field is not an observation of zero")
        return signal

    def _c_data(self, index: int) -> int:
        """Payload of a data-carrying beat; only ReleaseData needs it."""
        return self._val(self._require_c_signal(index, "c_data"))

    def _c_param(self, index: int) -> int:
        """C.param is part of every release header and is always required."""
        return self._val(self._require_c_signal(index, "c_param"))

    def _validate_release_header(self, beat: ReleaseBeat) -> None:
        if beat.opcode not in RELEASE_OPCODES:
            raise AssertionError(
                f"channel {beat.channel}: opcode {beat.opcode} is not Release/ReleaseData")
        if beat.size != 6:
            raise AssertionError(f"channel {beat.channel}: release size {beat.size} != 6")
        if not 0 <= beat.source < (1 << SOURCE_BITS):
            raise AssertionError(
                f"channel {beat.channel}: release source {beat.source} exceeds {SOURCE_BITS} bits")
        if not 0 <= beat.address < (1 << ADDRESS_BITS):
            raise AssertionError(
                f"channel {beat.channel}: release address {beat.address:#x} is not "
                f"{ADDRESS_BITS}-bit")
        if beat.address & (BLOCK_SIZE - 1):
            raise AssertionError(
                f"channel {beat.channel}: release address {beat.address:#x} is not "
                "cache-line aligned")

    def _release_header(self, index: int,
                        beat: ReleaseBeat) -> tuple[int, int, int, int, int, int]:
        return (beat.channel, beat.opcode, self._c_param(index), beat.size,
                beat.source, beat.address)

    def observe_release(self, limit: int = 24) -> tuple[ReleaseBeat, ...]:
        """Observe every currently offered C beat without accepting anything.

        When no beat is visible yet, the helper may advance up to ``limit``
        edges to reach the offer window; each advance closes C.ready first so an
        unregistered C transfer cannot be consumed inside this observation.
        An empty tuple means no C valid was seen in the window.  Observations are
        intentionally not acknowledgeable.
        """
        self._ensure_release_state()
        if type(limit) is not int or limit < 1:
            raise ValueError(f"observe limit must be a positive int: {limit!r}")
        for _ in range(limit):
            self.refresh()
            beats = tuple(self._read_c_beat(index)
                          for index, channel in enumerate(self.channels)
                          if self._val(channel["c_valid"]))
            if beats:
                return beats
            self._step_with_c_ready_closed()
        return ()

    def _step_with_c_ready_closed(self) -> None:
        """Advance one edge without consuming any offered C beat."""
        prior = [self._val(channel["c_ready"]) for channel in self.channels]
        for channel in self.channels:
            channel["c_ready"].Set(0)
        self.dut.Step(1)
        for channel, value in zip(self.channels, prior):
            channel["c_ready"].Set(value)
        self.refresh()

    def wait_release(self, limit: int = 24) -> ReleaseMessage | None:
        """Accept one complete Release (1 beat) or ReleaseData (2 beats).

        Readiness is sampled before each acceptance edge.  Only one channel is
        opened at a time; a simultaneously valid second channel is held at
        ready=0, so a single Step cannot consume an unregistered beat.  The
        overall ``limit`` is an edge budget shared with the message completion
        wait: after the first beat, an inter-beat bubble is legal and does not
        invent payload, but a message that never completes within the remaining
        budget fails instead of returning a zero-filled success.
        """
        self._ensure_release_state()
        if type(limit) is not int or limit < 1:
            raise ValueError(f"release limit must be a positive int: {limit!r}")
        spent = 0
        while spent < limit:
            self.refresh()
            candidates = []
            for index, channel in enumerate(self.channels):
                if not self._val(channel["c_valid"]):
                    continue
                beat = self._read_c_beat(index)
                if beat.opcode not in RELEASE_OPCODES:
                    continue
                if not self._val(channel["c_ready"]):
                    continue
                candidates.append((index, beat))
            if candidates:
                return self._accept_release(*candidates[0], budget=limit - spent)
            # Do not let an unrelated C valid+ready fire while searching.
            if any(self._val(channel["c_valid"]) and self._val(channel["c_ready"])
                   for channel in self.channels):
                self._step_with_c_ready_closed()
            else:
                self.dut.Step(1)
            spent += 1
        return None

    def _accept_release(self, index: int, first: ReleaseBeat, *,
                        budget: int) -> ReleaseMessage:
        """Complete one release message within ``budget`` edges.

        Only ``valid && ready`` beats are counted and only then are header and
        data sampled.  A legal zero-valid bubble between ReleaseData beats is
        waited out inside the same budget; a truncated message or a header
        change still fails.
        """
        self._validate_release_header(first)
        remaining = int(budget)
        if remaining < 1:
            raise AssertionError(
                f"channel {index}: no edge budget left to accept the first release beat")
        prior = [self._val(channel["c_ready"]) for channel in self.channels]
        for other, channel in enumerate(self.channels):
            channel["c_ready"].Set(1 if other == index else 0)
        try:
            count = RELEASE_BEATS[first.opcode]
            param = self._c_param(index)
            first_header = self._release_header(index, first)
            beats = [self._c_data(index)] if first.opcode == 7 else []
            accepted = 1
            remaining -= 1
            self.dut.Step(1)  # accept the first beat sampled by the caller
            while accepted < count:
                if remaining < 1:
                    raise AssertionError(
                        f"channel {index}: release message incomplete after "
                        f"{accepted}/{count} beat(s) within the edge budget")
                self.refresh()
                channel = self.channels[index]
                if not (self._val(channel["c_valid"]) and self._val(channel["c_ready"])):
                    # Bubble or backpressure: no payload is sampled and no beat
                    # is counted at this edge.
                    self.dut.Step(1)
                    remaining -= 1
                    continue
                beat = self._read_c_beat(index)
                header = self._release_header(index, beat)
                if header != first_header:
                    raise AssertionError(
                        f"channel {index}: release header changed mid-message: "
                        f"{first_header} -> {header}")
                accepted += 1
                if first.opcode == 7:
                    beats.append(self._c_data(index))
                self.dut.Step(1)
                remaining -= 1
            self._release_token_seq += 1
            message = ReleaseMessage(
                beat=first,
                beats=tuple(beats),
                param=param,
                token=self._release_token_seq,
                generation=self._release_generation,
            )
            self._release_tokens[message.token] = message
            return message
        finally:
            for channel, value in zip(self.channels, prior):
                channel["c_ready"].Set(value)
            self.refresh()

    def release_ack_ready(self, message: ReleaseMessage) -> bool:
        """Validate a release message without driving the D channel.

        Identity, not value equality, binds the message to this environment's
        ledger: two environments can accept byte-identical headers and both emit
        token 1 generation 0, and a copied/forged dataclass can repeat the same
        fields.  Only the registered object may be acknowledged, and only once.
        The original object may be retried after an ACK that did not complete.
        """
        self._ensure_release_state()
        if type(message) is not ReleaseMessage:
            raise TypeError(
                f"acknowledge_release requires an accepted ReleaseMessage: {message!r}")
        if message.generation != self._release_generation:
            raise AssertionError(
                f"release token {message.token} belongs to reset generation "
                f"{message.generation}, current {self._release_generation}")
        record = self._release_tokens.get(message.token)
        if record is None:
            raise AssertionError(
                f"release token {message.token} is not an accepted message in this environment")
        if record is not message:
            raise AssertionError(
                f"release token {message.token} was not issued by this environment "
                "(a different or copied message object cannot be acknowledged)")
        expected = DATA_BEATS.get(message.opcode)
        if expected is None or len(message.beats) != expected:
            raise AssertionError(
                f"release token {message.token}: {len(message.beats)} data beat(s) "
                f"for opcode {message.opcode}, expected {expected}")
        if message.token in self._acked_tokens:
            raise AssertionError(f"release token {message.token} was already acknowledged")
        return True

    def acknowledge_release(self, message: ReleaseMessage, limit: int = 8) -> bool:
        """Drive exactly one ReleaseAck for an accepted, unacknowledged message.

        Forged observations, wrong channel/source/header, messages from an old
        reset generation and repeated acknowledgements are rejected before any
        D pin is written.
        """
        self._ensure_release_state()
        if type(limit) is not int or limit < 1:
            raise ValueError(f"ack limit must be a positive int: {limit!r}")
        self.release_ack_ready(message)
        channel = self.channels[message.channel]
        channel["d_valid"].Set(1)
        channel["d_opcode"].Set(6)  # ReleaseAck
        channel["d_size"].Set(message.size)
        channel["d_source"].Set(message.source)
        channel["d_sink"].Set(0)
        channel["d_denied"].Set(0)
        channel["d_corrupt"].Set(0)
        channel["d_data"].Set(0)
        # The ACK edge must not consume any other offered C beat.
        prior_c_ready = [self._val(item["c_ready"]) for item in self.channels]
        for item in self.channels:
            item["c_ready"].Set(0)
        accepted = False
        try:
            for _ in range(limit):
                self.refresh()
                if self._val(channel["d_ready"]):
                    self.dut.Step(1)
                    accepted = True
                    break
                self.dut.Step(1)
        finally:
            channel["d_valid"].Set(0)
            for item, value in zip(self.channels, prior_c_ready):
                item["c_ready"].Set(value)
            self.refresh()
        if not accepted:
            raise AssertionError(
                f"channel {message.channel}: ReleaseAck for token {message.token} "
                f"was not accepted within {limit} cycles")
        self._acked_tokens.add(message.token)
        return True

    # --------------------------------------------------------------- error
    def _sample_error(self) -> ErrorReport:
        return ErrorReport(
            valid=self._val(self.error["valid"]),
            paddr=self._val(self.error["paddr"]),
            report=self._val(self.error["report"]),
        )

    def error_snapshot(self) -> ErrorReport:
        self.refresh()
        return self._sample_error()

    def wait_error(self, limit: int = 12) -> ErrorReport | None:
        """Step first and sample after the edge, for ``limit`` edges.

        This preserves the frozen observation window of the original loops:
        the report is inspected only after a clock edge, so an error asserted in
        the current cycle is seen after the same number of edges as before.
        """
        if type(limit) is not int or limit < 1:
            raise ValueError(f"error limit must be a positive int: {limit!r}")
        for _ in range(limit):
            self.dut.Step(1)
            self.refresh()
            report = self._sample_error()
            if report.valid:
                return report
        return None
