from toffee import Bin, CoverGroupDef, CoverPointDef


SCENARIOS = {
    "VSQ-REDIRECT.capacity_suffix": "取消4至128虚拟uop，公开exclusive尾精确且每个取消虚拟槽新UID正常退休",
    "VSQ-WALK.prefix_windows": "退休前缀1/8/9/59与恢复相位交错，公开exclusive尾保持并同槽新UID正常退休",
    "VSQ-REDIRECT.deep_suffix": "公开redirect一次取消至少八个年轻UID，cancelCount高位与exclusive尾、后续新UID复用均真实检查",
    "VSQ-RETIRE.batch_width": "八个四flow uop一次正常退休，总physical flow=32且公开退休尾精确前进",
    "VSQ-RESET.initial": "复位后公开tail/retired/empty收敛且新UID退休",
    "VSQ-RESET.active": "活动uop被reset中止后新UID退休",
    "VSQ-RESET.recovery": "恢复中reset不泄漏旧redirect或快照",
    **{f"VSQ-ADMIT.lane{lane}": f"dispatch入口{lane}保存快照并实际退休" for lane in range(8)},
    "VSQ-ADMIT.dense": "八入口同时接受按lane顺序压紧",
    "VSQ-ADMIT.sparse": "稀疏入口压紧不留下虚拟空洞",
    "VSQ-ADMIT.need_alloc": "有效非store请求不分配或污染tail",
    "VSQ-ADMIT.disabled": "无效请求的旧payload不保存",
    "VSQ-INTERVAL.zero": "零flow uop保留虚拟身份但不增加物理位置",
    "VSQ-INTERVAL.one": "单flow快照与退休物理位置一致",
    "VSQ-INTERVAL.multi": "多flow退休按flow和而不是uop个数",
    "VSQ-INTERVAL.maximum": "16flow上限保存完整exclusive end",
    "VSQ-SNAPSHOT.all_slots": "128个虚拟槽后续真实许可或退休",
    "VSQ-SNAPSHOT.flags": "物理end跨64/128/256保留双flag身份",
    "VSQ-ORDER.head_block": "未退休head阻止年轻记录越过",
    "VSQ-ORDER.batch8": "连续八项退休前缀按物理flow总和更新",
    "VSQ-ORDER.short": "尾部短前缀只退休现有uop",
    "VSQ-PRECOMMIT.head": "恰在ROB head仅预提交而非退休",
    "VSQ-PRECOMMIT.multi_uop": "同ROB slot多个uop逐个许可其end",
    "VSQ-PRECOMMIT.slot": "former/latter区分ROB同entry的两个slot",
    "VSQ-PRECOMMIT.payload": "许可end与headRobIdx来自同一uop",
    "VSQ-RETIRE.rob": "ROB head越过store才真实退休",
    "VSQ-RETIRE.latency": "退休flow总和按规定流水相位出现",
    "VSQ-RETIRE.no_duplicate": "退休后空闲不重复推进物理位置",
    "VSQ-RELEASE.precommit": "PSQ消费已许可store可释放VSQ",
    "VSQ-RELEASE.partial": "多flow仅部分消费不提前释放uop",
    "VSQ-RELEASE.pulse": "静态deqPtr没有消费valid不释放",
    "VSQ-RELEASE.two": "双flow实际消费可同时释放两个uop",
    "VSQ-REDIRECT.flush_self": "恢复取消cutoff自身和年轻后缀",
    "VSQ-REDIRECT.flush_after": "恢复保留cutoff而取消年轻后缀",
    "VSQ-REDIRECT.none": "零取消仍返回最后幸存end",
    "VSQ-REDIRECT.partial": "部分取消恢复到幸存最后end",
    "VSQ-REDIRECT.all": "全取消恢复到已退休物理位置",
    "VSQ-REDIRECT.rob_flags": "ROB跨160环绕的年龄恢复正确",
    "VSQ-REDIRECT.slots": "恢复精确区分former/latter slot",
    "VSQ-WALK.direct": "无需退休release时直接恢复",
    "VSQ-WALK.release_first": "先释放已退休head再walk取消年轻项",
    "VSQ-WALK.head_snapshot": "release期间ROB head变化不改变锁存范围",
    "VSQ-RECOVER.empty": "空队列恢复不读取旧快照作为有效tail",
    "VSQ-RECOVER.stall": "恢复流水整个窗口阻止新dispatch",
    "VSQ-RECOVER.adjacent": "相邻恢复不产生错误重复回退",
    "VSQ-RACE.dispatch_redirect": "恢复碰撞dispatch不留下幽灵uop",
    "VSQ-RACE.retire_release": "ROB退休与PSQ消费不重复记账",
    "VSQ-REUSE.cancel": "取消后同虚拟区间新UID实际退休",
    "VSQ-REUSE.wrap": "虚拟128项回绕后的新快照真实退休",
    "VSQ-CAPACITY.virtual": "虚拟uop容量与物理flow容量分开检查",
    "VSQ-IDLE.quiet": "空闲无伪恢复或物理位置推进",
    "VSQ-CONCURRENT.seeded": "合法并发固定种子最终守恒排空",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS}, description="; ".join(f"{key}: {value}" for key, value in SCENARIOS.items()))
        metadata = {"dut": "virtual_store_queue", "test": nodeid}
        self.reached = CoverGroupDef("lsq.vsq.reached", (point,)).instantiate("lsq.virtual_store_queue.reached", run_metadata=metadata, contract="public-dispatch-rob-psq.observed/v1")
        self.checked = CoverGroupDef("lsq.vsq.checked", (point,)).instantiate("lsq.virtual_store_queue.checked", run_metadata=metadata, contract="public-end-precommit-retired-recovery.checked/v1")
        self.pending, self.completed, self.canceled = [], set(), set()
        self.events = []

    def sample(self, names, tick, *, checked=False, uids=()):
        for name in names:
            assert name in SCENARIOS
            self.events.append({"scenario": name, "tick": tick, "checked": checked, "uids": sorted(uids)})
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)

    def arm(self, names, uids, tick):
        if isinstance(names, str):
            names = (names,)
        assert uids
        self.sample(names, tick, uids=uids)
        self.pending.extend((name, set(uids)) for name in names)

    def observe(self, change, tick):
        for item in change["accepted"]:
            self.arm((f"VSQ-ADMIT.lane{item['lane']}", "VSQ-RESET.initial"), [item["uid"]], tick)
        self.completed.update(item["uid"] for item in change["retired"])
        self.canceled.update(item["uid"] for item in change["canceled"])
        assert not self.completed & self.canceled
        pending = []
        for name, uids in self.pending:
            if uids <= self.completed:
                self.sample((name,), tick, checked=True, uids=uids)
            else:
                pending.append((name, uids))
        self.pending = pending
