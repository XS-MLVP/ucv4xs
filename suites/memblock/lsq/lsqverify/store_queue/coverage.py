from toffee import Bin, CoverGroupDef, CoverPointDef


SCENARIOS = {
    "SQ-INTERFACE.scalar_pool": "模块容量接口域128个单flow标量uop更老分支取消，逐绝对位置新UID真实完成；非完整核IQ可达性声明",
    "SQ-RECOVER.capacity_suffix": "真实4至64Store后缀取消无副作用，保留旧字节且每个位置新UID实际消费出队",
    "SQ-RECOVER.prefix_windows": "退休前缀与真实恢复流水交错，保留旧字节、仅取消年轻后缀并同槽新UID正常消费",
    "SQ-PAGE.paired_lifetimes": "真实VSQ/PSQ/UQ高低第二页两槽占有与四组SQ身份、两段消费正常复用",
    "SQ-WINDOW.prefix_byte": "真实VSQ/PSQ非满跨环窗口按Load派发前缀选原字节，消费和正常出队保持身份",
    "SQ-STRICT.lifecycle": "真实VSQ与PSQ四代STA洞strict身份等待及精确目标对照，真实填洞后正常消费释放",
    "SQ-PAYLOAD.pool": "真实VSQ和PSQ保持64槽四代全宽及槽号图样载荷直到转发消费并释放虚拟所有权",
    "SQ-RESET.initial": "reset收敛后真实VSQ/PSQ共同为空",
    "SQ-RESET.active": "活动或响应/WB等待reset后同槽新UID完成",
    "SQ-DISPATCH.sparse": "稀疏dispatch生成紧凑物理flow区间",
    "SQ-DISPATCH.lanes": "八个dispatch入口都有实际完成见证",
    "SQ-DISPATCH.filter": "valid/needAlloc过滤不产生幽灵flow",
    "SQ-DISPATCH.zero": "零flow虚拟uop不产生物理副作用",
    "SQ-DISPATCH.multi": "多flow虚拟uop的独立字节全部写出",
    "SQ-PERMIT.none": "不在ROB头且未退休的store不能提前写",
    "SQ-PERMIT.precommit": "真实ROB头经VSQ预提交使PSQ执行",
    "SQ-PERMIT.retired": "真实ROB前进经VSQ退休许可普通写出",
    "SQ-PERMIT.exception": "执行异常阻止头写出且恢复后可安全复用",
    "SQ-RETIRE.buffered": "虚拟项已退休而物理写未消费时empty仍假",
    "SQ-CREDIT.last_flow": "多flow须最后flow释放才完成整个虚拟owner",
    "SQ-CREDIT.split": "拆分首段不能提前释放整个物理flow",
    "SQ-CREDIT.special_order": "年轻NC或IO完成不能越过未消费的旧普通写而释放其SQ所有权",
    "SQ-READY.independent": "STA/STD独立到达并由真实前缀反馈LoadQueue",
    "SQ-READY.holes": "乱序ready位不能越过未就绪前缀洞",
    "SQ-READY.retry": "TLB miss等待重试不能形成虚假地址就绪",
    "SQ-READY.upper": "只能在当前物理64项窗口发行",
    "SQ-WRITE.lanes": "两个STA/STD入口配对原地址与字节",
    "SQ-WRITE.slots": "全部物理槽和四代身份真实消费后复用",
    "SQ-WRITE.sizes": "1/2/4/8/16B及偏移的PA有效字节正确",
    "SQ-WRITE.word": "跨16B两段保持同一个flow的原数据",
    "SQ-WRITE.line": "跨cacheline尾段不扩大写范围或wline",
    "SQ-WRITE.page": "跨页第二PA来自真实UQ而不是连续猜测",
    "SQ-FORWARD.data": "实际STA/STD历史在三lane返回原始字节",
    "SQ-FORWARD.youngest": "重叠候选返回最年轻旧store而非老值",
    "SQ-FORWARD.wait": "缺地址/数据产生原owner完整SQ身份依赖",
    "SQ-FORWARD.alias": "VA别名不能把旧PA值当作安全转发",
    "SQ-FORWARD.range": "跨段mask不能指向无store来源的PA字节",
    "SQ-FORWARD.clipped": "load越过物理窗口仍保持缺数据store的原代",
    "SQ-FORWARD.deq": "出队前接受的查询与出队后新查询窗口不同",
    "SQ-FORWARD.kill": "S1 kill精确取消自己而不取消相邻请求",
    "SQ-SPECIAL.nc": "真实VSQ许可NC请求且方向确认后完成",
    "SQ-SPECIAL.io": "真实IO响应/WB身份无串单并最终完成",
    "SQ-SPECIAL.cbo": "四类CBO在真实ROB头域执行并完成",
    "SQ-SPECIAL.error_response": "Cache错误无等待时经真实WB/异常消费",
    "SQ-SPECIAL.error_held": "Cache错误在WB背压后仍保持到实际fire",
    "SQ-SPECIAL.zero_owner": "旧普通请求消费不能冒充当前zero自己的零写",
    "SQ-SPECIAL.split_wline": "真实VSQ许可下split尾段不继承邻居zero控制",
    "SQ-RECOVER.suffix": "合法redirect只取消年轻后缀保留幸存前缀",
    "SQ-RECOVER.inflight": "前拍dispatch/在途执行恢复不留下ghost或旧污染",
    "SQ-RECOVER.release_walk": "退休前缀先release再walk后恢复正确exclusive end",
    "SQ-RECOVER.empty": "全部取消恢复到真实已退休end",
    "SQ-RECOVER.wrap": "跨完整flags的恢复和新代复用正确",
    "SQ-RECOVER.page": "取消真实UQ占有后同槽新页实际消费",
    "SQ-CAPACITY.virtual": "128flow占用与64物理发行分离并公平排空",
    "SQ-CAPACITY.force": "真实VSQ物理tail驱动forceWrite阈值滞回",
    "SQ-REUSE.cancelled": "取消后同槽新UID实际完成无旧异常/属性",
    "SQ-CONCURRENT.seeded": "合法完整域并发随机所有UID公平排空",
    "SQ-CONCURRENT.controlled": "必要条件对照单列范围不替代完整域随机",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS}, description="; ".join(f"{key}: {text}" for key, text in SCENARIOS.items()))
        metadata = {"dut": "store_queue", "test": nodeid}
        self.reached = CoverGroupDef("lsq.sq.reached", (point,)).instantiate("lsq.store_queue.reached", run_metadata=metadata, contract="real-vsq-psq.observed/v1")
        self.checked = CoverGroupDef("lsq.sq.checked", (point,)).instantiate("lsq.store_queue.checked", run_metadata=metadata, contract="real-vsq-psq.checked/v1")

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)
