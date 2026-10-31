from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import selected
from .types import bitmap

SCENARIOS = {
    "AGE-RESET.initial": "初始复位后重建年龄并实际选择",
    "AGE-RESET.active": "非空池复位后只保留新年龄",
    "AGE-ORDER.single_enqueue": "单路插入建立可观察年龄",
    "AGE-ORDER.parallel_enqueue": "同拍多路插入遵守端口年龄",
    "AGE-ORDER.sparse_lanes": "稀疏端口插入仍按端口顺序",
    "AGE-ORDER.lane_order_vs_index": "端口年龄优先于数值ID大小",
    "AGE-ORDER.existing_older": "旧存活项均先于新到达项",
    "AGE-READY.none": "没有eligible项时没有选择",
    "AGE-READY.singleton": "只有一个eligible项时选择它",
    "AGE-READY.subset_excludes_oldest": "全局最老不ready时服务其他ready项",
    "AGE-READY.all_active": "全体ready时选真正最老项",
    "AGE-READY.changes_without_mutation": "只改ready不改变年龄顺序",
    "AGE-REMOVE.oldest": "删除最老项后其他项保持顺序并可复用",
    "AGE-REMOVE.non_oldest": "删除非最老项不改变幸存项顺序",
    "AGE-REMOVE.multiple": "同拍多个删除保持幸存顺序",
    "AGE-REMOVE.all": "删除整个池后可按新顺序重建",
    "AGE-REMOVE.empty_cleanup": "幂等清理无效ID不影响存活项",
    "AGE-OVERLAP.disjoint": "不同ID的同拍删/插分别生效",
    "AGE-OVERLAP.same_slot_deq_wins": "同ID同拍删除优先于插入",
    "AGE-REUSE.reinsert_is_youngest": "重用旧ID作为年轻项而非继承年龄",
    "AGE-REUSE.repeated_lifecycles": "同ID多轮复用不破坏年龄关系",
    "AGE-TIMING.old_state_not_lookahead": "边沿前选择旧最老而非提前删除它",
    "AGE-HOLD.idle_order": "没有年龄变更时关系保持",
    "AGE-POOL.full_forty": "全部40项均建立可查询的顺序",
    "AGE-POOL.high_entry": "36到39等高编号能被正确选择",
    "AGE-POOL.low_entry": "编号0同样遵循到达年龄",
}


class FunctionalCoverage:
    def __init__(self, key, nodeid):
        points = (CoverPointDef("scenario", {k: Bin.values(k) for k in SCENARIOS},
                               description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items())),)
        self.reached = CoverGroupDef("lsq.age.reached", points).instantiate(
            f"lsq.{key}.reached", run_metadata={"test": nodeid, "dut": key}, contract="age.observed-live-domain/v1")
        self.checked = CoverGroupDef("lsq.age.checked", points).instantiate(
            f"lsq.{key}.checked", run_metadata={"test": nodeid, "dut": key}, contract="age.selected-and-reinsert-proven/v1")
        self.pending = []
        self.reset_wait = None
        self.was_reset = False
        self.previous_ready = 0

    def sample(self, scenes, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenes:
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)

    def discover(self, obs, change, model):
        scenes = {}

        def add(scene, targets=(), reinserts=(), cancel_on_remove=True):
            scenes[scene] = {"scene": scene, "remaining": set(targets), "awaiting_enqueue": set(reinserts),
                             "cancel_on_remove": cancel_on_remove}

        if obs.reset:
            self.pending.clear()
            if not self.was_reset:
                self.reset_wait = "AGE-RESET." + change.reset_kind
                # Reset is reached now; checked only after a new nontrivial
                # age comparison, not merely an empty output during reset.
                add(self.reset_wait, ("reset-proof",))
            self.was_reset = True
            self.previous_ready = 0
            return scenes
        self.was_reset = False
        old = change.before
        ready = obs.ready_mask
        if not ready:
            add("AGE-READY.none")
        elif ready.bit_count() == 1:
            add("AGE-READY.singleton")
        if len(old) > 1:
            if ready == bitmap(old):
                add("AGE-READY.all_active")
            if ready and not ready >> old[0] & 1:
                add("AGE-READY.subset_excludes_oldest")
            if not any(obs.enqueue_masks) and not obs.remove_mask:
                if ready != self.previous_ready:
                    add("AGE-READY.changes_without_mutation")
                if ready.bit_count() > 1:
                    add("AGE-HOLD.idle_order")
        self.previous_ready = ready
        if change.inserted:
            add("AGE-ORDER.single_enqueue" if len(change.inserted) == 1 else "AGE-ORDER.parallel_enqueue", change.inserted)
            active_lanes = [i for i, mask in enumerate(obs.enqueue_masks) if mask]
            if active_lanes != list(range(len(active_lanes))):
                add("AGE-ORDER.sparse_lanes", change.inserted)
            if len(change.inserted) > 1 and change.inserted != tuple(sorted(change.inserted)):
                add("AGE-ORDER.lane_order_vs_index", change.inserted)
            survivors = tuple(item for item in old if item not in change.removed)
            if survivors:
                add("AGE-ORDER.existing_older", (*survivors, *change.inserted))
        if change.removed:
            for label, condition in (("oldest", old[0] in change.removed),
                                     ("non_oldest", any(item != old[0] for item in change.removed)),
                                     ("multiple", len(change.removed) > 1), ("all", len(change.removed) == len(old))):
                if condition:
                    add("AGE-REMOVE." + label, change.removed, change.removed, False)
        elif obs.remove_mask:
            add("AGE-REMOVE.empty_cleanup")
        if change.removed and change.inserted:
            add("AGE-OVERLAP.disjoint", (*change.removed, *change.inserted), change.removed, False)
        if change.conflicts:
            add("AGE-OVERLAP.same_slot_deq_wins", change.conflicts, change.conflicts, False)
        if change.reused:
            add("AGE-REUSE.reinsert_is_youngest", change.reused)
            if any(model.generations[item] >= 3 for item in change.reused):
                add("AGE-REUSE.repeated_lifecycles", change.reused)
        before_winner = selected(old, ready)
        if before_winner in change.removed and ready & bitmap(model.order):
            add("AGE-TIMING.old_state_not_lookahead")
        if len(model.order) == model.size and len(old) < model.size:
            add("AGE-POOL.full_forty", model.order)
        for order in (old, model.order):
            if not ready & ~bitmap(order):
                winner = selected(order, ready)
                if winner is not None and winner >= 36:
                    add("AGE-POOL.high_entry")
                if winner == 0:
                    add("AGE-POOL.low_entry")
        return scenes

    def confirm(self, scenes, pre, post, change, model, pre_winner, post_winner, post_valid, tick):
        if pre.reset:
            return
        completed = [scene for scene, proof in scenes.items() if not proof["remaining"]]
        self.pending.extend(proof for proof in scenes.values() if proof["remaining"])
        if self.reset_wait and ((pre.ready_mask.bit_count() > 1) or (post_valid and post.ready_mask.bit_count() > 1)):
            completed.append(self.reset_wait)
            self.reset_wait = None
        outstanding = []
        for proof in self.pending:
            waiting, remaining = proof["awaiting_enqueue"], proof["remaining"]
            if pre_winner is not None and pre_winner not in waiting:
                remaining.discard(pre_winner)
            waiting.difference_update(change.inserted)
            if post_valid and post_winner is not None and post_winner not in waiting:
                remaining.discard(post_winner)
            unproven_removed = remaining & set(change.removed)
            if unproven_removed and proof["cancel_on_remove"]:
                # Dropping an unselected lifecycle does not prove its age.
                continue
            if not proof["cancel_on_remove"]:
                waiting.update(unproven_removed)
            if remaining:
                outstanding.append(proof)
            else:
                completed.append(proof["scene"])
        self.pending = outstanding
        self.sample(completed, tick, checked=True)
