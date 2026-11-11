"""Typed transactions and audited initial pin checks, not a completed general model."""
from collections import deque
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, DriveStable, FallingEdge, RisingEdge, SyncDriver

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.uncache_entry.transactions import Request
from suites.memblock.lsq.testbenches.uncache_entry.transactions import RobPtr
from suites.memblock.lsq.testbenches.uncache_entry.transactions import QueuePtr
from suites.memblock.lsq.testbenches.uncache_entry.transactions import SOURCE_EXCEPTION_BITS
from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
from suites.memblock.lsq.testbenches.uncache_entry.transactions import IdResponse, Redirect
from suites.memblock.lsq.testbenches.load_uncache.transactions import BypassQuery, BusReturn, LoadRequest, SampledInputs

SCENARIOS = {
    "LQU-BYPASS.payload_pool": "16真实mid两类型保存0/all1/0/all1响应和独立错误，原UID的s1元信息与s2全数据比较后完成",
    "LQU-RESET.initial": "复位后真实父块可以完成新事务",
    "LQU-RESET.active": "活动和在途事务复位后不泄漏旧状态",
    "LQU-SORT.lanes": "三路乱序输入按ROB年龄分配",
    "LQU-SORT.wrap": "ROB回绕和former/latter正确排序",
    "LQU-SORT.equal": "相同年龄的输入不丢失并保留身份",
    "LQU-FILTER.exception": "已有异常的load不建立entry",
    "LQU-FILTER.replay": "其他replay原因过滤而C_UNCACHE可进入",
    "LQU-FILTER.type": "非MMIO/NC load被过滤",
    "LQU-FILTER.redirect": "两拍redirect窗口排除被取消的输入",
    "LQU-ALLOC.real_id": "原load经过真实entry和总线id完整完成",
    "LQU-ALLOC.all_ids": "全部16个真实entry ID参与父块事务",
    "LQU-CAPACITY.reject": "预分配不足拒绝且不隐藏分配",
    "LQU-CAPACITY.return": "真实回收和预取等待后恢复容量",
    "LQU-ROLLBACK.oldest": "最老容量拒绝项携带正确恢复身份",
    "LQU-ROLLBACK.redirect_window": "容量拒绝按当前及前两拍redirect过滤而不使用过期取消",
    "LQU-ARB.mmio_priority": "MMIO活动阶段对新NC的优先关系正确",
    "LQU-ARB.nc_groups": "高低两组NC仲裁正确且有公平性证据",
    "LQU-ARB.withdrawn": "旧等待候选被取消后回退当前有效请求不串身份",
    "LQU-ARB.mmio_selector_boundary": "接口边界多个MMIO selector有效时按真实优先级完成",
    "LQU-PIPE.hold": "弹性总线寄存器在外部背压下保持",
    "LQU-PIPE.replace": "同拍输出和装入不串请求",
    "LQU-ID.bind": "实际mid回执建立正确sid响应关联",
    "LQU-ID.route": "总线回包和LDU数据回放属于原load",
    "LQU-ID.merge": "多个mid合法共享sid并分别取得同一回包数据",
    "LQU-ID.returned_sid_reuse": "已回包旧load未消费时同号新sid回包不污染旧数据",
    "LQU-WAKE.nc": "NC在正确LQ上唤醒后才能回放数据",
    "LQU-WAKE.mmio": "MMIO在正确LQ上唤醒后才能回放数据",
    "LQU-WAKE.priority": "多个entry的wakeup按实际优先级推进",
    "LQU-BYPASS.nc": "NC replay取走正确地址和数据",
    "LQU-BYPASS.mmio": "MMIO replay取走正确地址和数据",
    "LQU-BYPASS.s1_s2": "地址和128位复制数据按s1/s2边沿分离",
    "LQU-BYPASS.miss": "非匹配LQ或类型不制造回放结果",
    "LQU-BYPASS.lanes": "三路回放和重复命中不重复释放",
    "LQU-EXCEPTION.clean": "无错误的消费也报告原异常信息",
    "LQU-EXCEPTION.errors": "总线错误经bypass及异常信息传递",
    "LQU-EXCEPTION.truncation": "fullva与50位gpaddr的来源和宽度正确",
    "LQU-EXCEPTION.priority": "同拍多个entry报告按真实优先级选择",
    "LQU-FLUSH.before_bus": "保存及未内部接受阶段可直接取消",
    "LQU-FLUSH.inflight": "已缓冲/已发请求取消须最终收包再释放",
    "LQU-FLUSH.consume_concurrent": "redirect与bypass消费同拍仍产生相应数据和异常报告",
    "LQU-REUSE.pool": "全池多轮重用不串旧身份",
    "LQU-IDLE.empty": "空闲时无伪总线请求、唤醒或响应",
}


class PublicPorts:
    def __init__(self, dut):
        self.dut = dut
        self.inputs, self.outputs = {}, {}
        def walk(node, names=()):
            if "Pin" in node:
                name = "_".join(names)
                if name != "clock":
                    target = self.inputs if node["Pin"] == "input" else self.outputs
                    target[name] = getattr(dut, name)
                return
            for name, child in node.items():
                if isinstance(child, dict):
                    walk(child, (*names, name))
        walk(json.loads((ROOT / "dut/load_queue_uncache/signals.json").read_text()))
        assert "reset" in self.inputs and "io_uncache_req_bits_id" in self.outputs

    def sample(self, event):
        return ({name: signal.U() for name, signal in self.inputs.items()},
                {name: signal.U() for name, signal in self.outputs.items()})

    @staticmethod
    def observe_inputs(pins):
        def rob(prefix):
            return RobPtr(bool(pins[prefix + "flag"]), pins[prefix + "value"], bool(pins[prefix + "isFormer"]))

        def lq(prefix):
            return QueuePtr(bool(pins[prefix + "flag"]), pins[prefix + "value"])

        requests, bypass = [], []
        for lane in range(3):
            prefix = f"io_req_{lane}_"
            def get(suffix):
                return pins[prefix + suffix]
            request = None
            if get("valid"):
                entry = Request(True, rob(prefix + "bits_uop_robIdx_"), lq(prefix + "bits_uop_lqIdx_"),
                    *(get("bits_" + field) for field in ("vaddr", "fullva", "paddr", "gpaddr", "mask")),
                    *(bool(get("bits_" + field)) for field in ("nc", "mmio", "memBackTypeMM", "isHyper", "isForVSnonLeafPTE")),
                    sum(get(f"bits_uop_exceptionVec_{bit}") << bit for bit in (*SOURCE_EXCEPTION_BITS, 19, 5)))
                request = LoadRequest(entry, FtqPtr(bool(get("bits_uop_ftqPtr_flag")), get("bits_uop_ftqPtr_value")),
                    get("bits_uop_ftqOffset"), bool(get("bits_uop_isRVC")), get("bits_uop_perfDebugInfo_runahead_checkpoint_id"),
                    bool(get("bits_rep_info_need_rep")), bool(get("bits_rep_info_cause_0")))
            requests.append(request)
            prefix = f"io_bypass_{lane}_s0Req_"
            bypass.append(BypassQuery(lq(prefix + "bits_lqIdx_"), bool(get("bits_isNCReplay")),
                                      bool(get("bits_isMMIOReplay"))) if get("valid") else None)
        returned = BusReturn(pins["io_uncache_resp_bits_id"], pins["io_uncache_resp_bits_data"],
                             bool(pins["io_uncache_resp_bits_error"]), bool(pins["io_uncache_resp_bits_nderr"])) \
            if pins["io_uncache_resp_valid"] else None
        return SampledInputs(tuple(requests), rob("io_rob_pendingPtr_"),
            Redirect(bool(pins["io_redirect_valid"]), rob("io_redirect_bits_robIdx_"), bool(pins["io_redirect_bits_level"])),
            tuple(bypass), bool(pins["io_uncache_req_ready"]),
            IdResponse(bool(pins["io_uncache_idResp_valid"]), pins["io_uncache_idResp_bits_mid"],
                       pins["io_uncache_idResp_bits_sid"]), returned, bool(pins["reset"]))

    def observe(self, pins):
        """Decode one sampled public window into immutable LQU transactions."""
        from suites.memblock.lsq.testbenches.load_uncache.transactions import (
            BypassResponse, ExceptionFault, Observation, Rollback, UncacheRequestView, Wakeup)
        from suites.memblock.lsq.testbenches.shared.transactions import RobIdentity

        def rob(prefix):
            return RobIdentity(pins[prefix + "value"], bool(pins[prefix + "flag"]),
                               bool(pins[prefix + "isFormer"]))

        bypass = tuple(BypassResponse(
            lane, bool(pins[f"io_bypass_{lane}_s1Resp_valid"]), pins[f"io_bypass_{lane}_s1Resp_bits_paddr"],
            bool(pins[f"io_bypass_{lane}_s2Resp_valid"]), pins[f"io_bypass_{lane}_s2Resp_bits_data"],
            bool(pins[f"io_bypass_{lane}_s2Resp_bits_derr"]), bool(pins[f"io_bypass_{lane}_s2Resp_bits_nderr"]))
            for lane in range(3))
        request = UncacheRequestView(
            bool(pins["io_uncache_req_valid"]), pins["io_uncache_req_bits_addr"],
            pins["io_uncache_req_bits_vaddr"], pins["io_uncache_req_bits_mask"],
            pins["io_uncache_req_bits_id"], bool(pins["io_uncache_req_bits_nc"]),
            bool(pins["io_uncache_req_bits_memBackTypeMM"]),
            rob("io_uncache_req_bits_robIdx_")) if pins["io_uncache_req_valid"] else None
        return Observation(
            request, bool(pins["io_rob_mmioBusy"]),
            Wakeup(bool(pins["io_ncWakeup_bits_flag"]), pins["io_ncWakeup_bits_value"])
            if pins["io_ncWakeup_valid"] else None,
            Wakeup(bool(pins["io_mmioWakeup_bits_flag"]), pins["io_mmioWakeup_bits_value"])
            if pins["io_mmioWakeup_valid"] else None,
            Rollback(bool(pins["io_rollback_valid"]), rob("io_rollback_bits_robIdx_"),
                     bool(pins["io_rollback_bits_level"]), pins["io_rollback_bits_debug_runahead_checkpoint_id"]),
            ExceptionFault(
                bool(pins["io_exceptionInfo_valid"]), rob("io_exceptionInfo_bits_robIdx_"),
                pins["io_exceptionInfo_bits_vaddr"], pins["io_exceptionInfo_bits_gpaddr"],
                bool(pins["io_exceptionInfo_bits_isHyper"]), bool(pins["io_exceptionInfo_bits_isForVSnonLeafPTE"]),
                sum(pins[f"io_exceptionInfo_bits_exceptionVec_{bit}"] << bit
                    for bit in (3, 4, 5, 6, 7, 13, 15, 19, 21, 23))),
            bypass)


class PublicDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(tuple(ports.inputs.values()), name="load-uncache-public-cycle")

    async def _drive_one(self, values):
        assert set(values) == set(self.ports.inputs)
        await FallingEdge(self.ports.dut.clock)
        for name, signal in self.ports.inputs.items():
            signal.Set(values[name])
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            for name, signal in self.ports.inputs.items():
                if name == "reset" or name.endswith("valid") or name == "io_uncache_req_ready":
                    signal.Set(0)


def _load_from_dict(data):
    from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
    from suites.memblock.lsq.testbenches.uncache_entry.transactions import QueuePtr
    from suites.memblock.lsq.testbenches.uncache_entry.transactions import Request
    from suites.memblock.lsq.testbenches.uncache_entry.transactions import RobPtr

    entry = data["entry"]
    request = Request(
        entry["valid"],
        RobPtr(bool(entry["rob"]["flag"]), entry["rob"]["value"], bool(entry["rob"]["former"])),
        QueuePtr(bool(entry["lq"]["flag"]), entry["lq"]["value"]),
        entry["vaddr"], entry["fullva"], entry["paddr"], entry["gpaddr"], entry["mask"],
        bool(entry["nc"]), bool(entry["mmio"]), bool(entry["memory_backed"]),
        bool(entry["hyper"]), bool(entry["nonleaf"]), entry["exceptions"])
    ftq = data["ftq"]
    return LoadRequest(request, FtqPtr(bool(ftq["flag"]), ftq["value"]), data["offset"],
                       bool(data["rvc"]), data["checkpoint"], bool(data["need_replay"]),
                       bool(data["uncache_cause"]))


class ProbeEnv:
    def __init__(self, ports, driver, before, after, journal, checks, nodeid, *, coverage_scope="initial_public_probes_not_general_reference"):
        self.ports, self.driver, self.before, self.after = ports, driver, before, after
        self.journal, self.checks = journal, checks
        self.last_tick = -1
        self.observed = {}
        self.response = None
        # Full-reference subclass fills the request-owned lifecycle view.
        self.owners = {}
        self.pipe_uid = None
        self.external = set()
        self.pool_available = 16
        self.pending = RobPtr()
        self.wakeups = deque()
        self.mid_requests = {}
        self.reached_names, self.checked_names = set(), set()
        point = CoverPointDef("scenario", {key: Bin.values(key) for key in SCENARIOS},
                              description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items()))
        meta = {"test": nodeid, "dut": "load_queue_uncache", "scope": coverage_scope}
        self.reached = CoverGroupDef("lsq.load_uncache.reached", (point,)).instantiate(
            "lsq.load_queue_uncache.reached", run_metadata=meta, contract="lqu.observed-obligations/v2")
        self.checked = CoverGroupDef("lsq.load_uncache.checked", (point,)).instantiate(
            "lsq.load_queue_uncache.checked", run_metadata=meta, contract="lqu.actual-lifecycle-or-public-capacity-checks/v2")

    def reach(self, scene):
        if scene not in self.reached_names:
            self.reached.sample({"scenario": scene}, metadata={"tick": self.last_tick}, details=False)
            self.reached_names.add(scene)

    def prove(self, scene):
        self.reach(scene)
        if scene not in self.checked_names:
            self.checked.sample({"scenario": scene}, metadata={"tick": self.last_tick}, details=False)
            self.checked_names.add(scene)

    def expect(self, label, actual, expected):
        ok = actual == expected
        self.checks.write(json.dumps({"tick": self.last_tick, "label": label, "actual": actual, "expected": expected, "ok": ok}) + "\n")
        self.checks.flush()
        assert ok, (label, actual, expected)

    async def cycle(self, values=None, *, pending=None):
        if pending is not None:
            self.pending = pending
        drive = dict.fromkeys(self.ports.inputs, 0)
        drive.update(io_rob_pendingPtr_flag=int(self.pending.flag), io_rob_pendingPtr_value=self.pending.value,
                     io_rob_pendingPtr_isFormer=int(self.pending.former))
        for name, value in (values or {}).items():
            if name not in drive:
                raise ValueError(f"not an actual parent input: {name}")
            drive[name] = int(value)
        accepted = await self.driver.send(drive)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            assert pre.value[0] == post.value[0]
            if post.event.tick == accepted.tick:
                assert pre.value[0] == drive
            self.journal.write(json.dumps({"pre_tick": pre.event.tick, "post_tick": post.event.tick,
                                          "input": pre.value[0], "post_input": post.value[0],
                                          "before": pre.value[1], "after": post.value[1],
                                          "scope": "passive_observation_initial_probes_not_full_cycle_reference"}) + "\n")
            for kind in ("nc", "mmio"):
                if pre.value[1][f"io_{kind}Wakeup_valid"]:
                    self.wakeups.append((kind, pre.value[1][f"io_{kind}Wakeup_bits_flag"], pre.value[1][f"io_{kind}Wakeup_bits_value"]))
            self.observed = post.value[1]
            self.response = self.ports.observe(self.observed)
            if post.event.tick == accepted.tick:
                return

    @staticmethod
    def _redirect_fields(rob, self_flush=False, *, valid=True):
        return {"io_redirect_valid": int(valid), "io_redirect_bits_robIdx_flag": int(rob.flag),
                "io_redirect_bits_robIdx_value": rob.value, "io_redirect_bits_robIdx_isFormer": int(rob.former),
                "io_redirect_bits_level": int(self_flush)}

    async def redirect(self, rob, self_flush=False, *, valid=True):
        return await self.cycle(self._redirect_fields(rob, self_flush, valid=valid))

    async def bypass_request(self, lane, request, *, nc=None, mmio=None, redirect=None, redirect_self_flush=False):
        q = request.entry
        fields = {f"io_bypass_{lane}_s0Req_valid": 1,
                          f"io_bypass_{lane}_s0Req_bits_lqIdx_flag": int(q.lq.flag),
                          f"io_bypass_{lane}_s0Req_bits_lqIdx_value": q.lq.value,
                  f"io_bypass_{lane}_s0Req_bits_isNCReplay": int(q.nc if nc is None else nc),
                  f"io_bypass_{lane}_s0Req_bits_isMMIOReplay": int(q.mmio if mmio is None else mmio)}
        if redirect is not None:
            fields.update(self._redirect_fields(redirect, redirect_self_flush))
        return await self.cycle(fields)

    async def id_only(self, mid, sid):
        """Drive only a real ID acknowledgement without bus acceptance."""
        await self.cycle({"io_uncache_idResp_valid": 1, "io_uncache_idResp_bits_mid": mid,
                          "io_uncache_idResp_bits_sid": sid})

    async def bus_ready(self):
        return await self.cycle({"io_uncache_req_ready": 1})

    async def reset(self):
        self.pending = RobPtr()
        for _ in range(6):
            await self.cycle({"reset": 1})
        await self.idle(3)
        self.wakeups.clear()
        self.reach("LQU-RESET.initial")

    async def idle(self, cycles=1):
        for _ in range(cycles):
            await self.cycle()

    def request(self, *, nc=True, lq=11, rob=10, paddr=0x123456780000, vaddr=0x123450000, tag=1):
        q = Request(True, RobPtr.encode(rob), QueuePtr.encode(lq), vaddr, 0xFEDCBA9800000000 | tag,
                    paddr, 0xABCD000000000000 | (tag << 8), 0xA55A, nc, not nc, bool(tag & 1), bool(tag & 2), bool(tag & 4))
        return LoadRequest(q, FtqPtr(bool(tag & 64), tag % 64), tag % 32, bool(tag & 1), 0xABCD00000000 | tag)

    async def enqueue(self, requests, *, pending=None, controls=None, redirect=None):
        fields = {}
        for lane, request in requests.items():
            q = request.entry
            prefix = f"io_req_{lane}_"
            values = {"valid": q.valid, "bits_uop_isRVC": request.rvc, "bits_uop_ftqPtr_flag": request.ftq.flag,
                      "bits_uop_ftqPtr_value": request.ftq.value, "bits_uop_ftqOffset": request.offset,
                      "bits_uop_robIdx_flag": q.rob.flag, "bits_uop_robIdx_value": q.rob.value, "bits_uop_robIdx_isFormer": q.rob.former,
                      "bits_uop_perfDebugInfo_runahead_checkpoint_id": request.checkpoint,
                      "bits_uop_lqIdx_flag": q.lq.flag, "bits_uop_lqIdx_value": q.lq.value, "bits_vaddr": q.vaddr,
                      "bits_fullva": q.fullva, "bits_paddr": q.paddr, "bits_gpaddr": q.gpaddr, "bits_mask": q.mask,
                      "bits_nc": q.nc, "bits_mmio": q.mmio, "bits_memBackTypeMM": q.memory_backed,
                      "bits_isHyper": q.hyper, "bits_isForVSnonLeafPTE": q.nonleaf,
                      "bits_rep_info_need_rep": request.need_replay, "bits_rep_info_cause_0": request.uncache_cause}
            values.update({f"bits_uop_exceptionVec_{bit}": q.exceptions >> bit & 1 for bit in (*SOURCE_EXCEPTION_BITS, 19, 5)})
            fields.update({prefix + key: value for key, value in values.items()})
        if pending is None:
            if len(requests) != 1:
                raise ValueError("multi-load initial probes need an explicit external ROB pending pointer")
            pending = next(iter(requests.values())).entry.rob
        fields.update(controls or {})
        if redirect is not None:
            fields.update(self._redirect_fields(redirect))
        await self.cycle(fields, pending=pending)

    async def take_bus(self, request, mid):
        for _ in range(40):
            if self.observed["io_uncache_req_valid"]:
                break
            await self.cycle()
        else:
            raise AssertionError("no expected real-parent bus request within 40 cycles")
        q, out = request.entry, self.observed
        expected = {"robIdx_flag": int(q.rob.flag), "robIdx_value": q.rob.value, "robIdx_isFormer": int(q.rob.former),
                    "cmd": 0, "addr": q.paddr, "vaddr": q.vaddr, "mask": (q.mask >> (8 if q.paddr & 8 else 0)) & 255,
                    "id": mid, "nc": int(q.nc), "memBackTypeMM": int(q.memory_backed)}
        self.reach("LQU-ALLOC.real_id")
        self.expect("bus.original-request-and-mid", {key: out["io_uncache_req_bits_" + key] for key in expected}, expected)
        self.mid_requests[mid] = request
        await self.cycle({"io_uncache_req_ready": 1})

    async def bind(self, mid, sid):
        assert mid in self.mid_requests
        self.reach("LQU-ID.bind")
        await self.cycle({"io_uncache_idResp_valid": 1, "io_uncache_idResp_bits_mid": mid, "io_uncache_idResp_bits_sid": sid})

    async def respond(self, sid, data, *, error=False, nderr=False):
        await self.cycle({"io_uncache_resp_valid": 1, "io_uncache_resp_bits_id": sid, "io_uncache_resp_bits_data": data,
                          "io_uncache_resp_bits_error": error, "io_uncache_resp_bits_nderr": nderr})

    async def wait_wakeup(self, request):
        q = request.entry
        key = ("nc" if q.nc else "mmio", int(q.lq.flag), q.lq.value)
        for _ in range(40):
            if key in self.wakeups:
                self.wakeups.remove(key)
                self.reach("LQU-WAKE.nc" if q.nc else "LQU-WAKE.mmio")
                return
            await self.cycle()
        raise AssertionError(("no actual wakeup for original LQ", key))

    async def consume(self, request, data, *, lane=0, error=False, nderr=False):
        q, prefix = request.entry, f"io_bypass_{lane}_"
        for scene in ("LQU-BYPASS.nc" if q.nc else "LQU-BYPASS.mmio", "LQU-BYPASS.s1_s2", "LQU-ID.route",
                      "LQU-EXCEPTION.errors" if error or nderr else "LQU-EXCEPTION.clean", "LQU-EXCEPTION.truncation"):
            self.reach(scene)
        await self.cycle({prefix + "s0Req_valid": 1, prefix + "s0Req_bits_lqIdx_flag": q.lq.flag,
                          prefix + "s0Req_bits_lqIdx_value": q.lq.value, prefix + "s0Req_bits_isNCReplay": q.nc,
                          prefix + "s0Req_bits_isMMIOReplay": q.mmio})
        self.expect("bypass.s1.valid", self.observed[prefix + "s1Resp_valid"], 1)
        self.expect("bypass.s1.original-paddr", self.observed[prefix + "s1Resp_bits_paddr"], q.paddr)
        self.expect("exception.valid-on-consume", self.observed["io_exceptionInfo_valid"], 1)
        expected = {"robIdx_flag": int(q.rob.flag), "robIdx_value": q.rob.value, "robIdx_isFormer": int(q.rob.former),
                    "vaddr": q.fullva, "gpaddr": q.gpaddr, "isHyper": int(q.hyper), "isForVSnonLeafPTE": int(q.nonleaf)}
        expected.update({f"exceptionVec_{bit}": q.exceptions >> bit & 1 for bit in SOURCE_EXCEPTION_BITS})
        expected.update(exceptionVec_19=int(error), exceptionVec_5=int(nderr))
        self.expect("exception.original-load-metadata", {key: self.observed["io_exceptionInfo_bits_" + key] for key in expected}, expected)
        await self.cycle()
        self.expect("bypass.s2.valid", self.observed[prefix + "s2Resp_valid"], 1)
        self.expect("bypass.s2.original-response-data", self.observed[prefix + "s2Resp_bits_data"], (data << 64) | data)
        self.expect("bypass.s2.errors", (self.observed[prefix + "s2Resp_bits_derr"], self.observed[prefix + "s2Resp_bits_nderr"]), (int(error), int(nderr)))
        for scene in ("LQU-RESET.initial", "LQU-ALLOC.real_id", "LQU-ID.bind", "LQU-ID.route", "LQU-WAKE.nc" if q.nc else "LQU-WAKE.mmio",
                      "LQU-BYPASS.nc" if q.nc else "LQU-BYPASS.mmio", "LQU-BYPASS.s1_s2",
                      "LQU-EXCEPTION.errors" if error or nderr else "LQU-EXCEPTION.clean", "LQU-EXCEPTION.truncation"):
            self.prove(scene)
        await self.cycle()
