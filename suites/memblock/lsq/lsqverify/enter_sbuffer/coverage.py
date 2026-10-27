from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "ESB-RESET.initial": "初始清空后新写请求真实消费",
    "ESB-RESET.one_live": "一项在途复位中止后新身份完成",
    "ESB-RESET.two_live": "两项在途复位中止后新身份完成",
    "ESB-RESET.wrapped": "指针回绕的活动复位不泄露旧内容",
    "ESB-ADMIT.single": "单项接受并保序交给Sbuffer",
    "ESB-ADMIT.pair": "两项同时接受且数据各自保留",
    "ESB-ADMIT.partial_accept": "只接受较老前缀并在下拍压紧未接受项",
    "ESB-ADMIT.disabled": "无效输入不制造写请求",
    "ESB-ORDER.fifo": "按实际接受而非尝试顺序写出",
    "ESB-ORDER.lane_compaction": "原lane1项在头消费后移到lane0",
    "ESB-ORDER.wrap": "多轮两项回绕不串旧数据",
    "ESB-HOLD.head": "单项背压不变且不产生credit",
    "ESB-HOLD.both": "双项背压分别保持payload",
    "ESB-HOLD.tail_after_head": "只消费头后第二项继续保持",
    "ESB-REUSE.one_to_one": "单出单入同拍不丢幸存请求",
    "ESB-REUSE.two_to_two": "满队列双出双入仍比较旧请求",
    "ESB-REUSE.one_to_two": "单项出队后同拍接受两项",
    "ESB-REUSE.two_to_one": "双项出队后同拍只接受一项",
    "ESB-REUSE.full_block": "无真实消费的满队列拒绝新输入",
    "ESB-REUSE.consecutive": "连续拍满吞吐不出现伪空或重复消费",
    "ESB-CREDIT.ordinary": "普通写请求实际消费恰产生一次SQ释放",
    "ESB-CREDIT.split_pair": "同拍消费拆分两半只释放一个SQ项",
    "ESB-CREDIT.split_separate": "拆分两半分拍消费仍只有第二半释放",
    "ESB-CREDIT.zero_credit": "无credit写请求已消费但不释放SQ",
    "ESB-CREDIT.same_cycle_old_flag": "同槽重写不把新credit误用于旧消费",
    "ESB-PAYLOAD.data_bits": "128位数据walking one/zero逐位实际写出",
    "ESB-PAYLOAD.mask_bits": "16位mask原样保存而非按地址再生成",
    "ESB-PAYLOAD.address_bits": "物理48及虚拟50地址高低位完整保留",
    "ESB-PAYLOAD.wline": "整行写属性与字节写属性不串单",
    "ESB-PAYLOAD.input_lane": "两路输入的独特内容均真实消费",
    "ESB-IDLE.empty_ready": "空队列即便消费者ready也无伪消费",
    "ESB-IDLE.disabled_noise": "禁用payload变化不污染真实待发请求",
    "ESB-CONCURRENT.seeded": "合法前缀随机最终按接受顺序完整排空",
    "ESB-CONCURRENT.throughput": "持续双宽流量在公平消费下完整交付",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS},
                              description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items()))
        metadata = {"dut": "enter_sbuffer_queue", "test": nodeid}
        self.reached = CoverGroupDef("lsq.enter_sbuffer.reached", (point,)).instantiate(
            "lsq.enter_sbuffer_queue.reached", run_metadata=metadata, contract="committed-write.observed/v1")
        self.checked = CoverGroupDef("lsq.enter_sbuffer.checked", (point,)).instantiate(
            "lsq.enter_sbuffer_queue.checked", run_metadata=metadata, contract="actual-sbuffer-consumption-and-credit-check/v1")
        self.proofs, self.completed = [], set()
        self.reset_scene = None

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)

    def arm(self, names, uids, tick):
        if isinstance(names, str):
            names = (names,)
        assert uids, "positive lifecycle bins require a real accepted UID"
        self.sample(names, tick)
        self.proofs.extend((name, set(uids)) for name in names)

    def observe(self, change, tick):
        if change["reset"]:
            if change["before"]:
                self.reset_scene = "ESB-RESET." + ("one_live" if len(change["before"]) == 1 else "two_live")
            elif self.reset_scene is None:
                self.reset_scene = "ESB-RESET.initial"
            self.sample((self.reset_scene,), tick)
            self.proofs.clear()
            self.completed.clear()
            return
        accepted, consumed = change["accepted"], change["consumed"]
        if accepted:
            self.arm("ESB-ADMIT.single" if len(accepted) == 1 else "ESB-ADMIT.pair", [x["uid"] for x in accepted], tick)
            self.arm(("ESB-ORDER.fifo", "ESB-PAYLOAD.input_lane"), [x["uid"] for x in accepted], tick)
            for item in accepted:
                self.arm("ESB-CREDIT.ordinary" if item["write"]["credit"] else "ESB-CREDIT.zero_credit", [item["uid"]], tick)
        self.completed.update(x["uid"] for x in consumed)
        if consumed and self.reset_scene:
            self.sample((self.reset_scene,), tick, checked=True)
            self.reset_scene = None
        pending = []
        for name, uids in self.proofs:
            if uids <= self.completed:
                self.sample((name,), tick, checked=True)
            else:
                pending.append((name, uids))
        self.proofs = pending
