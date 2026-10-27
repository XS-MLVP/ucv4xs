"""RAR semantic coverage; hidden records require unique public probe evidence."""
from collections import deque
from dataclasses import dataclass, field

from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import partial_address
from .types import Release

SCENARIOS = {
    "RAR-RESET.initial": "初始复位后新记录经唯一匹配查询证明",
    "RAR-RESET.active": "活动/回收期间复位后旧记录不泄漏",
    "RAR-ALLOC.required": "存在未完成老load时分配真实记录",
    "RAR-ALLOC.behind_head": "head及更早的查询不占新槽",
    "RAR-ALLOC.redirect_canceled": "被取消的查询不建立新记录",
    "RAR-ALLOC.sparse": "稀疏需要分配的lane紧凑取得不同槽位",
    "RAR-ALLOC.capacity_nack": "容量nack不偷偷建立记录",
    "RAR-NUKE.younger_released": "年轻且已released的同hash条目触发nuke",
    "RAR-NUKE.unreleased_filtered": "尚未released的年轻条目不误触发",
    "RAR-NUKE.same_rob_filtered": "相同ROB slot不算更年轻",
    "RAR-NUKE.older_filtered": "较老记录不算年轻违例",
    "RAR-NUKE.multimatch": "多个匹配生成正确OR结果而非重复事件",
    "RAR-NUKE.old_state_remove": "本拍回收的旧记录仍参与本拍快照",
    "RAR-NUKE.nack_query": "没有分配ready的查询仍按时返回结果",
    "RAR-NUKE.lanes_independent": "同拍多lane的正反结果不串用",
    "RAR-HASH.same_line": "同cacheline不同offset仍匹配",
    "RAR-HASH.distinct": "编码相关位不同能排除非匹配",
    "RAR-HASH.collision": "不同完整line的hash碰撞保守触发",
    "RAR-HASH.high_bits": "高物理地址位参与编码区分",
    "RAR-RELEASE.concurrent": "分配同拍的完整line release被捕获",
    "RAR-RELEASE.previous": "分配前一拍的完整line release被捕获",
    "RAR-RELEASE.previous_isolated": "孤立release的下一拍新分配不遗漏标记",
    "RAR-RELEASE.no_expired_window": "两拍前的过期release不污染新分配",
    "RAR-RELEASE.late_hash_alias": "已有记录的release使用保守hash而非完整line比较",
    "RAR-RELEASE.late": "已存在记录的release按正确流水可见",
    "RAR-RELEASE.waiting_data": "最初dataValid为假的记录仍可被后续release标记",
    "RAR-RELEASE.nc": "NC按已released状态处理",
    "RAR-RELEASE.sticky": "已released状态经过空拍/其他release仍保持",
    "RAR-RELEASE.full_line_alias_excluded": "分配窗口不把hash碰撞误当完整line匹配",
    "RAR-AGE.former_latter": "同ROB entry区分former/latter年龄",
    "RAR-AGE.rob_wrap": "ROB跨环按年龄而非value排序",
    "RAR-AGE.lq_wrap": "LQ跨120边界仍正确判断是否需要分配",
    "RAR-DRAIN.head": "ldWbPtr只回收已不再受老load阻塞的记录",
    "RAR-DRAIN.redirect": "redirect只回收应取消的记录",
    "RAR-DRAIN.return_latency": "记录清除后回收容量不提前变得可分配",
    "RAR-REVOKE.one_cycle": "一拍revoke只撤销本lane上次真正分配",
    "RAR-REVOKE.two_cycle": "两拍revoke只撤销本lane对应历史分配",
    "RAR-REVOKE.both": "两个revoke窗口可同拍作用于不同记录",
    "RAR-REVOKE.no_history": "无历史分配的revoke不删除无关记录",
    "RAR-CAPACITY.threshold6": "六个空槽时尚未提前full",
    "RAR-CAPACITY.threshold5": "五个空槽时提前full但非零容量",
    "RAR-CAPACITY.exhausted": "空闲池耗尽时需要分配的查询不ready",
    "RAR-CAPACITY.partial3": "仅余1或2槽时三lane正确部分接受",
    "RAR-CAPACITY.recovered": "真实回收后full门限恢复",
    "RAR-RACE.allocate_release": "分配与release同拍不丢失标记",
    "RAR-RACE.allocate_revoke": "新分配与旧记录revoke同拍不串生命周期",
    "RAR-RACE.multifree": "同槽多种回收原因只归还一次",
    "RAR-RACE.reuse_fresh": "复用旧released槽先清除旧状态再捕获新release",
    "RAR-NUKE.old_snapshot_insert": "同拍新分配不参与其他lane的旧状态查询",
    "RAR-IDLE.empty": "空池空闲稳定",
    "RAR-IDLE.occupied": "占用期间空拍保持记录并只推进合法流水",
    "RAR-IDLE.disabled": "禁用payload不产生分配/查询/release",
    "RAR-PERF.fire_diff_from_alloc": "事件计数区分query fire和新记录分配",
    "RAR-PERF.nuke_count": "有效nuke数按规定事件流水输出",
    "RAR-PERF.three_fires": "三个实际fire正确计为三而不是单bit事件",
}


@dataclass
class Proof:
    scene: str
    born: int
    positives: set[int] = field(default_factory=set)
    removals: dict = field(default_factory=dict)
    unreleased: dict = field(default_factory=dict)
    phantoms: set = field(default_factory=set)


class FunctionalCoverage:
    def __init__(self, key, nodeid):
        points = (CoverPointDef("scenario", {k: Bin.values(k) for k in SCENARIOS},
                               description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items())),)
        self.reached = CoverGroupDef("lsq.rar.reached", points).instantiate(
            f"lsq.{key}.reached", run_metadata={"test": nodeid, "dut": key}, contract="rar.observed-legal-inputs/v1")
        self.checked = CoverGroupDef("lsq.rar.checked", points).instantiate(
            f"lsq.{key}.checked", run_metadata={"test": nodeid, "dut": key}, contract="rar.compared-with-unique-public-record-proofs/v1")
        self.pending = []
        self.witnessed = set()
        self.freed_slots = set()
        self.latency = []
        self.was_reset = False
        self.reset_wait = None
        self.reset_old = {}
        self.reset_eligible = False
        self.release_history = deque((Release(), Release()), maxlen=2)

    def sample(self, scenes, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenes:
            assert scene in SCENARIOS, scene
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)

    def discover(self, inp, change, model, pre, post):
        scenes = {}

        def add(scene, positives=(), removals=(), unreleased=(), phantoms=()):
            scenes[scene] = Proof(scene, model.edge, set(positives), {i.uid: i for i in removals},
                                  {i.uid: i for i in unreleased}, set(phantoms))

        if inp.reset:
            if not self.was_reset:
                self.reset_old = {i.uid: i for i in change.before if i.uid in self.witnessed}
                self.reset_eligible = change.reset_kind == "initial" or bool(self.reset_old)
            self.pending.clear()
            self.witnessed.clear()
            self.freed_slots.clear()
            self.latency.clear()
            self.release_history = deque((Release(), Release()), maxlen=2)
            if not self.was_reset:
                self.reset_wait = "RAR-RESET." + change.reset_kind
                add(self.reset_wait, (-1,))
            self.was_reset = True
            return scenes
        self.was_reset = False
        older_release, previous_release = self.release_history
        self.release_history.append(inp.release if inp.release.valid else Release())
        before = {item.uid: item for item in change.before}
        allocated = {item.uid: item for item in change.allocated}
        if allocated:
            add("RAR-ALLOC.required", allocated)
            lanes = [i for i, uid in enumerate(change.accepted) if uid is not None]
            if lanes != list(range(len(lanes))):
                add("RAR-ALLOC.sparse", allocated)
            if inp.release.valid:
                add("RAR-RACE.allocate_release", allocated)
            wrapped = [uid for uid, item in allocated.items() if item.query.lq.flag != inp.head.flag]
            if wrapped:
                add("RAR-AGE.lq_wrap", wrapped)
            for uid, item in allocated.items():
                if item.release_source == "previous" and not older_release.valid:
                    add("RAR-RELEASE.previous_isolated", (uid,))
                if (not item.query.nc and item.query.data_valid and not inp.release.valid
                        and not previous_release.valid and older_release.valid
                        and older_release.paddr >> 6 == item.query.paddr >> 6):
                    add("RAR-RELEASE.no_expired_window", (uid,), unreleased=(item,))
                if item.alias_window:
                    add("RAR-RELEASE.full_line_alias_excluded", (uid,), unreleased=(item,))
                if item.slot in self.freed_slots and not item.released:
                    add("RAR-RACE.reuse_fresh", (uid,), unreleased=(item,))
        for uid in change.newly_released:
            item = before.get(uid)
            if (item is not None and previous_release.valid
                    and item.query.paddr >> 6 != previous_release.paddr >> 6):
                add("RAR-RELEASE.late_hash_alias", (uid,))
        for lane, query in enumerate(inp.queries):
            if not query.valid:
                continue
            order = change.query_orders[lane]
            key = partial_address(query.paddr)
            matches = change.matches[lane]
            if not change.needed[lane] and query.nc:
                label = "behind_head" if change.query_positions[lane] <= change.head_after else "redirect_canceled"
                add("RAR-ALLOC." + label, phantoms=((order, key),))
            if change.needed[lane] and not pre.ready[lane]:
                add("RAR-NUKE.nack_query")
                if query.nc:
                    add("RAR-ALLOC.capacity_nack", phantoms=((order, key),))
            if matches:
                add("RAR-NUKE.younger_released")
                if len(matches) > 1:
                    add("RAR-NUKE.multimatch")
                if any(f.item.uid in matches for f in change.freed):
                    add("RAR-NUKE.old_state_remove")
            elif any(item.released and item.key == key and item.rob_order > order for item in allocated.values()):
                add("RAR-NUKE.old_snapshot_insert", (item.uid for item in allocated.values()
                                                     if item.released and item.key == key and item.rob_order > order))
            same_key = [item for item in change.before if item.key == key]
            if not matches:
                for item in same_key:
                    if item.rob_order == order:
                        add("RAR-NUKE.same_rob_filtered", (item.uid,))
                    elif item.rob_order < order:
                        add("RAR-NUKE.older_filtered", (item.uid,))
                    elif not item.released:
                        add("RAR-NUKE.unreleased_filtered", (item.uid,))
                for item in change.before:
                    difference = query.paddr ^ item.query.paddr
                    if item.released and item.rob_order > order and difference.bit_count() == 1 and difference >= 64 and item.key != key:
                        add("RAR-HASH.distinct", (item.uid,))
                        if difference >= 1 << 32:
                            add("RAR-HASH.high_bits", (item.uid,))
            for item in same_key:
                a, b = item.query.rob, query.rob
                if a.flag == b.flag and a.value == b.value and a.former != b.former:
                    add("RAR-AGE.former_latter", (item.uid,))
                if a.flag != b.flag:
                    add("RAR-AGE.rob_wrap", (item.uid,))
            if len(matches) == 1:
                item = before[matches[0]]
                if query.paddr != item.query.paddr:
                    add("RAR-HASH.same_line" if query.paddr >> 6 == item.query.paddr >> 6 else "RAR-HASH.collision")
                if item.release_source in ("nc", "concurrent", "previous", "late"):
                    add("RAR-RELEASE." + item.release_source)
                if item.release_source == "late" and not item.query.data_valid:
                    add("RAR-RELEASE.waiting_data")
                if item.uid in self.witnessed and model.edge > item.release_edge + 2:
                    add("RAR-RELEASE.sticky")
        valid_results = [r.nuke for r in post.responses if r.valid]
        if len(set(valid_results)) > 1:
            add("RAR-NUKE.lanes_independent")
        for freed in change.freed:
            for cause, scene in (("head", "RAR-DRAIN.head"), ("redirect", "RAR-DRAIN.redirect"),
                                 ("revoke_one", "RAR-REVOKE.one_cycle"), ("revoke_two", "RAR-REVOKE.two_cycle")):
                if cause in freed.causes:
                    add(scene, removals=(freed.item,))
            if len(freed.causes) > 1:
                add("RAR-RACE.multifree", removals=(freed.item,))
        revoked = [f for f in change.freed if any(c.startswith("revoke_") for c in f.causes)]
        if revoked and allocated:
            add("RAR-RACE.allocate_revoke", allocated, removals=(f.item for f in revoked))
        if any("revoke_one" in f.causes for f in revoked) and any("revoke_two" in f.causes for f in revoked):
            add("RAR-REVOKE.both", removals=(f.item for f in revoked))
        if any((*inp.revoke_last, *inp.revoke_older)) and not revoked and change.before:
            add("RAR-REVOKE.no_history", (item.uid for item in change.before))
        if change.old_available == 0 and change.freed:
            add("RAR-DRAIN.return_latency", (-1,))
            self.latency.append({"born": model.edge, "slots": {f.item.slot for f in change.freed}, "nack": False})
        self.freed_slots.update(f.item.slot for f in change.freed)
        if change.new_available in (6, 5):
            add("RAR-CAPACITY." + {6: "threshold6", 5: "threshold5"}[change.new_available])
        if change.old_available == 0 and any(change.needed):
            add("RAR-CAPACITY.exhausted")
        if change.old_available in (1, 2) and all(change.needed):
            add("RAR-CAPACITY.partial3", allocated)
        if pre.full and not post.full and change.recycled_slots:
            add("RAR-CAPACITY.recovered")
        no_input = not any(q.valid for q in inp.queries) and not inp.release.valid and not inp.redirect.valid and not any((*inp.revoke_last, *inp.revoke_older))
        if no_input:
            add("RAR-IDLE.occupied" if change.before else "RAR-IDLE.empty")
            if any(q.paddr or q.rob.value or q.lq.value or q.nc or q.data_valid for q in inp.queries) or inp.release.paddr or inp.redirect.rob.value:
                add("RAR-IDLE.disabled")
        if change.perf_fire_source != change.perf_alloc_source:
            add("RAR-PERF.fire_diff_from_alloc")
        if post.perf_nuke:
            add("RAR-PERF.nuke_count")
        if post.perf_fire == 3:
            add("RAR-PERF.three_fires")
        return scenes

    def confirm(self, scenes, inp, change, model, pre, post, tick):
        if inp.reset:
            return
        complete = []
        for match in change.matches:
            if len(match) == 1:
                self.witnessed.add(match[0])
        if self.reset_wait:
            for lane, query in enumerate(inp.queries):
                if query.valid and not post.responses[lane].nuke:
                    for uid, item in tuple(self.reset_old.items()):
                        if item.key == partial_address(query.paddr) and item.rob_order > change.query_orders[lane]:
                            del self.reset_old[uid]
            if self.reset_eligible and self.witnessed and not self.reset_old:
                complete.append(self.reset_wait)
                self.reset_wait = None
        self.pending.extend(proof for scene, proof in scenes.items() if not scene.startswith("RAR-RESET.") and scene != "RAR-DRAIN.return_latency")
        freed_ids = {f.item.uid for f in change.freed}
        before = {item.uid: item for item in change.before}
        outstanding = []
        for proof in self.pending:
            proof.positives.difference_update(self.witnessed)
            if proof.positives & freed_ids:
                continue  # an unproved lifecycle cannot be completed by reuse
            if proof.phantoms and model.edge > proof.born + 1:
                # An erroneous allocation could be automatically reaped by
                # head/redirect later. Only the immediate next probe proves
                # that the non-allocation path itself did not create it.
                continue
            if model.edge > proof.born:
                for lane, query in enumerate(inp.queries):
                    if not query.valid or post.responses[lane].nuke:
                        continue
                    order, key = change.query_orders[lane], partial_address(query.paddr)
                    for uid, item in list(proof.removals.items()):
                        if uid in self.witnessed and item.key == key and item.rob_order > order:
                            del proof.removals[uid]
                    for uid, item in list(proof.unreleased.items()):
                        if uid in before and not before[uid].released and item.key == key and item.rob_order > order:
                            del proof.unreleased[uid]
                    proof.phantoms.difference_update((rob, address) for rob, address in tuple(proof.phantoms) if address == key and rob > order)
            if not any((proof.positives, proof.removals, proof.unreleased, proof.phantoms)):
                complete.append(proof.scene)
            else:
                outstanding.append(proof)
        self.pending = outstanding
        latency_pending = []
        for proof in self.latency:
            if model.edge == proof["born"] + 1 and any(n and not pre.ready[i] for i, n in enumerate(change.needed)):
                proof["nack"] = True
            visible = any(n and not pre.ready[i] and post.ready[i] for i, n in enumerate(change.needed))
            if proof["nack"] and visible and proof["slots"] & set(change.recycled_slots):
                complete.append("RAR-DRAIN.return_latency")
            elif model.edge <= proof["born"] + 6:
                latency_pending.append(proof)
        self.latency = latency_pending
        self.sample(complete, tick, checked=True)
