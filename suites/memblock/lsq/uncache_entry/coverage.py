"""Lifecycle proofs: ordinary behavior waits for actual consumption/report."""
from dataclasses import dataclass

from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import is_younger
from .types import RobPtr, SOURCE_EXCEPTION_BITS

SCENARIOS = {
    "UE-RESET.initial": "初始复位后新事务实际完成",
    "UE-RESET.active": "活动复位取消旧事务后新身份实际完成",
    "UE-ALLOC.nc": "保存NC请求并完成对应生命周期",
    "UE-ALLOC.mmio": "保存MMIO请求并完成对应生命周期",
    "UE-ISSUE.nc_early": "NC在ROB未到许可位置时也可发起",
    "UE-ISSUE.mmio_wait": "MMIO在ROB许可前不提前请求总线",
    "UE-ISSUE.mmio_eligible": "ROB许可后MMIO最终发起请求",
    "UE-ISSUE.registered_pending": "pendingPtr改变先经过一级寄存再许可MMIO",
    "UE-REQ.accepted": "总线请求只按真实ready/valid接受",
    "UE-REQ.backpressure": "未接受的总线请求保持有效和payload",
    "UE-REQ.long_backpressure": "长背压不能丢失或重复请求",
    "UE-MASK.lower": "低8字节请求选择输入mask低半部",
    "UE-MASK.upper": "高8字节请求选择输入mask高半部",
    "UE-MASK.single_byte": "单字节mask位位置正确透传",
    "UE-ID.match": "当前entry的完整mid绑定sid",
    "UE-ID.other_mid": "其他entry的mid不改变本entry的路由",
    "UE-ID.high_alias": "相同低4位而高位不同的mid不能误绑定",
    "UE-ID.empty": "没有所有者时ID回执不能制造有效sid",
    "UE-RESP.clean": "无响应错误的data正确保存至消费",
    "UE-RESP.nderr": "非数据错误只置loadAccessFault",
    "UE-RESP.error": "数据错误只置hardwareError",
    "UE-RESP.both_errors": "两种响应错误可独立同时保留",
    "UE-RESP.delayed": "延迟回包期间不产生提前唤醒或数据",
    "UE-WAKE.nc": "NC先唤醒原LQ身份再提供数据",
    "UE-WAKE.mmio": "MMIO先唤醒原LQ身份再提供数据",
    "UE-WAKE.backpressure": "唤醒受阻时不能提前进入数据输出阶段",
    "UE-WAKE.other_ready": "非选择类型的wakeup ready不能推进事务",
    "UE-OUT.nc": "NC数据只经正确输出通道消费",
    "UE-OUT.mmio": "MMIO数据只经正确输出通道消费",
    "UE-OUT.backpressure": "消费者背压保持数据/地址/错误/身份",
    "UE-OUT.wrong_ready": "非选择数据通道ready不能释放所有者",
    "UE-EXCEPTION.no_error": "无错误的正常消费也产生有效异常信息报告",
    "UE-EXCEPTION.errors": "消费后的异常信息包含响应错误",
    "UE-EXCEPTION.metadata": "报告保留原ROB/完整VA/GPA/虚拟化元信息",
    "UE-FLUSH.permission": "等待ROB许可时redirect可直接释放",
    "UE-FLUSH.request": "尚未总线接受时取消抑制请求并直接释放",
    "UE-FLUSH.deferred": "已发请求的取消粘滞等待真实回包",
    "UE-FLUSH.response": "被取消的在途请求只在回包时释放",
    "UE-FLUSH.wakeup": "wakeup阶段取消不会产生后续数据消费",
    "UE-FLUSH.output": "数据等待阶段取消后可安全重用",
    "UE-FLUSH.consume_same_cycle": "取消与数据消费同拍仍按接口报告异常信息",
    "UE-AGE.former_latter": "ROB同entry的former/latter决定许可或取消边界",
    "UE-AGE.rob_wrap": "ROB159到160跨环按年龄而非value判断",
    "UE-AGE.flush_self": "flushSelf可取消同一ROB slot",
    "UE-AGE.flush_after": "flushAfter保留相同ROB slot",
    "UE-AGE.survivor": "不应取消的较老请求仍能完成",
    "UE-REUSE.normal": "正常释放后新身份可以再次完成",
    "UE-REUSE.canceled": "取消释放后新身份可以再次完成",
    "UE-REUSE.cross_type": "NC和MMIO交替重用不串通道",
    "UE-REUSE.clear_sid": "重用时旧sid有效性被清除",
    "UE-REUSE.clear_errors": "前一事务错误不污染新无错事务",
    "UE-IDLE.empty": "空闲无事务时公开valid保持安静",
    "UE-IDLE.disabled": "禁用payload不能分配/绑定/产生响应",
    **{f"UE-ID.sid_{sid}": f"本entry绑定并保持从站sid={sid}直到该事务完成" for sid in range(16)},
    **{f"UE-EXCEPTION.source_{bit}": f"保留输入异常位{bit}的接口级元信息透传" for bit in SOURCE_EXCEPTION_BITS},
}


@dataclass(frozen=True)
class Proof:
    scene: str
    uid: int | None
    mode: str = "complete"


class FunctionalCoverage:
    def __init__(self, key, spec, nodeid):
        self.spec = spec
        self.scenarios = {k: v for k, v in SCENARIOS.items() if spec["wakeup_backpressure"] or k not in ("UE-WAKE.backpressure", "UE-WAKE.other_ready")}
        point = CoverPointDef("scenario", {key: Bin.values(key) for key in self.scenarios},
                              description="; ".join(f"{k}: {v}" for k, v in self.scenarios.items()))
        metadata = {"test": nodeid, "dut": key, "entry_id": spec["entry_id"]}
        self.reached = CoverGroupDef("lsq.uncache_entry.reached", (point,)).instantiate(
            f"lsq.{key}.reached", run_metadata=metadata, contract="entry.observed-protocol-semantics/v1")
        self.checked = CoverGroupDef("lsq.uncache_entry.checked", (point,)).instantiate(
            f"lsq.{key}.checked", run_metadata=metadata, contract="entry.actual-data-consumption-report-or-cancel-then-reuse/v1")
        self.pending = []
        self.completed = set()
        self.retired = set()
        self.was_reset = False
        self.reset_wait = None
        self.last_retired = None
        self.previous_pending = RobPtr()
        self.stall = self.wait_response = 0

    def sample(self, scenes, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenes:
            assert scene in self.scenarios, scene
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)

    def discover(self, inp, change, model, pre, post):
        scenes = {}
        def add(scene, uid=None, mode="complete"):
            if scene in self.scenarios:
                scenes[scene] = Proof(scene, uid, mode)
        if inp.reset:
            if not self.was_reset:
                self.reset_wait = "UE-RESET." + change.reset_kind
                add(self.reset_wait)
            self.was_reset = True
            self.pending.clear()
            self.completed.clear()
            self.retired.clear()
            self.last_retired = None
            self.previous_pending = RobPtr()
            self.stall = self.wait_response = 0
            return scenes
        self.was_reset = False
        old = change.before
        if change.allocated is not None:
            uid, q = change.allocated.uid, change.allocated.request
            add("UE-ALLOC.nc" if q.nc else "UE-ALLOC.mmio", uid)
            if self.last_retired:
                previous, canceled, had_sid, had_errors = self.last_retired
                add("UE-REUSE.canceled" if canceled else "UE-REUSE.normal", uid)
                if q.nc != previous.request.nc:
                    add("UE-REUSE.cross_type", uid)
                if had_sid:
                    add("UE-REUSE.clear_sid", uid)
        if old is not None:
            uid, q = old.uid, old.request
            if change.phase_before == "holding":
                if q.nc and is_younger(q.rob, self.previous_pending):
                    add("UE-ISSUE.nc_early", uid)
                if not q.nc:
                    add("UE-ISSUE.mmio_wait" if is_younger(q.rob, self.previous_pending) else "UE-ISSUE.mmio_eligible", uid)
                    if is_younger(q.rob, self.previous_pending) and not is_younger(q.rob, inp.pending):
                        add("UE-ISSUE.registered_pending", uid)
            control = inp.redirect.rob if inp.redirect.valid else self.previous_pending
            mode = "reuse" if change.canceled else "complete"
            if q.rob.flag == control.flag and q.rob.value == control.value and q.rob.former != control.former:
                add("UE-AGE.former_latter", uid, mode)
            if q.rob.flag != control.flag:
                add("UE-AGE.rob_wrap", uid, mode)
            if inp.redirect.valid:
                if not change.canceled:
                    add("UE-AGE.survivor", uid)
                if q.rob == inp.redirect.rob:
                    add("UE-AGE.flush_self" if inp.redirect.flush_self else "UE-AGE.flush_after", uid, mode)
            if pre.bus.valid and not inp.bus_ready:
                self.stall += 1
                add("UE-REQ.backpressure", uid)
                if self.stall >= 5:
                    add("UE-REQ.long_backpressure", uid)
            else:
                self.stall = 0
            if change.issued:
                add("UE-REQ.accepted", uid)
                add("UE-MASK.upper" if q.paddr & 8 else "UE-MASK.lower", uid)
                if pre.bus.mask.bit_count() == 1:
                    add("UE-MASK.single_byte", uid)
            if inp.id_response.valid:
                if change.bound and not change.retired:
                    add("UE-ID.match", uid)
                    add(f"UE-ID.sid_{inp.id_response.sid}", uid)
                elif inp.id_response.mid != self.spec["entry_id"]:
                    add("UE-ID.other_mid", uid)
                    if inp.id_response.mid & 15 == self.spec["entry_id"]:
                        add("UE-ID.high_alias", uid)
            if change.phase_before == "response" and not inp.response.valid:
                self.wait_response += 1
                if self.wait_response >= 5:
                    add("UE-RESP.delayed", uid)
            else:
                self.wait_response = 0
            if change.responded:
                errors = int(inp.response.nderr) + 2 * int(inp.response.error)
                add("UE-RESP." + ("clean", "nderr", "error", "both_errors")[errors], uid)
                if self.last_retired and self.last_retired[3] and not errors:
                    add("UE-REUSE.clear_errors", uid)
            if change.woke:
                add("UE-WAKE.nc" if q.nc else "UE-WAKE.mmio", uid)
            if change.phase_before == "wakeup" and not change.retired:
                selected = inp.nc_wake_ready if q.nc else inp.mmio_wake_ready
                other = inp.mmio_wake_ready if q.nc else inp.nc_wake_ready
                if not selected:
                    add("UE-WAKE.backpressure", uid)
                    if other:
                        add("UE-WAKE.other_ready", uid)
            if pre.nc.valid or pre.mmio.valid:
                selected, other = (inp.nc_ready, inp.mmio_ready) if q.nc else (inp.mmio_ready, inp.nc_ready)
                if not selected:
                    add("UE-OUT.backpressure", uid)
                    if other:
                        add("UE-OUT.wrong_ready", uid)
            if change.consumed:
                selected_output = pre.nc if q.nc else pre.mmio
                add("UE-OUT.nc" if q.nc else "UE-OUT.mmio", uid)
                add("UE-EXCEPTION.errors" if selected_output.error or selected_output.nderr else "UE-EXCEPTION.no_error", uid)
                add("UE-EXCEPTION.metadata", uid)
                for bit in SOURCE_EXCEPTION_BITS:
                    if q.exceptions >> bit & 1:
                        add(f"UE-EXCEPTION.source_{bit}", uid)
            if change.canceled:
                if change.phase_before == "response":
                    add("UE-FLUSH.response" if change.retired else "UE-FLUSH.deferred", uid, "reuse")
                elif change.retired:
                    label = {"holding": "permission", "request": "request", "wakeup": "wakeup", "output": "output"}[change.phase_before]
                    add("UE-FLUSH." + label, uid, "reuse")
                    if change.consumed:
                        add("UE-FLUSH.consume_same_cycle", uid)
        elif inp.id_response.valid:
            add("UE-ID.empty", mode="direct")
        no_valid = not (inp.request.valid or inp.response.valid or inp.id_response.valid or inp.redirect.valid)
        if no_valid:
            if old is None:
                add("UE-IDLE.empty", mode="direct")
            if (inp.request.paddr or inp.request.exceptions or inp.response.data or inp.id_response.mid or inp.redirect.rob.value):
                add("UE-IDLE.disabled", old.uid if old else None, "complete" if old else "direct")
        self.previous_pending = inp.pending
        return scenes

    def confirm(self, scenes, inp, change, model, pre, post, tick):
        if change.consumed:
            assert post.exception.valid
            self.completed.add(change.before.uid)
        if change.retired:
            assert pre.flush
            self.retired.add(change.before.uid)
            selected_output = pre.nc if change.before.request.nc else pre.mmio
            self.last_retired = (change.before, change.canceled, pre.slave_valid,
                                 selected_output.error or selected_output.nderr)
        completed = []
        if self.reset_wait and self.completed:
            completed.append(self.reset_wait)
            self.reset_wait = None
        self.pending.extend(proof for scene, proof in scenes.items() if not scene.startswith("UE-RESET."))
        pending = []
        for proof in self.pending:
            done = (proof.mode == "direct" or proof.mode == "complete" and proof.uid in self.completed
                    or proof.mode == "reuse" and proof.uid in self.retired and any(uid > proof.uid for uid in self.completed))
            if done:
                completed.append(proof.scene)
            else:
                pending.append(proof)
        self.pending = pending
        self.sample(completed, tick, checked=True)
