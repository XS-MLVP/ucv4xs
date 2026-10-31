"""Observed semantic scenarios, with separate reached and successfully checked groups."""
from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "FL-RESET.initial": "复位建立完整初始槽位池",
    "FL-RESET.active": "活动/积压期间复位终止旧所有权",
    "FL-ALLOC.single": "单个分配保序且唯一",
    "FL-ALLOC.partial": "部分批次分配保序且唯一",
    "FL-ALLOC.full": "满带宽批次分配保序且唯一",
    "FL-ALLOC.sparse": "稀疏确认按数量消耗有效前缀",
    "FL-IDLE.available": "有空闲时无操作保持",
    "FL-IDLE.empty": "耗尽后无操作保持",
    "FL-CAPACITY.one_remaining": "仅剩一个可用槽位",
    "FL-CAPACITY.two_remaining": "仅剩两个可用槽位",
    "FL-CAPACITY.exhausted": "耗尽时不能承诺容量",
    "FL-CAPACITY.recovered": "回收后恢复合法分配",
    "FL-RETURN.delayed": "空池收到释放后不能立即使用",
    "FL-RETURN.reused": "已回收槽位再次被分配且唯一",
    "FL-CONGESTION.one_bank": "同回收通道积压",
    "FL-CONGESTION.multibank": "多回收通道并行通知",
    "FL-CONGESTION.continuing_notifications": "回收中仍能接收后续通知",
    "FL-OVERLAP.notify_and_allocate": "分配与释放通知同拍",
    "FL-OVERLAP.recycle_and_allocate": "分配与回收完成同拍",
    "FL-WRAP.allocate_wrap": "分配跨过槽位池边界",
    "FL-WRAP.return_wrap": "回收跨过槽位池边界",
    "FL-PREFETCH.continuous": "预分配连续消费无陈旧槽位",
    "FL-PREFETCH.after_partial": "部分批次后恢复满带宽",
    "FL-PREFETCH.refill_wait": "新回收容量等待窗口准备",
    "FL-ORDER.non_fifo_returns": "非分配顺序归还仍正确回收",
    "FL-ORDER.priority_over_notification_age": "已选批次不变，未选积压按编号而非通知年龄优先",
}


class FunctionalCoverage:
    def __init__(self, key, spec, nodeid):
        self.scenarios = {k: v for k, v in SCENARIOS.items() if spec["preallocate"] or not k.startswith("FL-PREFETCH.")}
        points = (CoverPointDef("scenario", {k: Bin.values(k) for k in self.scenarios},
                                description="; ".join(f"{k}: {v}" for k, v in self.scenarios.items())),)
        self.reached = CoverGroupDef("lsq.freelist.reached", points).instantiate(
            f"lsq.{key}.reached", run_metadata={"test": nodeid, "dut": key}, contract="freelist.actual-pins-preedge/v1")
        self.checked = CoverGroupDef("lsq.freelist.checked", points).instantiate(
            f"lsq.{key}.checked", run_metadata={"test": nodeid, "dut": key}, contract="freelist.compared-with-return-obligations/v2")

    def sample(self, facts, tick, *, checked):
        self.sample_scenarios(facts.scenarios, tick, checked=checked)

    def sample_scenarios(self, scenarios, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenarios:
            assert scene in self.scenarios
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)
