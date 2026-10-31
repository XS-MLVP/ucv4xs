from toffee import Bin, CoverGroupDef, CoverPointDef


SCENARIOS = {
    "DEQ-CREDIT.special_order": "年轻NC/IO完成不能越过未消费旧普通项释放SQ",
    "DEQ-RESET.initial": "reset排空后没有旧请求或credit",
    "DEQ-RESET.active": "活动写出被reset中止后新UID完成",
    "DEQ-RESET.waiting": "等待总线时reset不产生旧事务回写",
    "DEQ-CACHE.single": "单store原始字节经真实下级实际消费",
    "DEQ-CACHE.two": "双store按序消费并保持不同身份",
    "DEQ-BYTE.offset": "有效字节按真实地址偏移对齐",
    "DEQ-BYTE.sizes": "全部连续size mask正确写出",
    "DEQ-BYTE.source": "输出每个有效PA字节来自原store",
    "DEQ-SPLIT.word": "跨16B两段各自地址和字节正确",
    "DEQ-SPLIT.line": "跨cacheline两段不丢失尾部",
    "DEQ-SPLIT.page": "非连续第二页来自真实UQ输入",
    "DEQ-SPLIT.identity": "UQ比较完整SQ双flag",
    "DEQ-BACKPRESSURE.hold": "Sbuffer背压期间payload不变",
    "DEQ-BACKPRESSURE.compact": "仅消费第一项后第二项压紧不串单",
    "DEQ-BACKPRESSURE.capacity": "两项满时不提前移动读取头",
    "DEQ-BACKPRESSURE.overlap": "同拍消费和接收新项仍有序",
    "DEQ-CREDIT.real_fire": "进入流水不释放SQ而实际消费后才credit",
    "DEQ-CREDIT.split": "跨16B第一段无credit且第二段仅一次",
    "DEQ-CREDIT.zero": "CBO.zero写零不提前释放SQ",
    "DEQ-CREDIT.nc": "NC确认读取移动和最终出队分开记账",
    "DEQ-CREDIT.mmio": "MMIO真实回写后只完成一次",
    "DEQ-NC.memory": "memory NC请求与确认完成",
    "DEQ-NC.device": "device NC请求与确认完成",
    "DEQ-NC.direction": "load方向idResp不能完成store",
    "DEQ-NC.hold": "Uncache请求背压保持完整payload",
    "DEQ-MMIO.memory": "PBMT IO等待真实resp后回写",
    "DEQ-MMIO.device": "device IO等待真实resp后回写",
    "DEQ-CBO.zero": "CBO.zero真实Sbuffer写零和排空后回写",
    "DEQ-CBO.clean": "clean完整flush/cache/response/writeback流程",
    "DEQ-CBO.flush": "flush完整flush/cache/response/writeback流程",
    "DEQ-CBO.inval": "inval完整flush/cache/response/writeback流程",
    "DEQ-CBO.drain": "Sbuffer和真实内部流水均排空才发下一阶段",
    "DEQ-CBO.request_hold": "Cache请求背压保持opcode与地址",
    "DEQ-EXCEPTION.response": "Cache响应错误实际出现在回写和异常口",
    "DEQ-EXCEPTION.held": "回写背压下错误保持直到实际fire",
    "DEQ-EXCEPTION.identity": "ROB/VA/isHyper与原特殊store一致",
    "DEQ-INACTIVE.one": "单inactive不发送数据而正常移动前缀",
    "DEQ-INACTIVE.two": "双inactive按程序前缀完成",
    "DEQ-INACTIVE.mixed": "inactive与活跃项并存不越序或重复credit",
    "DEQ-DRAIN.force_write": "60置1和55保持阈值的寄存滞回",
    "DEQ-IDENTITY.flags": "SQ四圈回绕保持完整完成身份",
    "DEQ-IDENTITY.rob_slot": "ROB former/latter路由不串slot",
    "DEQ-IDLE.disabled": "无committed项和无关payload不制造请求",
    "DEQ-CONCURRENT.seeded": "固定种子合法混合流量公平排空",
    "DEQ-SPLIT.zero_neighbor": "普通split尾段仍属原store而不继承相邻CBO.zero的整line控制",
    "DEQ-CONCURRENT.controlled": "排除zero的必要条件对照仍完成cache/NC/IO/CBO/inactive混合排空，不替代完整随机",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {name: Bin.values(name) for name in SCENARIOS}, description="; ".join(f"{key}: {value}" for key, value in SCENARIOS.items()))
        metadata = {"dut": "deq_module", "test": nodeid}
        self.reached = CoverGroupDef("lsq.deq.reached", (point,)).instantiate("lsq.deq_module.reached", run_metadata=metadata, contract="public-writeout-case.observed/v1")
        self.checked = CoverGroupDef("lsq.deq.checked", (point,)).instantiate("lsq.deq_module.checked", run_metadata=metadata, contract="directed-public-response-and-completion.checked/v1")

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)
