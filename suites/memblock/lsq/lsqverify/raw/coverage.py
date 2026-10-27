"""Observed semantics; delayed rollback and negative probes discharge obligations."""
from collections import deque
from dataclasses import dataclass, field

from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import address_match, rollback_for

SCENARIOS = {
    "RAW-RESET.initial": "初始复位后新记录产生真实rollback",
    "RAW-RESET.active": "活动复位后旧记录消失并能重建新记录",
    "RAW-ALLOC.required": "未决老store使load真正建立记录",
    "RAW-ALLOC.behind_ready": "已越过地址就绪指针的load不占容量",
    "RAW-ALLOC.canceled": "被当前redirect取消的load不分配",
    "RAW-ALLOC.sparse": "稀疏need压紧使用真实可用槽位",
    "RAW-ALLOC.nack": "预分配容量nack不建立隐藏记录",
    "RAW-CAPACITY.exhausted": "真实空闲池耗尽时需要分配的load不ready",
    "RAW-CAPACITY.partial": "只有1或2项预告容量时三lane部分接受",
    "RAW-CAPACITY.recovered": "回收后真实full解除且能再次分配",
    "RAW-CAPACITY.prefetch_wait": "返回新槽后预分配额外等待不提前ready",
    "RAW-CAPACITY.reuse": "曾回收的物理槽位重新保存并恢复新身份",
    "RAW-ADDRESS.word_hit": "同16字节word的load/store匹配",
    "RAW-ADDRESS.word_miss": "不同word不因同line误匹配",
    "RAW-ADDRESS.wline": "line写模式允许同line不同word匹配",
    "RAW-ADDRESS.truncated_alias": "bit28以上截断别名保守匹配",
    "RAW-ADDRESS.offset_ignored": "同word不同低4位由mask决定重叠",
    "RAW-MASK.hit": "相交字节mask生成违例",
    "RAW-MASK.disjoint": "同地址无重叠字节不违例",
    "RAW-MASK.zero": "零mask不能产生违例",
    "RAW-MASK.single_byte": "单字节重叠正确生成违例",
    "RAW-ORDER.younger": "仅比store年轻的load参与违例",
    "RAW-ORDER.same_slot_filtered": "相同ROB slot不算年轻load",
    "RAW-ORDER.older_filtered": "比store更老的load被排除",
    "RAW-ORDER.not_insertion_order": "最老选择不按分配先后顺序",
    "RAW-ORDER.cross_group": "不同物理选择组的候选按ROB年龄选择",
    "RAW-ORDER.former_latter": "同ROB entry区分former/latter",
    "RAW-ORDER.rob_wrap": "ROB160跨环仍正确比较年龄",
    "RAW-ORDER.sq_second_wrap": "SQ63到64跨second_flag仍正确分配",
    "RAW-ORDER.sq_first_wrap": "SQ127到128跨first_flag仍正确分配",
    "RAW-DATA.filtered": "未取得有效数据的load不能要求rollback",
    "RAW-PIPELINE.adjacent_write": "前拍新分配在紧邻store比较时可见",
    "RAW-PIPELINE.same_edge_new_excluded": "当前新分配不参与本拍store快照",
    "RAW-PIPELINE.consecutive": "连续store保持各自恢复身份和时序",
    "RAW-PIPELINE.both_ports": "两个store并行但恢复通道互不串用",
    "RAW-PIPELINE.latency": "store经过规定三级寄存后才输出rollback",
    "RAW-PIPELINE.tlb_miss": "TLB miss的store不能输出有效恢复",
    "RAW-REDIRECT.sample": "store采样拍排除被取消候选",
    "RAW-REDIRECT.group_stage": "分组选择阶段redirect取消在途恢复",
    "RAW-REDIRECT.output_stage": "最终选择阶段redirect取消在途恢复",
    "RAW-REDIRECT.survivor": "redirect不取消的老记录仍能恢复",
    "RAW-REVOKE.one": "一拍revoke只移除同lane上次分配",
    "RAW-REVOKE.two": "两拍revoke只移除同lane相应历史分配",
    "RAW-REVOKE.both": "两个历史revoke窗口同拍独立作用",
    "RAW-REVOKE.no_history": "无实际分配历史时不误删旧记录",
    "RAW-REVOKE.late_snapshot": "store采样后才撤销不伪造额外流水过滤",
    "RAW-DRAIN.head": "地址就绪指针只回收不再受老store阻塞的记录",
    "RAW-DRAIN.redirect": "redirect释放对应年轻记录并恢复容量",
    "RAW-DRAIN.return_latency": "记录失效到返回可分配池有真实流水延迟",
    "RAW-DRAIN.multifree": "同槽多种回收原因合并一次",
    "RAW-ROLLBACK.metadata": "有效恢复逐字段保留load和store元信息",
    "RAW-TRAIN.oldest": "MDP选择两个有效恢复中更老者",
    "RAW-TRAIN.tie_lane0": "两个恢复同龄时选择store端口0元信息",
    "RAW-TRAIN.invalid": "没有有效rollback时不虚构训练",
    "RAW-PERF.fire_not_alloc": "事件区分query fire和真正分配",
    "RAW-PERF.three_fires": "三个fire按事件数三输出",
    "RAW-PERF.rollback_or": "两个rollback只产生单个OR事件而非计二",
    "RAW-IDLE.empty": "空池空闲时保持正确公开状态",
    "RAW-IDLE.occupied": "占用期间空拍不丢失记录",
    "RAW-IDLE.disabled": "禁用payload不制造分配或恢复",
}

POSITIVE_JOB_SCENARIOS = {
    "RAW-ADDRESS.word_hit", "RAW-ADDRESS.wline", "RAW-ADDRESS.truncated_alias", "RAW-ADDRESS.offset_ignored",
    "RAW-MASK.hit", "RAW-MASK.single_byte", "RAW-ORDER.younger", "RAW-ORDER.not_insertion_order", "RAW-ORDER.cross_group",
    "RAW-PIPELINE.adjacent_write", "RAW-REDIRECT.survivor", "RAW-REVOKE.late_snapshot", "RAW-PIPELINE.consecutive",
}


@dataclass
class Proof:
    scene: str
    born: int
    jobs: set[int] = field(default_factory=set)
    positives: set[int] = field(default_factory=set)
    removals: dict = field(default_factory=dict)
    phantoms: list = field(default_factory=list)
    valid_jobs: set[int] = field(default_factory=set)


class FunctionalCoverage:
    def __init__(self, key, nodeid):
        points = (CoverPointDef("scenario", {key: Bin.values(key) for key in SCENARIOS},
                               description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items())),)
        metadata = {"test": nodeid, "dut": key}
        self.reached = CoverGroupDef("lsq.raw.reached", points).instantiate(
            f"lsq.{key}.reached", run_metadata=metadata, contract="raw.passive-input-semantics/v1")
        self.checked = CoverGroupDef("lsq.raw.checked", points).instantiate(
            f"lsq.{key}.checked", run_metadata=metadata, contract="raw.compared-delayed-public-rollback-and-capacity/v1")
        self.pending = []
        self.witnessed = set()
        self.completed_jobs = set()
        self.valid_jobs = set()
        self.negative_unsafe = set()
        self.freed_slots = set()
        self.last_allocation_edge = {}
        self.last_store_edge = None
        self.last_store_jobs = ()
        self.rollback_history = deque((0, 0), maxlen=2)
        self.was_reset = False
        self.reset_wait = None
        self.reset_old = {}
        self.reset_eligible = False
        self.latency = []
        self.full_free_states = {}
        self.capacity_freed = set()

    def sample(self, scenes, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenes:
            assert scene in SCENARIOS
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)

    def discover(self, inp, change, model, pre, post):
        scenes = {}
        def add(scene, *, jobs=(), positives=(), removals=(), phantoms=()):
            proof = Proof(scene, model.edge, set(jobs), set(positives), {i.uid: i for i in removals}, list(phantoms))
            if scene in POSITIVE_JOB_SCENARIOS:
                proof.valid_jobs.update(proof.jobs)
            if scene in scenes:
                previous = scenes[scene]
                previous.jobs.update(proof.jobs)
                previous.positives.update(proof.positives)
                previous.removals.update(proof.removals)
                previous.phantoms.extend(proof.phantoms)
                previous.valid_jobs.update(proof.valid_jobs)
            else:
                scenes[scene] = proof
        if inp.reset:
            if not self.was_reset:
                self.reset_wait = "RAW-RESET." + change.reset_kind
                self.reset_old = {i.uid: i for i in change.before if i.uid in self.witnessed}
                self.reset_eligible = change.reset_kind == "initial" or bool(self.reset_old)
                add(self.reset_wait, positives=(-1,))
            self.was_reset = True
            self.pending.clear()
            self.witnessed.clear()
            self.completed_jobs.clear()
            self.valid_jobs.clear()
            self.negative_unsafe.clear()
            self.freed_slots.clear()
            self.last_allocation_edge.clear()
            self.last_store_edge = None
            self.last_store_jobs = ()
            self.rollback_history = deque((0, 0), maxlen=2)
            self.latency.clear()
            self.full_free_states.clear()
            self.capacity_freed.clear()
            return scenes
        self.was_reset = False
        allocated = {item.uid: item for item in change.allocated}
        visible = {uid for uid, item in allocated.items() if item.query.data_valid and item.query.mask}
        if visible:
            add("RAW-ALLOC.required", positives=visible)
            lanes = [lane for lane, uid in enumerate(change.accepted) if uid is not None]
            if lanes != list(range(len(lanes))):
                add("RAW-ALLOC.sparse", positives=visible)
            for uid in visible:
                item = allocated[uid]
                if item.slot in self.freed_slots:
                    add("RAW-CAPACITY.reuse", positives=(uid,))
                if item.query.sq.second != inp.head.second and item.query.sq.first == inp.head.first:
                    add("RAW-ORDER.sq_second_wrap", positives=(uid,))
                if item.query.sq.first != inp.head.first:
                    add("RAW-ORDER.sq_first_wrap", positives=(uid,))
        for lane, query in enumerate(inp.queries):
            if not query.valid or not query.data_valid or not query.mask:
                continue
            if not change.needed[lane]:
                scene = "behind_ready" if change.query_positions[lane] <= change.head_after else "canceled"
                add("RAW-ALLOC." + scene, phantoms=((change.query_orders[lane], query),))
            elif not pre.ready[lane]:
                add("RAW-ALLOC.nack", phantoms=((change.query_orders[lane], query),))
        if change.old_available == 0 and any(change.needed):
            add("RAW-CAPACITY.exhausted")
        if change.old_offered in (1, 2) and all(change.needed) and visible:
            add("RAW-CAPACITY.partial", positives=visible)
        if pre.full and not post.full and change.recycled_slots:
            add("RAW-CAPACITY.recovered", positives=(-1,))
            self.latency.append({"kind": "recover", "edge": model.edge})
        if change.new_available and not change.new_offered and any(change.needed):
            add("RAW-CAPACITY.prefetch_wait")
        if change.old_available == 0 and change.freed:
            add("RAW-DRAIN.return_latency", positives=(-1,))
            self.latency.append({"kind": "latency", "edge": model.edge, "nack": False})
        for freed in change.freed:
            for cause, scene in (("head", "RAW-DRAIN.head"), ("redirect", "RAW-DRAIN.redirect"),
                                 ("revoke_one", "RAW-REVOKE.one"), ("revoke_two", "RAW-REVOKE.two")):
                if cause in freed.causes and freed.item.query.data_valid and freed.item.query.mask:
                    add(scene, removals=(freed.item,))
            if len(freed.causes) > 1 and freed.item.query.data_valid and freed.item.query.mask:
                add("RAW-DRAIN.multifree", removals=(freed.item,))
            if pre.full and len(change.before) == model.spec["size"]:
                self.full_free_states[freed.item.uid] = {"slot": freed.item.slot, "returned": False, "replacement": None}
        if (any("revoke_one" in f.causes for f in change.freed)
                and any("revoke_two" in f.causes for f in change.freed)):
            add("RAW-REVOKE.both", removals=(f.item for f in change.freed if any(c.startswith("revoke") for c in f.causes)))
        if any((*inp.revoke_last, *inp.revoke_older)) and not any(any(c.startswith("revoke") for c in f.causes) for f in change.freed):
            remaining = [item.uid for item in change.before if item.query.data_valid and item.query.mask]
            if remaining:
                add("RAW-REVOKE.no_history", positives=remaining)
        revoked = {f.item.uid for f in change.freed if any(c.startswith("revoke") for c in f.causes)}
        for job in (*model.pending, *change.emitted):
            if job.born < model.edge and job.winner is not None and job.winner.uid in revoked:
                add("RAW-REVOKE.late_snapshot", jobs=(job.uid,))
        for job in change.created:
            waits = (job.uid,)
            same_address = [item for item in change.before if address_match(item.query, job.store)]
            for item in same_address:
                if item.rob_order > job.store_order:
                    if not item.query.data_valid:
                        add("RAW-DATA.filtered", jobs=waits)
                    elif not item.query.mask & job.store.mask:
                        add("RAW-MASK.zero" if not item.query.mask or not job.store.mask else "RAW-MASK.disjoint", jobs=waits,
                            positives=(item.uid,))
                elif item.rob_order == job.store_order:
                    add("RAW-ORDER.same_slot_filtered", jobs=waits, positives=(item.uid,))
                else:
                    add("RAW-ORDER.older_filtered", jobs=waits, positives=(item.uid,))
                if item.query.rob.flag == job.store.rob.flag and item.query.rob.value == job.store.rob.value and item.query.rob.former != job.store.rob.former:
                    add("RAW-ORDER.former_latter", jobs=waits, positives=(item.uid,))
                if item.query.rob.flag != job.store.rob.flag:
                    add("RAW-ORDER.rob_wrap", jobs=waits, positives=(item.uid,))
            if not job.candidates:
                for item in change.before:
                    if (item.query.data_valid and item.rob_order > job.store_order and not job.store.wline
                            and ((item.query.paddr ^ job.store.paddr) & ((1 << 28) - 1)) >> 6 == 0
                            and not address_match(item.query, job.store)):
                        add("RAW-ADDRESS.word_miss", jobs=waits, positives=(item.uid,))
                new_matches = [item.uid for item in change.allocated if item.query.data_valid and item.rob_order > job.store_order
                               and address_match(item.query, job.store) and item.query.mask & job.store.mask]
                if new_matches:
                    add("RAW-PIPELINE.same_edge_new_excluded", jobs=waits, positives=new_matches)
            if job.winner is not None:
                item = job.winner
                if job.store.tlb_miss:
                    add("RAW-PIPELINE.tlb_miss", jobs=waits, positives=(item.uid,))
                add("RAW-ORDER.younger", jobs=waits)
                add("RAW-MASK.hit", jobs=waits)
                if ((item.query.paddr ^ job.store.paddr) & ((1 << 28) - 1)) >> 4 == 0:
                    add("RAW-ADDRESS.word_hit", jobs=waits)
                if job.store.wline and item.query.paddr >> 4 != job.store.paddr >> 4:
                    add("RAW-ADDRESS.wline", jobs=waits)
                if item.query.paddr >> 28 != job.store.paddr >> 28:
                    add("RAW-ADDRESS.truncated_alias", jobs=waits)
                if item.query.paddr >> 4 == job.store.paddr >> 4 and item.query.paddr != job.store.paddr:
                    add("RAW-ADDRESS.offset_ignored", jobs=waits)
                if (item.query.mask & job.store.mask).bit_count() == 1:
                    add("RAW-MASK.single_byte", jobs=waits)
                if len(job.candidates) > 1 and item.uid != min(job.candidates):
                    add("RAW-ORDER.not_insertion_order", jobs=waits)
                groups = {i.slot // model.spec["select_group_size"] for i in change.before if i.uid in job.candidates}
                if len(groups) > 1:
                    add("RAW-ORDER.cross_group", jobs=waits)
                if self.last_allocation_edge.get(item.uid) == model.edge - 1:
                    add("RAW-PIPELINE.adjacent_write", jobs=waits)
                if inp.redirect.valid:
                    add("RAW-REDIRECT.survivor", jobs=waits)
            if inp.redirect.valid:
                possible = [item.uid for item in change.before if item.query.data_valid and item.rob_order > job.store_order
                            and address_match(item.query, job.store) and item.query.mask & job.store.mask]
                if set(possible) - set(job.candidates):
                    add("RAW-REDIRECT.sample", jobs=waits, positives=possible)
        for job_uid in change.canceled_jobs:
            job = next(j for j in (*model.pending, *change.emitted) if j.uid == job_uid)
            age = model.edge - job.born
            add("RAW-REDIRECT." + ("group_stage" if age == 1 else "output_stage"), jobs=(job.uid,))
        if change.created:
            if (self.last_store_edge == model.edge - 1 and self.last_store_jobs
                    and all(job.winner is not None and not job.store.tlb_miss for job in (*self.last_store_jobs, *change.created))):
                add("RAW-PIPELINE.consecutive", jobs=(job.uid for job in (*self.last_store_jobs, *change.created)))
            self.last_store_edge = model.edge
            self.last_store_jobs = change.created
        if len(change.created) == 2:
            add("RAW-PIPELINE.both_ports", jobs=(job.uid for job in change.created))
        valid = [job for job in change.emitted if rollback_for(job).valid]
        if valid:
            add("RAW-PIPELINE.latency")
            add("RAW-ROLLBACK.metadata")
        if len(valid) == 2:
            add("RAW-TRAIN.oldest")
            if valid[0].winner.rob_order == valid[1].winner.rob_order:
                add("RAW-TRAIN.tie_lane0")
        if not post.training.valid:
            add("RAW-TRAIN.invalid")
        if change.perf_fire_source != change.perf_alloc_source:
            add("RAW-PERF.fire_not_alloc")
        if post.perf_fire == 3:
            add("RAW-PERF.three_fires")
        if self.rollback_history[0] == 2 and post.perf_rollback == 1:
            add("RAW-PERF.rollback_or")
        self.rollback_history.append(sum(rb.valid for rb in post.rollbacks))
        no_valid = not any(q.valid for q in inp.queries) and not any(s.valid for s in inp.stores) and not inp.redirect.valid and not any((*inp.revoke_last, *inp.revoke_older))
        if no_valid:
            add("RAW-IDLE.occupied" if change.before else "RAW-IDLE.empty")
            if any(q.paddr or q.mask or q.data_valid for q in inp.queries) or any(s.paddr or s.mask or s.tlb_miss for s in inp.stores):
                add("RAW-IDLE.disabled")
        self.freed_slots.update(f.item.slot for f in change.freed)
        self.last_allocation_edge.update({item.uid: model.edge for item in change.allocated})
        if inp.redirect.valid:
            self.negative_unsafe.update(job.uid for job in (*model.pending, *change.emitted))
        return scenes

    def confirm(self, scenes, inp, change, model, pre, post, tick):
        complete = []
        for job in change.emitted:
            self.completed_jobs.add(job.uid)
            if rollback_for(job).valid:
                self.witnessed.add(job.winner.uid)
                self.valid_jobs.add(job.uid)
        for uid, proof in self.full_free_states.items():
            if proof["slot"] in change.recycled_slots:
                proof["returned"] = True
            for item in change.allocated:
                if proof["returned"] and item.slot == proof["slot"] and proof["replacement"] is None:
                    proof["replacement"] = item.uid
            if proof["replacement"] in self.witnessed:
                self.capacity_freed.add(uid)
        negatives = [job for job in change.emitted if job.winner is None and not job.store.tlb_miss
                     and not job.canceled and job.uid not in self.negative_unsafe]
        def observes_absence(job, item, order):
            return item.data_valid and order > job.store_order and address_match(item, job.store) and bool(item.mask & job.store.mask)
        if self.reset_wait:
            for job in negatives:
                for uid, item in tuple(self.reset_old.items()):
                    if observes_absence(job, item.query, item.rob_order):
                        del self.reset_old[uid]
            if self.reset_eligible and self.witnessed and not self.reset_old:
                complete.append(self.reset_wait)
                self.reset_wait = None
        self.pending.extend(proof for scene, proof in scenes.items() if not scene.startswith("RAW-RESET.")
                            and scene not in ("RAW-CAPACITY.recovered", "RAW-DRAIN.return_latency"))
        pending = []
        for proof in self.pending:
            proof.jobs.difference_update(self.completed_jobs)
            if (proof.valid_jobs & self.completed_jobs) - self.valid_jobs:
                continue  # a canceled/miss response cannot prove a positive hit
            proof.valid_jobs.difference_update(self.valid_jobs)
            proof.positives.difference_update(self.witnessed)
            for job in negatives:
                if job.born > proof.born:
                    for uid, item in tuple(proof.removals.items()):
                        if (uid in self.witnessed or uid in self.capacity_freed) and observes_absence(job, item.query, item.rob_order):
                            del proof.removals[uid]
                if job.born == proof.born + 1:
                    proof.phantoms = [(order, query) for order, query in proof.phantoms if not observes_absence(job, query, order)]
            if not any((proof.jobs, proof.positives, proof.removals, proof.phantoms, proof.valid_jobs)):
                complete.append(proof.scene)
            else:
                pending.append(proof)
        self.pending = pending
        for proof in self.latency:
            if proof["kind"] == "recover" and change.allocated and model.edge > proof["edge"]:
                visible = {item.uid for item in change.allocated if item.query.data_valid and item.query.mask}
                if visible:
                    self.pending.append(Proof("RAW-CAPACITY.recovered", model.edge, positives=visible))
                    proof["done"] = True
            elif proof["kind"] == "latency":
                if model.edge == proof["edge"] + 1 and any(n and not pre.ready[lane] for lane, n in enumerate(change.needed)):
                    proof["nack"] = True
                if change.recycled_slots and model.edge > proof["edge"] + 1:
                    proof["recycled"] = True
                visible = any(need and post.ready[lane] and not pre.ready[lane] for lane, need in enumerate(change.needed))
                if proof["nack"] and proof.get("recycled") and visible:
                    complete.append("RAW-DRAIN.return_latency")
                    proof["done"] = True
        self.latency = [proof for proof in self.latency if not proof.get("done")]
        self.sample(complete, tick, checked=True)
