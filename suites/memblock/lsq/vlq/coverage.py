"""Observed scenarios; allocation/hold/recovery proofs wait for checked outcomes."""
from dataclasses import dataclass

from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "VLQ-RESET.initial": "初始复位后重新分配且实际释放",
    "VLQ-RESET.active": "非空池复位后旧完成不泄漏",
    "VLQ-RESET.recovering": "恢复期间复位终止旧恢复事务",
    "VLQ-INTERVAL.scalar": "单流区间被正确完成和释放",
    "VLQ-INTERVAL.multiflow": "多流连续区间全部被正确释放",
    "VLQ-INTERVAL.zero": "有效零流请求不占用槽位",
    "VLQ-INTERVAL.sparse": "稀疏dispatch端口仍分配紧凑区间",
    "VLQ-INTERVAL.all_lanes": "八路同时分配的区间不丢失或重叠",
    "VLQ-COMPLETE.good": "有效且无需重放的WB完成对应生命周期",
    "VLQ-COMPLETE.replay_blocks": "需要重放的WB不能解除队头阻塞",
    "VLQ-COMPLETE.invalid_addr_blocks": "地址未更新的WB不能完成队头",
    "VLQ-COMPLETE.both_block": "重放与无地址更新共同抑制完成",
    "VLQ-ORDER.out_of_order": "年轻项先完成仍不能越过未完成队头",
    "VLQ-ORDER.partial_batch": "部分连续完成前缀保序释放",
    "VLQ-ORDER.eight_batch": "连续八项完成前缀满批次释放",
    "VLQ-ORDER.multiple_reports": "多个释放报告不重复且累计推进指针",
    "VLQ-TIMING.wb_not_immediate": "本拍WB不能零延迟移动释放头",
    "VLQ-TIMING.release_pipeline": "准备释放后才在后继边沿报告并前移",
    "VLQ-TIMING.empty_lag": "empty与指针距离按规定延迟对齐",
    "VLQ-REUSE.wrap": "释放指针跨过119到0的非2幂边界",
    "VLQ-REUSE.completed_slot_fresh": "旧完成槽位重用后重新等待完成",
    "VLQ-REUSE.two_lq_flags": "两种LQ环绕flag均正确参与实际释放",
    "VLQ-REDIRECT.flush_after": "flushAfter保留相同ROB slot",
    "VLQ-REDIRECT.flush_self": "flushItself还取消相同ROB slot",
    "VLQ-REDIRECT.former_latter": "同ROB entry的former/latter有不同年龄",
    "VLQ-REDIRECT.rob_flag": "ROB跨环时按真实年龄取消",
    "VLQ-REDIRECT.none": "无匹配取消仍正确响应恢复",
    "VLQ-REDIRECT.partial": "部分取消保留老项且正确回退尾部",
    "VLQ-REDIRECT.all": "全部取消后恢复空的合法区间",
    "VLQ-RECOVER.response": "恢复响应给出本次实际恢复尾部",
    "VLQ-RECOVER.stall_window": "恢复期间持续stall并按时解除",
    "VLQ-RECOVER.clamp": "恢复尾部不落后已经释放的头部",
    "VLQ-RECOVER.adjacent": "相邻恢复请求各自对齐响应",
    "VLQ-RACE.dispatch_redirect": "同拍被取消dispatch也正确回退其预留流",
    "VLQ-RACE.wb_redirect": "取消与WB重叠不复活旧生命周期",
    "VLQ-RACE.release_recover": "释放报告与恢复响应同拍保持指针守恒",
    "VLQ-RACE.post_recover_reuse": "取消槽位重新分配后没有旧完成泄漏",
    "VLQ-IDLE.empty": "空池空闲保持稳定",
    "VLQ-IDLE.occupied": "占用期间空拍只推进合法流水",
    "VLQ-IDLE.disabled_payload": "禁用端口上变化的payload不生效",
    "VLQ-CAPACITY.full": "合法恰满120流仍可全部完成释放",
    "VLQ-CAPACITY.one_free": "只余一个可用槽位时仍不丢流",
    "VLQ-CAPACITY.two_free": "只余两个可用槽位时仍不丢流",
}


@dataclass
class Proof:
    scene: str
    remaining: set[int]
    recovery: int | None = None
    response_seen: bool = False
    hold_uid: int | None = None
    hold_head: int | None = None
    deadline: int = 0
    hold_verified: bool = True


class FunctionalCoverage:
    def __init__(self, key, nodeid):
        points = (CoverPointDef("scenario", {k: Bin.values(k) for k in SCENARIOS},
                               description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items())),)
        self.reached = CoverGroupDef("lsq.vlq.reached", points).instantiate(
            f"lsq.{key}.reached", run_metadata={"test": nodeid, "dut": key}, contract="vlq.observed-legal-transactions/v1")
        self.checked = CoverGroupDef("lsq.vlq.checked", points).instantiate(
            f"lsq.{key}.checked", run_metadata={"test": nodeid, "dut": key}, contract="vlq.release-recovery-and-hold-proven/v1")
        self.pending = []
        self.reset_wait = None
        self.was_reset = False
        self.released_indices = set()
        self.recovered_indices = set()
        self.head_flags = {False}
        self.report_count = 0
        self.previous_occupancy = 0

    def sample(self, scenes, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenes:
            assert scene in SCENARIOS, scene
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)

    def discover(self, inp, change, model):
        scenes = {}

        def add(scene, targets=(), *, recovery=None, hold_uid=None):
            scenes[scene] = Proof(scene, set(targets), recovery=recovery,
                                  hold_uid=hold_uid, hold_head=change.old_head if hold_uid is not None else None,
                                  deadline=model.edge + 3 if hold_uid is not None else 0, hold_verified=hold_uid is None)

        if inp.reset:
            self.pending.clear()
            self.released_indices.clear()
            self.recovered_indices.clear()
            self.head_flags = {False}
            self.report_count = self.previous_occupancy = 0
            if not self.was_reset:
                self.reset_wait = "VLQ-RESET." + change.reset_kind
                add(self.reset_wait, (-1,))
            self.was_reset = True
            return scenes
        self.was_reset = False
        active = [d for d in inp.dispatch if d.valid]
        uids = tuple(item.uid for item in change.allocated)
        if uids:
            if any(d.flows == 1 for d in active):
                add("VLQ-INTERVAL.scalar", uids)
            if any(d.flows > 1 for d in active):
                add("VLQ-INTERVAL.multiflow", uids)
            lanes = [i for i, d in enumerate(inp.dispatch) if d.valid]
            if lanes != list(range(len(lanes))):
                add("VLQ-INTERVAL.sparse", uids)
            if len(active) == model.spec["dispatch_width"]:
                add("VLQ-INTERVAL.all_lanes", uids)
            reused = [item.uid for item in change.allocated if item.position % model.spec["size"] in self.released_indices]
            if reused:
                add("VLQ-REUSE.completed_slot_fresh", reused)
            recovered = [item.uid for item in change.allocated if item.position % model.spec["size"] in self.recovered_indices]
            if recovered:
                add("VLQ-RACE.post_recover_reuse", recovered)
        if active and not any(d.flows for d in active) and not inp.redirect.valid and not any(w.valid for w in inp.writebacks):
            add("VLQ-INTERVAL.zero")
        normal = set(change.completed) - set(change.canceled)
        if normal:
            add("VLQ-COMPLETE.good", normal)
            if change.head_blocked_by in normal and not change.reported:
                add("VLQ-TIMING.wb_not_immediate", (change.head_blocked_by,))
        for uid, label in change.suppressed:
            if uid == change.head_blocked_by and uid not in change.canceled:
                add("VLQ-COMPLETE." + label, (uid,), hold_uid=uid)
        if change.head_blocked_by is not None and change.younger_completed and change.head_blocked_by not in change.completed:
            add("VLQ-ORDER.out_of_order", (change.head_blocked_by, *change.younger_completed), hold_uid=change.head_blocked_by)
        if change.prepared:
            add("VLQ-TIMING.release_pipeline", (item.uid for item in change.prepared))
        if change.reported:
            add("VLQ-ORDER.eight_batch" if len(change.reported) == model.spec["release_width"] else "VLQ-ORDER.partial_batch")
            self.report_count += 1
            if self.report_count > 1:
                add("VLQ-ORDER.multiple_reports")
            self.released_indices.update(item.position % model.spec["size"] for item in change.reported)
            if change.old_head // model.spec["size"] != model.head // model.spec["size"]:
                add("VLQ-REUSE.wrap")
            self.head_flags.add(model.outputs.head.flag)
            if len(self.head_flags) == 2:
                add("VLQ-REUSE.two_lq_flags")
        if model.outputs.empty != (model.head == model.tail):
            add("VLQ-TIMING.empty_lag", uids)
        recovery = change.started_recovery
        if recovery is not None:
            for scene in recovery.categories:
                add(scene, recovery.survivors, recovery=recovery.sequence)
        if change.finished_recovery is not None:
            due = change.finished_recovery
            self.recovered_indices.update(due.canceled_indices)
            if change.clamped_recovery:
                add("VLQ-RECOVER.clamp", due.survivors, recovery=due.sequence)
            if change.reported:
                add("VLQ-RACE.release_recover", due.survivors, recovery=due.sequence)
        if not active and not any(w.valid for w in inp.writebacks) and not inp.redirect.valid:
            add("VLQ-IDLE.empty" if change.old_head == change.old_tail else "VLQ-IDLE.occupied")
            if any(d.start.value or d.rob.value or d.flows for d in inp.dispatch) or any(w.index or w.update_address or w.replay for w in inp.writebacks):
                add("VLQ-IDLE.disabled_payload")
        occupancy = model.tail - model.head
        if occupancy != self.previous_occupancy and not model.outputs.recovery_stall:
            remaining = model.spec["size"] - occupancy
            if remaining in (0, 1, 2):
                label = {0: "full", 1: "one_free", 2: "two_free"}[remaining]
                add("VLQ-CAPACITY." + label, (item.uid for item in (*model.entries.values(), *model.prepared)))
        self.previous_occupancy = occupancy
        return scenes

    def confirm(self, scenes, inp, change, model, tick):
        if inp.reset:
            return
        self.pending.extend(scenes.values())
        complete, outstanding = [], []
        released = {item.uid for item in change.reported}
        canceled = set(change.canceled)
        if self.reset_wait and released:
            complete.append(self.reset_wait)
            self.reset_wait = None
        for proof in self.pending:
            if proof.remaining & canceled:
                continue
            if not proof.hold_verified:
                if model.edge < proof.deadline and proof.hold_uid in change.completed:
                    continue
                if model.edge >= proof.deadline:
                    if model.head != proof.hold_head:
                        continue
                    proof.hold_verified = True
            proof.remaining.difference_update(released)
            if change.finished_recovery is not None and proof.recovery == change.finished_recovery.sequence:
                proof.response_seen = True
            recovery_done = proof.recovery is None or proof.response_seen and not model.outputs.recovery_stall
            if not proof.remaining and proof.hold_verified and recovery_done:
                complete.append(proof.scene)
            else:
                outstanding.append(proof)
        self.pending = outstanding
        self.sample(complete, tick, checked=True)
