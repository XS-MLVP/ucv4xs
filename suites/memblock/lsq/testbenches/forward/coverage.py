from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "FWD-WINDOW.prefix_byte": "非满与跨环窗口中Load独占SQ前缀排除已写年轻同址字节，三路逐槽字节检查",
    "FWD-PAYLOAD.pool": "64槽高低地址全宽128位四代含槽号图样在三路实际S2逐字节保持来源",
    "FWD-PIPE.warmup": "无reset接口通过无效查询排空后新UID完成",
    "FWD-PIPE.latency": "S0和对应S1 PA在规定S2相位产生唯一结果",
    **{f"FWD-PIPE.lane{lane}": f"独立load查询入口{lane}完整结果检查" for lane in range(3)},
    "FWD-PIPE.back_to_back": "同lane连续请求不串地址与选择快照",
    "FWD-PIPE.holes": "查询空洞不重复输出旧UID",
    "FWD-PIPE.kill": "S1 kill不产生S2有效结果",
    "FWD-PIPE.kill_reuse": "取消后新UID实际完成不带旧payload",
    "FWD-AGE.old_only": "仅程序较老store可提供字节",
    "FWD-AGE.young_excluded": "年轻物理命中不参与转发或假重放",
    "FWD-AGE.retired_excluded": "已出队槽不参与当前候选域",
    "FWD-AGE.window_limit": "物理upper裁剪虚拟SQ前缀",
    "FWD-AGE.flags": "双flag四圈身份决定年龄与等待目标",
    "FWD-AGE.wrap": "跨64物理回绕仍选择程序最年轻",
    "FWD-AGE.all_slots": "64个物理slot都实际选中并检查",
    "FWD-SELECT.single": "单store有效转发数据和mask",
    "FWD-SELECT.youngest": "多个VA候选选择最年轻的较老store",
    "FWD-SELECT.no_fallback": "最年轻者无数据时不回退旧值",
    "FWD-SELECT.multi_partial": "多候选但不完整覆盖时重放",
    "FWD-SELECT.full": "最年轻者完整覆盖时可转发",
    "FWD-BYTE.sizes": "1/2/4/8/16字节范围与返回位置正确",
    "FWD-BYTE.q_encodings": "MemorySize4至7均为16字节",
    "FWD-BYTE.offsets": "16个字节起点旋转和截取正确",
    "FWD-BYTE.mask": "store原始mask孔洞不被填造有效字节",
    "FWD-BYTE.partial": "部分字节与范围交界逐字节检查",
    "FWD-BYTE.range_mask": "跨16B旋转不把另一段字节标到本段未覆盖地址",
    "FWD-BYTE.no_overlap": "无范围重叠不制造候选",
    "FWD-CROSS.same_word": "当前16B段的未对齐store字节正确",
    "FWD-CROSS.next_word": "同页下一16B段按store相对字节选择",
    "FWD-CROSS.page_boundary": "VA页边界不错误长进位匹配",
    "FWD-VAPA.agree": "VA/PA集合一致时有效字节来源正确",
    "FWD-VAPA.disagree": "同VA不同PA必须要求重放",
    "FWD-VAPA.alias": "物理别名不能隐藏更年轻store",
    "FWD-VAPA.alias_cross_word": "跨16B的物理别名不能返回旧word安全值",
    "FWD-VAPA.physical_only": "仅物理命中也不能假装无相关store",
    "FWD-REG.alias_6693": "88fb444c5的VA1旧store和VA2年轻同PA复现需重放",
    "FWD-REG.negative_young": "晚于load的别名不会错误参与",
    "FWD-REG.negative_invalid": "无效地址store的别名不会错误参与",
    "FWD-REG.negative_disjoint": "无字节重叠物理命中不产生假违例",
    "FWD-WAIT.strict": "strict等待所有较老未就绪地址",
    "FWD-WAIT.address": "未知store地址不被当成安全候选",
    "FWD-WAIT.data": "有效候选缺数据返回完整SQ依赖",
    "FWD-WAIT.precise": "非strict只等待当前MDP预测目标",
    "FWD-WAIT.retired": "预测目标已退休不再等待",
    "FWD-WAIT.outside": "预测目标超物理窗口需要等待",
    "FWD-WAIT.identity": "依赖SQ包含双flag而非仅物理索引",
    "FWD-WAIT.clipped_identity": "load跨代且被物理upper裁剪时仍返回原store的完整SQ依赖",
    "FWD-CBO.zero": "CBO.zero可提供有效零数据",
    "FWD-CBO.other": "其他CBO子类型必须要求重放",
    "FWD-CBO.line": "CBO同cacheline匹配不同16B子段",
    "FWD-UQ.lane0": "跨页页入口0按较老SQ要求重放",
    "FWD-UQ.lane1": "跨页页入口1按较老SQ要求重放",
    "FWD-UQ.young": "年轻或同SQ页不错误要求重放",
    "FWD-UQ.disabled": "禁用旧页及flag不影响有效查询",
    "FWD-UQ.flags": "第二页匹配比较完整SQ四圈年龄",
    "FWD-LIVE.data_snapshot": "S1所选data快照不被后续bank更新串改",
    "FWD-LIVE.physical_cam": "S2物理CAM按live输入重新核对原候选域",
    "FWD-LIVE.mdp": "S2精确MDP按当前addrValid解除等待",
    "FWD-LIVE.boundaries": "S0年龄快照和S2当前指针不被混用",
    "FWD-REUSE.identity": "复用物理slot后新UID的数据身份正确",
    "FWD-IDLE.quiet": "无效查询不制造S2义务",
    "FWD-IDLE.disabled": "禁用或无关slot payload不污染候选",
    "FWD-CONCURRENT.seeded": "合法并发随机查询最终管线排空",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS}, description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items()))
        metadata = {"dut": "forward_module", "test": nodeid}
        self.reached = CoverGroupDef("lsq.forward.reached", (point,)).instantiate("lsq.forward_module.reached", run_metadata=metadata, contract="load-forward-query.observed/v1")
        self.checked = CoverGroupDef("lsq.forward.checked", (point,)).instantiate("lsq.forward_module.checked", run_metadata=metadata, contract="actual-s2-flags-and-data-with-physical-byte-safety/v1")
        self.pending, self.completed, self.killed = [], set(), set()
        self.events, self.kill_reuse = [], []

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
        for job in change["accepted"]:
            self.arm((f"FWD-PIPE.lane{job['lane']}", "FWD-PIPE.latency", "FWD-PIPE.warmup"), [job["uid"]], tick)
        self.killed.update(job["uid"] for job in change["killed"])
        self.completed.update(answer["uid"] for answer in change["responses"])
        assert not self.killed & self.completed, "killed UID must never get a valid response"
        pending = []
        for name, uids in self.pending:
            if uids <= self.completed:
                self.sample((name,), tick, checked=True, uids=uids)
            else:
                pending.append((name, uids))
        self.pending = pending

    def arm_kill_reuse(self, names, killed_uids, new_uids, tick):
        assert set(killed_uids) <= self.killed and not set(killed_uids) & set(new_uids)
        self.kill_reuse.append({"tick": tick, "killed_uids": sorted(killed_uids), "new_uids": sorted(new_uids)})
        self.arm(names, new_uids, tick)
