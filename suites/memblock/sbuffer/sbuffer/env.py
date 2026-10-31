"""Toffee environment for the Sbuffer top level.

Only public ports are driven and observed. The reference tracks physical-tag
lines and merged bytes; the DUT's slot id is matched to a unique live line by
payload, so PLRU slot choice is not asserted while payload correctness is.
"""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from .coverage import SbufferCoverage
from .model import BYTES, LANES, LINES, Enq, Line, SbufferModel, LANE_MASK


@dataclass
class ReqSnap:
    id: int
    addr: int
    vaddr: int
    mask: int
    data: int
    line: Line | None = None


class SbufferEnv:
    def __init__(self, dut, coverage: SbufferCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = SbufferModel()
        self.in_enqueue = [getattr(dut, f"io_in_req_{i}_valid") for i in range(2)]
        self.in_ready = [getattr(dut, f"io_in_req_{i}_ready") for i in range(2)]
        self.in_pins = [
            dict(
                vaddr=getattr(dut, f"io_in_req_{i}_bits_vaddr"),
                data=getattr(dut, f"io_in_req_{i}_bits_data"),
                mask=getattr(dut, f"io_in_req_{i}_bits_mask"),
                addr=getattr(dut, f"io_in_req_{i}_bits_addr"),
                wline=getattr(dut, f"io_in_req_{i}_bits_wline"),
            )
            for i in range(2)
        ]
        self.req_valid = getattr(dut, "io_dcache_req_valid")
        self.req_ready = getattr(dut, "io_dcache_req_ready")
        self.req_bits = dict(
            id=getattr(dut, "io_dcache_req_bits_id"),
            addr=getattr(dut, "io_dcache_req_bits_addr"),
            vaddr=getattr(dut, "io_dcache_req_bits_vaddr"),
            mask=getattr(dut, "io_dcache_req_bits_mask"),
            data=getattr(dut, "io_dcache_req_bits_data"),
        )
        self.hit_valid = getattr(dut, "io_dcache_main_pipe_hit_resp_valid")
        self.hit_id = getattr(dut, "io_dcache_main_pipe_hit_resp_bits_id")
        self.replay_valid = getattr(dut, "io_dcache_replay_resp_valid")
        self.replay_id = getattr(dut, "io_dcache_replay_resp_bits_id")
        self.sbempty = getattr(dut, "io_sbempty")
        self.sbfull = getattr(dut, "io_sbFull")
        self.flush_valid = getattr(dut, "io_flush_valid")
        self.flush_is_cmo = getattr(dut, "io_flush_isCmo")
        self.flush_empty = getattr(dut, "io_flush_empty")
        self.sqempty = getattr(dut, "io_sqempty")
        self.mshr_empty = getattr(dut, "io_mshr_store_empty")
        self.force_write = getattr(dut, "io_force_write")
        self.timeout = getattr(dut, "io_csrCtrl_sbuffer_timeout")
        self.fwd = [
            dict(
                s0_valid=getattr(dut, f"io_forward_{lane}_s0Req_valid"),
                s0_vaddr=getattr(dut, f"io_forward_{lane}_s0Req_bits_vaddr"),
                s1_paddr=getattr(dut, f"io_forward_{lane}_s1Req_paddr"),
                s1_kill=getattr(dut, f"io_forward_{lane}_s1Kill"),
                s2_valid=getattr(dut, f"io_forward_{lane}_s2Resp_valid"),
                s2_invalid=getattr(dut, f"io_forward_{lane}_s2Resp_bits_matchInvalid"),
                s2_mask=[getattr(dut, f"io_forward_{lane}_s2Resp_bits_forwardMask_{bit}") for bit in range(16)],
                s2_data=[getattr(dut, f"io_forward_{lane}_s2Resp_bits_forwardData_{byte}") for byte in range(16)],
            )
            for lane in range(3)
        ]
        self.tick = 0

    # ------------------------------------------------------------------ basics
    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def settle(self, cycles: int = 2) -> None:
        for _ in range(cycles):
            await self.edge()

    async def reset(self, context: str = "idle") -> None:
        self.dut.reset.Set(1)
        await self.edge()
        self.dut.reset.Set(1)
        await self.edge()
        self.model.reset()
        self.dut.reset.Set(0)
        await self.edge()
        assert self.read(self.sbempty) == 1, "sbempty must be 1 after reset"
        assert self.read(self.sbfull) == 0, "sbFull must be 0 after reset"
        assert self.read(self.req_valid) == 0, "no dcache request after reset"
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    # ------------------------------------------------------------------ enqueue
    def _predict_ready(self, reqs: list[Enq]) -> list[int]:
        if self.model.uarch_drain:
            return [0] * len(reqs)
        readys = []
        lines = len(self.model.lines)
        for index, req in enumerate(reqs):
            merge = self.model.can_merge(req.ptag)
            if index == 0:
                can = merge or lines < LINES
            else:
                same_fresh_slot = (
                    req.ptag == reqs[0].ptag
                    and not self.model.can_merge(reqs[0].ptag)
                    and readys[0] == 1
                )
                can = merge or same_fresh_slot or lines + index < LINES
            readys.append(1 if can else 0)
        return readys

    async def enqueue(
        self, reqs: list[Enq], expect_ready=None, note: str = "", ports=None
    ) -> list[int]:
        if len(reqs) > 2:
            raise ValueError("Sbuffer has two enqueue ports")
        if ports is None:
            ports = tuple(range(len(reqs)))
        if len(ports) != len(reqs):
            raise ValueError("ports and enqueue requests length differ")
        before = len(self.model.lines)
        targets = [self.model.active_same_tag(req.ptag) for req in reqs]
        for port in range(2):
            self.in_enqueue[port].Set(0)
        for port, req in zip(ports, reqs):
            self.in_enqueue[port].Set(1)
            self.in_pins[port]["vaddr"].Set(req.vaddr)
            self.in_pins[port]["addr"].Set(req.addr)
            self.in_pins[port]["mask"].Set(req.mask)
            self.in_pins[port]["data"].Set(req.data)
            self.in_pins[port]["wline"].Set(1 if req.wline else 0)
        self.dut.RefreshComb()
        actual = {port: self.read(self.in_ready[port]) for port in range(2)}
        accepted = [req for port, req in zip(ports, reqs) if actual[port]]
        if expect_ready is not None:
            wanted = list(expect_ready)
            observed = [actual[port] for port in ports]
            assert observed == wanted, f"{note}: ready {observed} != expected {wanted}"
        else:
            for port, req in zip(ports, reqs):
                if req.ptag in {line.ptag for line in self.model.lines if not line.inflight}:
                    assert actual[port] == 1, f"{note}: merge on port {port} must be ready"
        await self.edge()
        for port in range(2):
            self.in_enqueue[port].Set(0)
        self.model.enqueue(accepted)

        if self.coverage is not None:
            if not accepted:
                kind = "blocked_drain" if self.model.uarch_drain else "blocked_full"
                self.coverage.sample_enqueue(kind, [])
            elif len(accepted) == 2:
                kind = "same_cycle_same_tag" if accepted[0].ptag == accepted[1].ptag else "same_cycle_diff_tags"
                lanes = {accepted[0].lane, accepted[1].lane}
                self.coverage.sample_enqueue(kind, sorted(lanes))
                self.coverage.sample_capacity("not_full")
            else:
                req = accepted[0]
                target = targets[0]
                if target is None:
                    kind = "new_line"
                elif target.vtag == req.vtag:
                    kind = "merge_same_vtag"
                else:
                    kind = "merge_diff_vtag"
                lanes = list(range(LANES)) if req.wline else [req.lane]
                inflight_same = any(
                    line.ptag == req.ptag and line.inflight for line in self.model.lines
                )
                self.coverage.sample_enqueue(kind, lanes)
                self.coverage.sample_capacity("not_full")
                if inflight_same:
                    self.coverage.sample_sameblock("allocate_while_inflight")
        return actual

    # ------------------------------------------------------------------ requests
    def read_req(self) -> ReqSnap:
        return ReqSnap(
            id=self.read(self.req_bits["id"]),
            addr=self.read(self.req_bits["addr"]),
            vaddr=self.read(self.req_bits["vaddr"]),
            mask=self.read(self.req_bits["mask"]),
            data=self.read(self.req_bits["data"]),
        )

    def _matches(self, snap: ReqSnap) -> list[Line]:
        ptag = snap.addr >> 6
        vtag = snap.vaddr >> 6
        matches = []
        for line in self.model.lines:
            if line.ptag != ptag or line.vtag != vtag or line.line_mask() != snap.mask:
                continue
            ok = True
            for lane in range(LANES):
                for byte in range(BYTES):
                    if not (snap.mask >> (16 * lane + byte)) & 1:
                        continue
                    got = (snap.data >> (8 * (16 * lane + byte))) & 0xFF
                    if line.data[lane][byte] != got:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                matches.append(line)
        return matches

    def verify_req(self, snap: ReqSnap, note: str = "") -> Line:
        assert 0 <= snap.id < LINES, f"{note}: request id {snap.id} outside 16 lines"
        matches = self._matches(snap)
        assert len(matches) == 1, (
            f"{note}: request payload (ptag={snap.addr >> 6}, vtag={snap.vaddr >> 6}, "
            f"mask={snap.mask:#018x}) matched {len(matches)} live lines"
        )
        line = matches[0]
        assert not line.inflight, f"{note}: request selected an already inflight line"
        inflight_tags = {item.ptag for item in self.model.lines if item.inflight}
        assert line.ptag not in inflight_tags, f"{note}: same block still inflight"
        snap.line = line
        return line

    async def wait_req(
        self, note: str = "", max_cycles: int = 40, allow_inflight: bool = False
    ) -> ReqSnap:
        for _ in range(max_cycles):
            await self.edge()
            if self.read(self.req_valid):
                snap = self.read_req()
                if allow_inflight:
                    matches = self._matches(snap)
                    assert len(matches) == 1, f"{note}: request payload matched {len(matches)} lines"
                    snap.line = matches[0]
                else:
                    self.verify_req(snap, note)
                return snap
        raise TimeoutError(f"{note}: no dcache request within {max_cycles} cycles")

    async def no_req_for(self, cycles: int, note: str = "") -> None:
        for _ in range(cycles):
            await self.edge()
            assert self.read(self.req_valid) == 0, f"{note}: unexpected dcache request"

    async def accept(self, snap: ReqSnap, reason: str) -> None:
        self.req_ready.Set(1)
        await self.edge()
        self.req_ready.Set(0)
        self.model.mark_inflight(snap.line)
        if self.coverage is not None:
            lanes = [lane for lane in range(LANES) if (snap.mask >> (16 * lane)) & 0xFFFF]
            self.coverage.sample_request(reason, lanes or [0])

    async def hit(self, snap: ReqSnap) -> None:
        self.hit_id.Set(snap.id)
        self.hit_valid.Set(1)
        await self.edge()
        self.hit_valid.Set(0)
        self.model.on_hit(snap.line)

    async def replay(self, snap: ReqSnap) -> None:
        self.replay_id.Set(snap.id)
        self.replay_valid.Set(1)
        await self.edge()
        self.replay_valid.Set(0)
        self.model.on_replay(snap.line)
        if self.coverage is not None:
            self.coverage.sample_replay("replay_resp")

    # ------------------------------------------------------------------ forward
    async def forward(self, load_lane: int, vaddr: int, paddr: int, kill: bool = False) -> dict:
        pins = self.fwd[load_lane]
        pins["s0_vaddr"].Set(vaddr)
        pins["s0_valid"].Set(1)
        await self.edge()
        pins["s0_valid"].Set(0)
        pins["s1_paddr"].Set(paddr)
        pins["s1_kill"].Set(1 if kill else 0)
        await self.edge()
        pins["s1_kill"].Set(0)
        assert self.read(pins["s2_valid"]) == 1, "forward response valid must be one cycle after s1"
        mask = 0
        data = []
        for byte in range(16):
            bit = self.read(pins["s2_mask"][byte]) & 1
            mask |= bit << byte
            data.append(self.read(pins["s2_data"][byte]) & 0xFF)
        invalid = self.read(pins["s2_invalid"]) & 1
        expected_mask, expected_data, mismatch = self.model.forward(vaddr, paddr)
        lane = (paddr >> 4) & LANE_MASK
        if kill:
            assert invalid == 0, "kill must suppress matchInvalid"
        else:
            assert invalid == int(mismatch), (
                f"forward matchInvalid {invalid} != expected {int(mismatch)}"
            )
        assert mask == expected_mask, (
            f"forward mask {mask:#06x} != expected {expected_mask:#06x} (lane {lane})"
        )
        for byte in range(16):
            if (expected_mask >> byte) & 1:
                assert data[byte] == expected_data[byte], (
                    f"forward byte {byte} {data[byte]:#04x} != {expected_data[byte]:#04x}"
                )
        if self.coverage is not None:
            active = any(
                line.vtag == vaddr >> 6 and not line.inflight for line in self.model.lines
            )
            inflight = any(
                line.vtag == vaddr >> 6 and line.inflight for line in self.model.lines
            )
            if kill:
                result = "killed"
            elif mismatch and expected_mask:
                result = "mismatch_ptag"
            elif mismatch:
                result = "mismatch_vtag"
            elif expected_mask == 0:
                result = "no_match"
            elif active and inflight:
                result = "active_over_inflight"
            elif active:
                result = "active"
            else:
                result = "inflight"
            self.coverage.sample_forward(result, load_lane, lane)
        return dict(mask=mask, data=data, invalid=invalid, expected_mask=expected_mask)

    # ------------------------------------------------------------------ flush/drain
    async def start_flush(self, cmo: bool = False, sqempty: int = 1, mshr: int = 1) -> None:
        self.sqempty.Set(sqempty)
        self.mshr_empty.Set(mshr)
        self.flush_is_cmo.Set(1 if cmo else 0)
        self.flush_valid.Set(1)
        await self.edge()

    async def drain_requests(self, reason: str, max_cycles: int = 200, require_increasing: bool = True) -> list[ReqSnap]:
        drained = []
        last_id = -1
        for _ in range(max_cycles):
            await self.edge()
            if self.read(self.req_valid):
                snap = self.read_req()
                self.verify_req(snap, reason)
                if require_increasing:
                    assert snap.id > last_id, f"{reason}: drain ids not increasing: {snap.id} after {last_id}"
                    last_id = snap.id
                await self.accept(snap, reason)
                await self.hit(snap)
                drained.append(snap)
                continue
            if not self.model.lines:
                break
        return drained

    async def flush_and_finish(
        self, cmo: bool = False, sqempty: int = 1, mshr: int = 1, expect_empty: bool = True
    ) -> list[ReqSnap]:
        await self.start_flush(cmo=cmo, sqempty=sqempty, mshr=mshr)
        drained = await self.drain_requests("drain_flush")
        await self.settle(3)
        if self.coverage is not None:
            self.coverage.sample_flush(
                "cmo" if cmo else "normal",
                "cmo_ignores_sq" if cmo else "normal_after_all",
            )
        if expect_empty:
            assert self.read(self.flush_empty) == 1, "flush.empty must be 1 after drain"
        self.flush_valid.Set(0)
        await self.edge()
        return drained

    async def drain_uarch(self) -> list[ReqSnap]:
        drained = []
        last_id = -1
        for _ in range(100):
            await self.edge()
            if self.read(self.req_valid):
                snap = self.read_req()
                self.verify_req(snap, "drain_uarch")
                assert snap.id > last_id, "uarch drain ids must increase"
                last_id = snap.id
                await self.accept(snap, "drain_uarch")
                await self.hit(snap)
                drained.append(snap)
                continue
            if not self.model.lines:
                break
        await self.settle(3)
        if self.coverage is not None:
            self.coverage.sample_flush("uarch", "normal_after_all")
        self.model.uarch_drain = False
        return drained
