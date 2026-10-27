"""Readable behavior bins; positive proofs wait for actual feedback release."""
from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "LRQ-RESET.initial": "初始复位后新事务真实重放并反馈完成",
    "LRQ-RESET.active": "活动复位中止旧义务后新身份完成",
    "LRQ-ADMIT.single": "单条需要重放的首次请求建立一个所有者",
    "LRQ-ADMIT.partial": "两个首次请求压紧分配且分别完成",
    "LRQ-ADMIT.full": "三路首次请求都保存并分别完成",
    "LRQ-ADMIT.sparse": "稀疏输入不浪费预分配槽位",
    "LRQ-ADMIT.no_need": "need_rep为假不隐藏占用槽位",
    "LRQ-ADMIT.redirect": "已被当前redirect取消的新请求不分配",
    "LRQ-OWNER.wait_feedback": "实际调度握手后保持占用直到反馈",
    "LRQ-OWNER.done": "不再重放的反馈真实释放原所有者",
    "LRQ-OWNER.rereplay": "再次重放在原slot更新而不新增分配",
    "LRQ-OWNER.changed_cause": "反馈可以改变阻塞原因且新依赖正确生效",
    "LRQ-OWNER.other_lane": "反馈从其他LDU入口返回仍释放正确所有者",
    "LRQ-BANK.all_slots": "全部120项都经实际输出和反馈完成证明",
    "LRQ-BANK.parallel": "三个真实bank并行输出不同所有者",
    "LRQ-BANK.input_migration": "输入lane不决定输出bank归属",
    "LRQ-ORDER.age": "bank内按首次入队年龄而非槽号或最近反馈选择",
    "LRQ-ORDER.priority": "普通选择高组优先但保留低组进展",
    "LRQ-ORDER.head": "ldWbPtr相等项覆盖一般年龄与原因优先级",
    "LRQ-ORDER.near_head": "头后1至3项覆盖一般选择且按bank索引仲裁",
    "LRQ-ORDER.wrap": "LQ120回绕的头窗口不按2幂截断",
    "LRQ-HOLD.stable": "消费者背压保持同一UID和完整payload",
    "LRQ-HOLD.replace": "同拍接受旧重放与装入新选择不串请求",
    "LRQ-COOLDOWN.continuous": "连续重放达到冷却边界但不重复已发请求",
    "LRQ-COOLDOWN.interrupted": "非连续握手按规定打断连续计数",
    "LRQ-COOLDOWN.cancel": "取消可以清理冷却中的旧选择",
    "LRQ-STORE.address_pointer": "store地址ready指针越过阻塞SQ才解除等待",
    "LRQ-STORE.address_bits": "非strict地址依赖用真实物理ready位与upper解除",
    "LRQ-STORE.strict": "strict地址依赖不凭ready位提前重放",
    "LRQ-STORE.strict_capacity": "全池无预分配余量时严格地址依赖仍不凭ready位解除",
    "LRQ-STORE.strict_valid_only": "禁用反馈payload不能清除活动load的严格依赖属性",
    "LRQ-STORE.address_wakeup": "延迟地址wakeup按完整SQ及物理窗口匹配",
    "LRQ-STORE.data_pointer": "数据ready指针或ready位解除转发失败等待",
    "LRQ-STORE.data_wakeup": "延迟STD wakeup按完整SQ匹配",
    "LRQ-STORE.actual_write": "真实storeDataWrite与新FF同拍可直接非阻塞",
    "LRQ-STORE.sq_empty": "SQ确实为空时不再等待已不存在的store",
    "LRQ-STORE.wrap": "SQ两个flag与四圈年龄保持正确",
    "LRQ-TLB.slow": "慢TLB hint按本地延迟和ID匹配解除",
    "LRQ-TLB.fast": "fast TLB hint可直接加入当前选择候选",
    "LRQ-TLB.all": "慢TLB replay_all解除全部相关等待",
    "LRQ-TLB.full": "tlb_full反馈无需等待普通TLB hint",
    "LRQ-TLB.history": "S4延迟头可接受额外历史hint而普通项不接受",
    "LRQ-TLB.mismatch": "错误ID或过期hint不能错误解锁",
    "LRQ-REFILL.delayed": "延迟refill按MSHR匹配解除cache miss",
    "LRQ-REFILL.history": "新入队按普通或S4历史refill窗口处理",
    "LRQ-REFILL.beats": "L2 keyword和lastBeat决定准确解锁边沿",
    "LRQ-REFILL.mismatch": "错MSHR及过期hint不污染旧新事务",
    "LRQ-REFILL.channels": "两个内存channel都能唤醒各自请求",
    "LRQ-UNCACHE.mmio": "MMIO wakeup按完整LQ身份解除等待",
    "LRQ-UNCACHE.nc": "NC wakeup按完整LQ身份解除等待",
    "LRQ-UNCACHE.mismatch": "错误LQ flag或索引不能解锁不可缓存load",
    "LRQ-PAYLOAD.scalar": "scalar访问按op size和vaddr生成有效mask",
    "LRQ-PAYLOAD.vector": "vector保留alignedType和输入mask",
    "LRQ-PAYLOAD.metadata": "ROB/FTQ/恢复身份/目的寄存器和写使能逐字段保留",
    "LRQ-PAYLOAD.pool_checkpoint": "全120项恢复checkpoint经每个真实输出握手保持，反馈前不释放",
    "LRQ-RECYCLE.public_slots": "两生命周期公开槽号均完整覆盖120项且新旧checkpoint不串用",
    "LRQ-PAYLOAD.exceptions": "写入时清除源异常而非重放旧异常",
    "LRQ-PAYLOAD.ff_entrance": "FF属于选择高组但输出entrance仍为低组编码",
    "LRQ-FLUSH.blocked": "阻塞所有者可被redirect释放并安全重用",
    "LRQ-FLUSH.selected": "当前重定向抑制待发选择的valid",
    "LRQ-FLUSH.issued": "已发但未反馈的年轻项取消且不再出现",
    "LRQ-FLUSH.age": "former/latter和ROB回绕决定正确幸存者",
    "LRQ-FLUSH.overlap": "正常反馈与redirect同拍不重复归还slot",
    "LRQ-RECYCLE.full": "满120项后的真实回收与预取等待恢复容量",
    "LRQ-RECYCLE.banks": "同/跨4回收通道积压后新UID完整重放",
    "LRQ-RECYCLE.many_rounds": "多次非2幂全池循环不串旧身份或MSHR",
    "LRQ-SPECIAL.threshold": "ROB头稳定2048边界后才进入特殊模式",
    "LRQ-SPECIAL.head_moves": "ROB头移动含former/latter变化解除模式",
    "LRQ-SPECIAL.not_eligible": "非eligible或被取消的输入不启动窗口",
    "LRQ-SPECIAL.rereplay": "再次重放与原因更新不重启已有窗口",
    "LRQ-SPECIAL.request": "特殊模式的年轻C_TM标记不等待常规hint",
    "LRQ-PERF.events": "全部13公开事件按真实条件和两级时序比较",
    "LRQ-IDLE.empty": "空闲所有valid安静且没有隐藏占用",
    "LRQ-IDLE.disabled": "禁用payload不制造分配或唤醒",
    **{f"LRQ-CAUSE.{cause}": f"合法原因{cause}在满足其依赖后实际重放并反馈完成" for cause in range(12)},
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS},
                              description="; ".join(f"{key}: {value}" for key, value in SCENARIOS.items()))
        metadata = {"test": nodeid, "dut": "load_queue_replay"}
        self.reached = CoverGroupDef("lsq.replay.reached", (point,)).instantiate(
            "lsq.load_queue_replay.reached", run_metadata=metadata, contract="replay.observed-semantic-obligations/v1")
        self.checked = CoverGroupDef("lsq.replay.checked", (point,)).instantiate(
            "lsq.load_queue_replay.checked", run_metadata=metadata, contract="replay.actual-output-then-feedback-release-or-cancel-then-reuse/v1")
        self.proofs = []
        self.completed = set()
        self.canceled = set()
        self.completed_slots = set()
        self.reset_scene = None

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)

    def arm(self, names, uids, tick, sequence, *, reuse=False):
        if isinstance(names, str):
            names = (names,)
        self.sample(names, tick)
        self.proofs.extend((name, set(uids), reuse, sequence) for name in names)

    def observe(self, inp, change, model, tick):
        if change["reset"]:
            self.proofs.clear()
            self.completed.clear()
            self.canceled.clear()
            self.completed_slots.clear()
            scene = "LRQ-RESET.active" if change["before"] or self.reset_scene == "LRQ-RESET.active" else "LRQ-RESET.initial"
            self.reset_scene = scene
            self.sample((scene,), tick)
            return
        allocated = change["allocated"]
        if allocated:
            scenes = ["LRQ-ADMIT." + {1: "single", 2: "partial", 3: "full"}[len(allocated)]]
            if sum(1 << owner["input_lane"] for owner in allocated) != (1 << len(allocated)) - 1:
                scenes.append("LRQ-ADMIT.sparse")
            self.arm(scenes, [owner["uid"] for owner in allocated], tick, model.sequence)
            for owner in allocated:
                req = owner["request"]
                names = [f"LRQ-CAUSE.{req['causes'].bit_length() - 1}", "LRQ-PAYLOAD.vector" if req["vector"] else "LRQ-PAYLOAD.scalar", "LRQ-PAYLOAD.metadata"]
                if req["uop"]["exceptions"]:
                    names.append("LRQ-PAYLOAD.exceptions")
                self.arm(names, [owner["uid"]], tick, model.sequence)
        before = {owner["uid"]: owner for owner in change["before"]}
        if change["fired"]:
            self.arm(("LRQ-OWNER.wait_feedback", "LRQ-OWNER.done"), change["fired"], tick, model.sequence)
            if len(change["fired"]) == 3:
                self.arm("LRQ-BANK.parallel", change["fired"], tick, model.sequence)
            for uid in change["fired"]:
                owner = before[uid]
                if owner["slot"] % 3 != owner["input_lane"]:
                    self.arm("LRQ-BANK.input_migration", [uid], tick, model.sequence)
                if owner["request"]["causes"] == 1 << 4:
                    self.arm("LRQ-PAYLOAD.ff_entrance", [uid], tick, model.sequence)
        if change["updates"]:
            self.arm("LRQ-OWNER.rereplay", change["updates"], tick, model.sequence)
            for uid in change["updates"]:
                latest = next(owner for owner in model.owners.values() if owner.uid == uid)
                if before[uid]["request"]["causes"] != latest.request.causes:
                    self.arm("LRQ-OWNER.changed_cause", [uid], tick, model.sequence)
        self.completed.update(change["completed"])
        for owner in change["freed"]:
            if owner["uid"] in self.completed:
                self.completed_slots.add(owner["slot"])
            else:
                self.canceled.add(owner["uid"])
        if self.reset_scene and change["completed"]:
            self.sample((self.reset_scene,), tick, checked=True)
            self.reset_scene = None
        if self.completed_slots == set(range(120)):
            self.sample(("LRQ-BANK.all_slots",), tick)
            self.sample(("LRQ-BANK.all_slots",), tick, checked=True)
        pending = []
        for name, uids, reuse, since in self.proofs:
            done = uids <= (self.canceled if reuse else self.completed)
            if reuse:
                done &= any(uid > since for uid in self.completed)
            if done:
                self.sample((name,), tick, checked=True)
            else:
                pending.append((name, uids, reuse, since))
        self.proofs = pending
