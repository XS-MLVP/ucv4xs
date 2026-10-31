from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "UQ-PAGE.paired_lifetimes": "两槽高低第二页背压保持、满池第三请求等待到真实接受消费并正常复用",
    "UQ-RESET.initial": "初始复位后新第二页请求完成",
    "UQ-RESET.one_live": "单条在途复位后新身份完成",
    "UQ-RESET.two_live": "两条在途复位后新身份完成",
    "UQ-RESET.wrapped": "回绕后的复位不泄漏旧页",
    "UQ-ADMIT.lane0": "STA入口0匹配完整SQ后接受",
    "UQ-ADMIT.lane1": "STA入口1匹配完整SQ后接受",
    "UQ-ADMIT.value": "错误SQ值不接受而正确身份可完成",
    "UQ-ADMIT.first_flag": "相同物理SQ但first flag不同不误收",
    "UQ-ADMIT.second_flag": "相同物理SQ但second flag不同不误收",
    "UQ-ADMIT.multiple_valid": "双入口valid但只有当前addrReady身份被收",
    "UQ-CAPACITY.two": "两个活跃第二页各自保留并依序消费",
    "UQ-CAPACITY.full": "无消费满池不覆盖旧地址",
    "UQ-CAPACITY.no_same_cycle_reuse": "满池同拍消费不偷接下一请求",
    "UQ-CAPACITY.no_flow": "空池无组合直通或入队即消费",
    "UQ-ORDER.fifo": "SQ顺序与实际head消费顺序一致",
    "UQ-ORDER.gaps": "跨页store之间允许普通SQ项间隙",
    "UQ-ORDER.wrap": "两个物理槽多次回绕不串旧身份",
    "UQ-PAGE.bits": "高36位页号walking one/zero完整保存",
    "UQ-PAGE.offset": "输入页内offset被清零而非泄漏",
    "UQ-PAGE.input_lane": "两个STA入口到两个公开forward槽正确",
    "UQ-FORWARD.slot0": "物理槽0活跃页可见并随后真实消费",
    "UQ-FORWARD.slot1": "物理槽1活跃页可见并随后真实消费",
    "UQ-FORWARD.same_page": "不同SQ指向相同第二页仍各自保留",
    "UQ-FORWARD.different_pages": "两个页与SQ不被错误混合",
    "UQ-HOLD.stable": "背压下head和forward页保持",
    "UQ-REDIRECT.equal": "等于SQ恢复指针的条目也被取消",
    "UQ-REDIRECT.younger": "年轻后缀取消不影响更老前缀",
    "UQ-REDIRECT.none": "恢复指针之后无在途项则不误删",
    "UQ-REDIRECT.all": "两项均取消并可完整复用",
    "UQ-REDIRECT.last": "只取消最后一项并回退尾部",
    "UQ-REDIRECT.flags": "完整SQ四圈flag及边界决定取消年龄",
    "UQ-REDIRECT.repeated": "连续恢复空拍不重复删除或回退",
    "UQ-REDIRECT.block_enqueue": "恢复拍即便SQ匹配也不接受输入",
    "UQ-REDIRECT.consume_survivor": "真实消费较老head与取消年轻尾同拍",
    "UQ-REUSE.consume": "消费过的槽保存新SQ及新页",
    "UQ-REUSE.cancel": "被取消槽以新UID实际完成证明可复用",
    "UQ-REUSE.rollback": "恢复尾部回退后槽归属正确",
    "UQ-IDLE.empty": "空闲ready不制造伪head或forward",
    "UQ-IDLE.disabled": "禁用请求噪声不修改活跃页",
    "UQ-CONCURRENT.seeded": "合法输入和恢复压力下最终公平排空",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS}, description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items()))
        metadata = {"dut": "unalign_queue", "test": nodeid}
        self.reached = CoverGroupDef("lsq.unalign.reached", (point,)).instantiate("lsq.unalign_queue.reached", run_metadata=metadata, contract="second-page.observed/v1")
        self.checked = CoverGroupDef("lsq.unalign.checked", (point,)).instantiate("lsq.unalign_queue.checked", run_metadata=metadata, contract="actual-head-consumption-or-same-slot-new-uid-consumption/v1")
        self.completed, self.canceled, self.proofs = {}, set(), []
        self.reset_scene = None

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)

    def arm(self, names, owners, tick, sequence, *, reuse=False):
        if isinstance(names, str):
            names = (names,)
        assert owners
        self.sample(names, tick)
        self.proofs.extend((name, {x["uid"] for x in owners}, {x["slot"] for x in owners}, sequence, reuse) for name in names)

    def observe(self, change, tick, sequence):
        if change["reset"]:
            if change["before"]:
                self.reset_scene = "UQ-RESET." + ("one_live" if len(change["before"]) == 1 else "two_live")
            elif self.reset_scene is None:
                self.reset_scene = "UQ-RESET.initial"
            self.sample((self.reset_scene,), tick)
            self.completed.clear()
            self.canceled.clear()
            self.proofs.clear()
            return
        for owner in change["accepted"]:
            self.arm((f"UQ-ADMIT.lane{owner['input_lane']}", "UQ-ORDER.fifo", f"UQ-FORWARD.slot{owner['slot']}", "UQ-PAGE.input_lane"), [owner], tick, sequence)
        self.completed.update({x["uid"]: x["slot"] for x in change["consumed"]})
        self.canceled.update(x["uid"] for x in change["canceled"])
        if change["consumed"] and self.reset_scene:
            self.sample((self.reset_scene,), tick, checked=True)
            self.reset_scene = None
        pending = []
        for name, uids, slots, since, reuse in self.proofs:
            done = uids <= (self.canceled if reuse else self.completed.keys())
            if reuse:
                done &= slots <= {slot for uid, slot in self.completed.items() if uid > since}
            if done:
                self.sample((name,), tick, checked=True)
            else:
                pending.append((name, uids, slots, since, reuse))
        self.proofs = pending
