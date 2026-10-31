"""Port-level environment for the MissQueue (MSHR array).

Calibrated timing on the generated RTL (kunminghu-v3 @ 893e1580):

* A request presented on `io_queryMQ_<port>.req` is accepted when the matching
  `ready` is high; the A-channel Acquire fires in the same cycle (primary path)
  or one cycle later (pipe-reg path).  The allocated MSHR id appears on
  `io_misstrack_alloc_<port>` one cycle after acceptance and is also used as
  the Acquire `source`.
* A 64B refill is two GrantData beats of 32B, D-channel `size=6`.  After the
  second beat `io_main_pipe_req` asks MainPipe to install the line, and
  `io_refill_info` returns the assembled line when MainPipe reports
  `s2_valid` for the same miss id.
* The entry is released when Finish has been acknowledged, MainPipe sends
  `main_pipe_resp` with `ack_miss_queue`, and `s3_refill_resp` is seen for the
  same miss id.
* `io_probe_block` / `io_replace_block` compare the block address and the
  hashed vaddr alias; they are only meaningful after the last refill beat.

Only public ports are used; the 512-bit refill line is modelled byte by byte.
"""
from __future__ import annotations

from .coverage import MissQueueCoverage

BLOCK_BYTES = 64
BEAT_BYTES = 32
MSHR_STORE = 1
LOAD_SOURCE = 0

TL_ACQUIRE_BLOCK = 6
TL_ACQUIRE_PERM = 7
TL_GRANT_DATA = 5
TL_CBO_ACK = 8
TL_CBO_CLEAN = 12
TL_CBO_FLUSH = 13
TL_CBO_INVAL = 14

M_XRD = 0
M_XWR = 1
M_XA_SWAP = 4
M_XA_ADD = 8


def dcache_alias(vaddr: int) -> int:
    """`get_alias(vaddr)` for the 64KB DCache (modeId=1)."""
    bit0 = 0
    bit1 = 0
    for i in range(12, 48, 2):
        bit0 ^= (vaddr >> i) & 1
        bit1 ^= (vaddr >> (i + 1)) & 1
    return bit0 | (bit1 << 1)


def block_addr(paddr: int) -> int:
    return paddr & ~(BLOCK_BYTES - 1)


def channel_of(paddr: int) -> int:
    return (block_addr(paddr) >> 6) & 1


def beat_pattern(base: int) -> int:
    return int.from_bytes(bytes(((base + i) & 0xFF) for i in range(BEAT_BYTES)),
                          "little")


def line_from_beats(beat0: int, beat1: int) -> int:
    return (beat0 & ((1 << 256) - 1)) | ((beat1 & ((1 << 256) - 1)) << 256)


def first(snapshots, key, value=1):
    for snap in snapshots:
        if snap.get(key) == value:
            return snap
    return None


class MissQueueEnv:
    def __init__(self, dut, coverage: MissQueueCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.mem_acquire = []
        self.mem_grant = []
        self.mem_finish = []
        for index in range(2):
            self.mem_acquire.append({
                "valid": getattr(dut, f"io_mem_acquire_{index}_valid"),
                "ready": getattr(dut, f"io_mem_acquire_{index}_ready"),
                "opcode": getattr(dut, f"io_mem_acquire_{index}_bits_opcode"),
                "param": getattr(dut, f"io_mem_acquire_{index}_bits_param"),
                "size": getattr(dut, f"io_mem_acquire_{index}_bits_size"),
                "source": getattr(dut, f"io_mem_acquire_{index}_bits_source"),
                "address": getattr(dut, f"io_mem_acquire_{index}_bits_address"),
                "alias": getattr(dut, f"io_mem_acquire_{index}_bits_user_alias"),
                "vaddr": getattr(dut, f"io_mem_acquire_{index}_bits_user_vaddr"),
                "req_source": getattr(dut, f"io_mem_acquire_{index}_bits_user_reqSource"),
                "need_hint": getattr(dut, f"io_mem_acquire_{index}_bits_user_needHint"),
            })
            self.mem_grant.append({
                "valid": getattr(dut, f"io_mem_grant_{index}_valid"),
                "ready": getattr(dut, f"io_mem_grant_{index}_ready"),
                "opcode": getattr(dut, f"io_mem_grant_{index}_bits_opcode"),
                "param": getattr(dut, f"io_mem_grant_{index}_bits_param"),
                "size": getattr(dut, f"io_mem_grant_{index}_bits_size"),
                "source": getattr(dut, f"io_mem_grant_{index}_bits_source"),
                "sink": getattr(dut, f"io_mem_grant_{index}_bits_sink"),
                "denied": getattr(dut, f"io_mem_grant_{index}_bits_denied"),
                "corrupt": getattr(dut, f"io_mem_grant_{index}_bits_corrupt"),
                "data": getattr(dut, f"io_mem_grant_{index}_bits_data"),
            })
            self.mem_finish.append({
                "valid": getattr(dut, f"io_mem_finish_{index}_valid"),
                "ready": getattr(dut, f"io_mem_finish_{index}_ready"),
                "sink": getattr(dut, f"io_mem_finish_{index}_bits_sink"),
            })
        self.query = []
        for port in range(4):
            prefix = f"io_queryMQ_{port}"
            self.query.append({
                "valid": getattr(dut, prefix + "_req_valid"),
                "ready": getattr(dut, prefix + "_ready"),
                "source": getattr(dut, prefix + "_req_bits_source"),
                "pf_source": getattr(dut, prefix + "_req_bits_pf_source")
                if hasattr(dut, prefix + "_req_bits_pf_source") else None,
                "cmd": getattr(dut, prefix + "_req_bits_cmd"),
                "addr": getattr(dut, prefix + "_req_bits_addr"),
                "vaddr": getattr(dut, prefix + "_req_bits_vaddr"),
                "alias": getattr(dut, prefix + "_req_bits_vaddrAlias"),
                "vaddr_set": getattr(dut, prefix + "_req_bits_vaddrSet"),
                "full_overwrite": getattr(dut, prefix + "_req_bits_full_overwrite")
                if hasattr(dut, prefix + "_req_bits_full_overwrite") else None,
                "word_idx": getattr(dut, prefix + "_req_bits_word_idx")
                if hasattr(dut, prefix + "_req_bits_word_idx") else None,
                "amo_data": getattr(dut, prefix + "_req_bits_amo_data")
                if hasattr(dut, prefix + "_req_bits_amo_data") else None,
                "amo_mask": getattr(dut, prefix + "_req_bits_amo_mask")
                if hasattr(dut, prefix + "_req_bits_amo_mask") else None,
                "amo_cmp": getattr(dut, prefix + "_req_bits_amo_cmp")
                if hasattr(dut, prefix + "_req_bits_amo_cmp") else None,
                "coh": getattr(dut, prefix + "_req_bits_req_coh_state"),
                "id": getattr(dut, prefix + "_req_bits_id"),
                "isBtoT": getattr(dut, prefix + "_req_bits_isBtoT")
                if hasattr(dut, prefix + "_req_bits_isBtoT") else None,
                "occupy_way": getattr(dut, prefix + "_req_bits_occupy_way")
                if hasattr(dut, prefix + "_req_bits_occupy_way") else None,
                "cancel": getattr(dut, prefix + "_req_bits_cancel")
                if hasattr(dut, prefix + "_req_bits_cancel") else None,
                "spec": getattr(dut, prefix + "_req_bits_isSpecMiss")
                if hasattr(dut, prefix + "_req_bits_isSpecMiss") else None,
                "store_data": getattr(dut, prefix + "_req_bits_store_data")
                if hasattr(dut, prefix + "_req_bits_store_data") else None,
                "store_mask": getattr(dut, prefix + "_req_bits_store_mask")
                if hasattr(dut, prefix + "_req_bits_store_mask") else None,
            })
        self.resp = []
        for port in range(1, 4):
            self.resp.append({
                "handled": getattr(dut, f"io_resp_{port}_handled"),
                "id": getattr(dut, f"io_resp_{port}_id"),
            })
        self.lq_empty = getattr(dut, "io_lqEmpty")
        # "no free MSHR entry" — the parent uses it to nack/replay new misses.
        self.full = getattr(dut, "io_full")
        self.alloc = []
        for port in range(4):
            self.alloc.append({
                "valid": getattr(dut, f"io_misstrack_alloc_{port}_valid"),
                "vaddr": getattr(dut, f"io_misstrack_alloc_{port}_bits_vaddr"),
                "paddr": getattr(dut, f"io_misstrack_alloc_{port}_bits_paddr"),
                "id": getattr(dut, f"io_misstrack_alloc_{port}_bits_mshr_id"),
            })
        self.main_pipe_req = {
            "valid": dut.io_main_pipe_req_valid,
            "ready": dut.io_main_pipe_req_ready,
            "miss_id": dut.io_main_pipe_req_bits_miss_id,
            "occupy_way": dut.io_main_pipe_req_bits_occupy_way,
            "source": dut.io_main_pipe_req_bits_source,
            "cmd": dut.io_main_pipe_req_bits_cmd,
            "vaddr": dut.io_main_pipe_req_bits_vaddr,
            "addr": dut.io_main_pipe_req_bits_addr,
            "word_idx": dut.io_main_pipe_req_bits_word_idx,
            "amo_data": dut.io_main_pipe_req_bits_amo_data,
            "amo_mask": dut.io_main_pipe_req_bits_amo_mask,
            "amo_cmp": dut.io_main_pipe_req_bits_amo_cmp,
            "pf_source": dut.io_main_pipe_req_bits_pf_source,
            "access": dut.io_main_pipe_req_bits_access,
            "id": dut.io_main_pipe_req_bits_id,
        }
        self.main_pipe_resp = {
            "valid": dut.io_main_pipe_resp_valid,
            "miss_id": dut.io_main_pipe_resp_bits_miss_id,
            "ack": dut.io_main_pipe_resp_bits_ack_miss_queue,
        }
        self.info = {
            "s2_valid": dut.io_mainpipe_info_s2_valid,
            "s2_miss_id": dut.io_mainpipe_info_s2_miss_id,
            "s2_replay": dut.io_mainpipe_info_s2_replay_to_mq,
            "s2_evict_btot": dut.io_mainpipe_info_s2_evict_BtoT_way,
            "s2_next_way": dut.io_mainpipe_info_s2_next_evict_way,
            "s3_valid": dut.io_mainpipe_info_s3_valid,
            "s3_miss_id": dut.io_mainpipe_info_s3_miss_id,
            "s3_refill_resp": dut.io_mainpipe_info_s3_refill_resp,
        }
        self.refill_info = {
            "valid": dut.io_refill_info_valid,
            "data": dut.io_refill_info_bits_store_data,
            "mask": dut.io_refill_info_bits_store_mask,
            "param": dut.io_refill_info_bits_miss_param,
            "denied": dut.io_refill_info_bits_error_tl_denied,
            "corrupt": dut.io_refill_info_bits_error_tl_corrupt,
            "latency": dut.io_refill_info_bits_refill_latency,
        }
        self.probe = {
            "addr": dut.io_probe_req_bits_addr,
            "vaddr": dut.io_probe_req_bits_vaddr,
            "block": dut.io_probe_block,
        }
        self.replace = {
            "addr": dut.io_replace_req_bits_addr,
            "vaddr": dut.io_replace_req_bits_vaddr,
            "block": dut.io_replace_block,
        }
        self.cmo = {
            "valid": dut.io_cmo_req_valid,
            "ready": dut.io_cmo_req_ready,
            "opcode": dut.io_cmo_req_bits_opcode,
            "address": dut.io_cmo_req_bits_address,
            "resp_valid": dut.io_cmo_resp_valid,
            "resp_denied": dut.io_cmo_resp_bits_denied,
            "resp_corrupt": dut.io_cmo_resp_bits_corrupt,
            "resp_ready": dut.io_cmo_resp_ready,
        }
        self.wbq_block = [getattr(dut, f"io_wbq_block_miss_req_{index}")
                          for index in range(4)]
        self.mshr_store_empty = dut.io_mshr_store_empty
        self.transactions = 0

    @staticmethod
    def _val(signal) -> int:
        return int(signal.value)

    def refresh(self) -> None:
        self.dut.xclock.RefreshComb()

    def _idle(self) -> None:
        for port in self.query:
            port["valid"].Set(0)
        self.cmo["valid"].Set(0)
        for grant in self.mem_grant:
            grant["valid"].Set(0)
        self.main_pipe_resp["valid"].Set(0)
        for signal in self.wbq_block:
            signal.Set(0)
        self.info["s2_valid"].Set(0)
        self.info["s3_valid"].Set(0)
        self.info["s3_refill_resp"].Set(0)
        self.lq_empty.Set(1)

    def reset(self) -> None:
        self._idle()
        self.probe["addr"].Set(0)
        self.probe["vaddr"].Set(0)
        self.replace["addr"].Set(0)
        self.replace["vaddr"].Set(0)
        self.info["s2_miss_id"].Set(0)
        self.info["s3_miss_id"].Set(0)
        self.main_pipe_resp["miss_id"].Set(0)
        self.main_pipe_resp["ack"].Set(0)
        self.main_pipe_req["ready"].Set(1)
        self.cmo["resp_ready"].Set(1)
        for index in range(2):
            self.mem_acquire[index]["ready"].Set(1)
            self.mem_finish[index]["ready"].Set(1)
        self.dut.reset.Set(1)
        self.dut.Step(4)
        self.dut.reset.Set(0)
        self.dut.Step(2)

    def snapshot(self) -> dict:
        v = self._val
        snap = {
            "acquire": [],
            "grant_ready": [],
            "finish": [],
            "query_ready": [],
            "resp": [],
            "alloc": [],
            "main_pipe_req": v(self.main_pipe_req["valid"]),
            "main_pipe_miss_id": v(self.main_pipe_req["miss_id"]),
            "main_pipe_addr": v(self.main_pipe_req["addr"]),
            "main_pipe_cmd": v(self.main_pipe_req["cmd"]),
            "main_pipe_source": v(self.main_pipe_req["source"]),
            "main_pipe_occupy": v(self.main_pipe_req["occupy_way"]),
            "refill_info": v(self.refill_info["valid"]),
            "refill_data": v(self.refill_info["data"]),
            "refill_mask": v(self.refill_info["mask"]),
            "refill_param": v(self.refill_info["param"]),
            "refill_denied": v(self.refill_info["denied"]),
            "refill_corrupt": v(self.refill_info["corrupt"]),
            "probe_block": v(self.probe["block"]),
            "replace_block": v(self.replace["block"]),
            "cmo_ready": v(self.cmo["ready"]),
            "cmo_resp": v(self.cmo["resp_valid"]),
            "cmo_denied": v(self.cmo["resp_denied"]),
            "cmo_corrupt": v(self.cmo["resp_corrupt"]),
            "mshr_store_empty": v(self.mshr_store_empty),
        }
        for index in range(2):
            acq = self.mem_acquire[index]
            snap["acquire"].append({
                "valid": v(acq["valid"]), "opcode": v(acq["opcode"]),
                "param": v(acq["param"]), "size": v(acq["size"]),
                "source": v(acq["source"]), "address": v(acq["address"]),
                "alias": v(acq["alias"]), "vaddr": v(acq["vaddr"]),
                "req_source": v(acq["req_source"]),
            })
            snap["grant_ready"].append(v(self.mem_grant[index]["ready"]))
            snap["finish"].append({
                "valid": v(self.mem_finish[index]["valid"]),
                "sink": v(self.mem_finish[index]["sink"]),
            })
        for port in self.query:
            snap["query_ready"].append(v(port["ready"]))
        for port in self.resp:
            snap["resp"].append({"handled": v(port["handled"]),
                                 "id": v(port["id"])})
        for port in self.alloc:
            snap["alloc"].append({"valid": v(port["valid"]),
                                  "vaddr": v(port["vaddr"]),
                                  "paddr": v(port["paddr"]),
                                  "id": v(port["id"])})
        return snap

    def run(self, cycles: int = 1) -> list[dict]:
        snaps = []
        for _ in range(cycles):
            self.refresh()
            self.dut.Step(1)
            snaps.append(self.snapshot())
        return snaps

    # ------------------------------------------------------------------ enqueue
    def enqueue(self, *, port: int = 0, paddr: int, vaddr: int,
                cmd: int = M_XRD, source: int = LOAD_SOURCE, req_id: int = 0,
                store_data: int = 0, store_mask: int = 0,
                full_overwrite: bool = False, is_btot: bool = False,
                occupy_way: int = 0, coh: int = 0, alias: int | None = None,
                wbq_block: int = 0, cycles: int = 3) -> list[dict]:
        self._idle()
        self.set_wbq_block(wbq_block)
        entry = self.query[port]
        entry["valid"].Set(1)
        entry["source"].Set(source)
        entry["cmd"].Set(cmd)
        entry["addr"].Set(paddr)
        entry["vaddr"].Set(vaddr)
        entry["alias"].Set(dcache_alias(vaddr) if alias is None else alias)
        entry["vaddr_set"].Set((vaddr >> 6) & 0x3F)
        entry["coh"].Set(coh)
        entry["id"].Set(req_id)
        entry["isBtoT"].Set(1 if is_btot else 0)
        entry["occupy_way"].Set(occupy_way)
        if entry["store_data"] is not None:
            entry["store_data"].Set(store_data)
            entry["store_mask"].Set(store_mask)
            entry["full_overwrite"].Set(1 if full_overwrite else 0)
        snaps = self.run(1)
        entry["valid"].Set(0)
        snaps += self.run(cycles - 1)
        self.transactions += 1
        if self.coverage is not None:
            channel = channel_of(paddr)
            for snap in snaps:
                if snap["acquire"][channel]["valid"]:
                    self.coverage.sample_alloc(cmd, full_overwrite, channel, port)
                    break
        return snaps

    def enqueue_parallel(self, requests: list[dict], *,
                         cycles: int = 3) -> list[dict]:
        """Present several requests on different ports in the same cycle."""
        self._idle()
        for request in requests:
            port = request["port"]
            entry = self.query[port]
            entry["valid"].Set(1)
            entry["source"].Set(request.get("source", LOAD_SOURCE))
            entry["cmd"].Set(request.get("cmd", M_XRD))
            entry["addr"].Set(request["paddr"])
            entry["vaddr"].Set(request["vaddr"])
            entry["alias"].Set(request.get("alias", dcache_alias(request["vaddr"])))
            entry["vaddr_set"].Set((request["vaddr"] >> 6) & 0x3F)
            entry["coh"].Set(request.get("coh", 0))
            entry["id"].Set(request.get("req_id", 0))
            if entry["store_data"] is not None and "store_data" in request:
                entry["store_data"].Set(request["store_data"])
                entry["store_mask"].Set(request["store_mask"])
                entry["full_overwrite"].Set(1 if request.get("full_overwrite") else 0)
        snaps = self.run(1)
        for request in requests:
            self.query[request["port"]]["valid"].Set(0)
        snaps += self.run(cycles - 1)
        return snaps

    def set_wbq_block(self, mask: int) -> None:
        for index, signal in enumerate(self.wbq_block):
            signal.Set((mask >> index) & 1)

    def mainpipe_feedback(self, *, miss_id: int, replay: bool = False,
                          evict_btot: bool = False,
                          next_way: int = 0, cycles: int = 1) -> list[dict]:
        self.info["s2_valid"].Set(1)
        self.info["s2_miss_id"].Set(miss_id)
        self.info["s2_replay"].Set(1 if replay else 0)
        self.info["s2_evict_btot"].Set(1 if evict_btot else 0)
        self.info["s2_next_way"].Set(next_way)
        snaps = self.run(cycles)
        self.info["s2_valid"].Set(0)
        self.info["s2_replay"].Set(0)
        self.info["s2_evict_btot"].Set(0)
        return snaps

    # ------------------------------------------------------------------- refill
    def refill(self, *, miss_id: int, beat0: int, beat1: int,
               denied: bool = False, corrupt: bool = False,
               channel: int = 0, sink: int = 7, param: int = 1,
               cycles: int = 5) -> list[dict]:
        """Drive two GrantData beats and capture install/refill_info."""
        snaps = []
        for index in range(2):
            for gr in self.mem_grant:
                gr["valid"].Set(0)
            grant = self.mem_grant[channel]
            grant["valid"].Set(1)
            grant["opcode"].Set(TL_GRANT_DATA)
            grant["param"].Set(param)
            grant["size"].Set(6)
            grant["source"].Set(miss_id)
            grant["sink"].Set(sink)
            grant["denied"].Set(1 if denied else 0)
            grant["corrupt"].Set(1 if corrupt else 0)
            grant["data"].Set(beat0 if index == 0 else beat1)
            self.refresh()
            if not self._val(grant["ready"]):
                raise AssertionError(
                    f"refill beat {index}: D channel not ready "
                    f"(miss_id={miss_id}, channel={channel})")
            snaps += self.run(1)
        for gr in self.mem_grant:
            gr["valid"].Set(0)
        # MainPipe sees S2 for this miss id while the entry still holds data.
        self.info["s2_valid"].Set(1)
        self.info["s2_miss_id"].Set(miss_id)
        snaps += self.run(cycles)
        self.info["s2_valid"].Set(0)
        return snaps

    # ----------------------------------------------------------------- complete
    def complete(self, *, miss_id: int, idle: int = 10) -> list[dict]:
        self.info["s3_valid"].Set(1)
        self.info["s3_miss_id"].Set(miss_id)
        self.info["s3_refill_resp"].Set(1)
        self.main_pipe_resp["valid"].Set(1)
        self.main_pipe_resp["miss_id"].Set(miss_id)
        self.main_pipe_resp["ack"].Set(1)
        snaps = self.run(1)
        self.info["s3_valid"].Set(0)
        self.info["s3_refill_resp"].Set(0)
        self.main_pipe_resp["valid"].Set(0)
        snaps += self.run(idle)
        return snaps

    # -------------------------------------------------------------------- probe
    def check_block(self, *, paddr: int, vaddr: int) -> dict:
        self.probe["addr"].Set(paddr)
        self.probe["vaddr"].Set(vaddr)
        self.replace["addr"].Set(paddr)
        self.replace["vaddr"].Set(vaddr)
        self.refresh()
        return self.snapshot()

    # ---------------------------------------------------------------------- cmo
    def cmo_request(self, *, opcode: int, address: int, denied: bool = False,
                    corrupt: bool = False, channel: int | None = None,
                    cycles: int = 6) -> dict:
        self._idle()
        self.cmo["valid"].Set(1)
        self.cmo["opcode"].Set(opcode)
        self.cmo["address"].Set(address)
        self.refresh()
        ready = self.snapshot()
        accepted = self.run(1)[0]
        self.cmo["valid"].Set(0)
        self.refresh()
        issued = self.snapshot()
        if channel is None:
            channel = channel_of(address)
        self.run(1)  # A fires, CMO unit advances to s_wresp
        grant = self.mem_grant[channel]
        grant["valid"].Set(1)
        grant["opcode"].Set(TL_CBO_ACK)
        grant["size"].Set(6)
        grant["source"].Set(0)
        grant["sink"].Set(0)
        grant["denied"].Set(1 if denied else 0)
        grant["corrupt"].Set(1 if corrupt else 0)
        grant["data"].Set(0)
        response = None
        for _ in range(cycles):
            snap = self.run(1)[0]
            if snap["cmo_resp"] and response is None:
                response = snap
            grant["valid"].Set(0)
        return {"ready": ready, "accepted": accepted, "issued": issued,
                "response": response, "channel": channel}
