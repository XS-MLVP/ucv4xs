from toffee import Bin, CoverGroupDef, CoverPointDef


SCENARIOS = {
    "PSQ-PAGE.paired_lifetimes": "两真实跨页Store按完整SQ接受高低第二页，两段原字节实际消费后完成",
    "PSQ-WINDOW.prefix_byte": "真实STA/STD已写年轻同址字节时Load只见独占SQ前缀，正常消费后跨窗口复用",
    "PSQ-STRICT.lifecycle": "真实STA洞使strict等待完整SQ身份而精确已就绪目标可通过，填洞后四代正常消费完成",
    "PSQ-PAYLOAD.pool": "真实64槽四代全宽及槽号图样写入三路转发和Sbuffer消费后正常同槽复用",
    "PSQ-DEQ.special_order": "真实PSQ年轻NC/IO完成不能释放未消费的旧普通owner",
    "PSQ-RESET.initial": "reset收敛后无旧请求或出队",
    "PSQ-RESET.active": "活动状态reset中止后新UID同槽完成",
    "PSQ-WRITE.addr_first": "STA先于STD仍保留原身份与字节",
    "PSQ-WRITE.data_first": "STD先于STA仍保留原身份与字节",
    "PSQ-WRITE.together": "STA/STD同拍写入在真实写出正确配对",
    "PSQ-WRITE.lanes": "两条输入lane都经真实下级实际完成",
    "PSQ-WRITE.slots": "全部64物理槽及四圈身份可重用",
    "PSQ-STAGE.s2": "S1后S2属性只更新对应事务",
    "PSQ-STAGE.retry": "TLB miss不完成地址而重试后完成",
    "PSQ-STAGE.split": "分拆首末请求保持原起始地址与mask",
    "PSQ-READY.address": "地址就绪指针只越过连续前缀",
    "PSQ-READY.data": "数据就绪指针独立推进",
    "PSQ-READY.holes": "乱序写入仅置位图不跳过洞",
    "PSQ-READY.upper": "物理窗口上界阻止越代发行",
    "PSQ-PERMIT.precommit": "真实VSQ预提交许可使head写出",
    "PSQ-PERMIT.retired": "已退休区间允许普通连续写出",
    "PSQ-PERMIT.none": "无许可时不提前写出或释放",
    "PSQ-PERMIT.exception": "已有异常的store不能普通提交",
    "PSQ-BYTE.sizes": "全部size与偏移的PA字节来源正确",
    "PSQ-BYTE.word": "跨16B两段仅完成一个owner",
    "PSQ-BYTE.line": "跨line尾段不丢失或扩大写范围",
    "PSQ-BYTE.page": "非连续第二页经真实UQ写出",
    "PSQ-FORWARD.data": "真实STA/STD历史产生原store转发数据",
    "PSQ-FORWARD.youngest": "多个候选选择最年轻旧store",
    "PSQ-FORWARD.wait": "地址数据未就绪产生正确完整依赖",
    "PSQ-FORWARD.alias": "VA别名不能安全返回旧PA字节",
    "PSQ-FORWARD.range": "跨段mask不折回未写PA字节",
    "PSQ-FORWARD.deq_window": "出队前后转发可见窗口正确",
    "PSQ-DEQ.credit": "真实Sbuffer消费后才完成一次SQ释放",
    "PSQ-DEQ.backpressure": "内部队列满和部分消费不串单",
    "PSQ-SPECIAL.nc": "NC请求确认后真实handleFinish并释放",
    "PSQ-SPECIAL.io": "IO等真实响应与WB再完成",
    "PSQ-SPECIAL.cbo": "四类CBO真实控制/数据与下级完成",
    "PSQ-SPECIAL.wb_error": "Cache错误保持到父级实际WB消费",
    "PSQ-SPECIAL.wb_response": "无等待时Cache错误及身份经父级实际WB消费",
    "PSQ-SPECIAL.split_wline": "split尾段不继承相邻zero整line控制",
    "PSQ-RECOVER.suffix": "redirect只取消年轻后缀保留已提交前缀",
    "PSQ-RECOVER.inflight": "恢复与S1/S2/STD/UQ在途不污染新代",
    "PSQ-CAPACITY.virtual": "虚拟128占用与物理64驻留分开",
    "PSQ-CAPACITY.force": "真实enq-deq计数驱动forceWrite滞回",
    "PSQ-REUSE.completed": "正常完成后同槽新UID实际完成",
    "PSQ-REUSE.cancelled": "取消后同槽新UID无旧属性或数据",
    "PSQ-CONCURRENT.seeded": "固定种子合法并发与公平排空",
    "PSQ-SPECIAL.zero_owner": "CBO.zero必须真正写出自己的零line，不能由旧普通store的消费代替",
    "PSQ-CONCURRENT.controlled": "无zero且load在物理窗口内的必要条件随机对照，不替代完整域",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS}, description="; ".join(f"{key}: {text}" for key, text in SCENARIOS.items()))
        metadata = {"dut": "physical_store_queue", "test": nodeid}
        self.reached = CoverGroupDef("lsq.psq.reached", (point,)).instantiate("lsq.physical_store_queue.reached", run_metadata=metadata, contract="real-parent-public.observed/v1")
        self.checked = CoverGroupDef("lsq.psq.checked", (point,)).instantiate("lsq.physical_store_queue.checked", run_metadata=metadata, contract="real-parent-public.checked/v1")

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)
