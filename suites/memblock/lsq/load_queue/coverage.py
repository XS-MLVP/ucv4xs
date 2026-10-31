from toffee import Bin, CoverGroupDef, CoverPointDef

SCENARIOS = {
    "LQ-UNCACHE.payload_pool": "16真实mid响应全位和独立错误经原slot、源正确S3及实际LQ前缀释放完成",
    "LQ-RESET.initial": "复位后五个真实队列共同空闲且新事务可完成",
    "LQ-RESET.active": "活动reset中止旧owner后同槽新UID完成",
    "LQ-RESET.waiting": "已发Uncache或Replay等待reset后安全复用",
    **{"LQ-ALLOC." + k: v for k, v in dict(sparse="稀疏dispatch分配连续区间", multi_flow="单uop多个flow均实际完成", all_lanes="全部八入口有完成见证", wrap="120项非2幂回绕身份正确", capacity="满120项不覆盖并排空").items()},
    **{"LQ-COMPLETE." + k: v for k, v in dict(prefix="只报告连续完成前缀", out_of_order="年轻完成等待旧头", replay_blocks="需要replay不能完成VLQ", address_blocks="无地址更新不能完成VLQ").items()},
    **{"LQ-HEAD." + k: v for k, v in dict(rar_release="真实VLQ头前进回收RAR", replay_priority="真实头改变Replay选择优先级", rollover="内部head跨圈不串身份").items()},
    **{"LQ-RAR." + k: v for k, v in dict(release="release命中后查询年轻记录冲突", previous_release="分配前一拍release合同", nc="NC记录预标记冲突", revoke="一两拍撤销无ghost", all_slots="真实96槽分别保存与查询").items()},
    **{"LQ-RAW." + k: v for k, v in dict(collision="store冲突恢复原load身份", negative="字节地址年龄不匹配不恢复", dual_store="双store独立恢复", train="最老冲突产生MDP训练", revoke="撤销load不产生旧恢复", all_slots="真实56槽与所有入口组合").items()},
    **{"LQ-CAPACITY." + k: v for k, v in dict(rar_block="真实RAR满使Replay阻塞", rar_wake="VLQ回收RAR后真实唤醒", raw_block="真实RAW满使Replay阻塞", raw_wake="SQ地址前进回收后唤醒", replay_pool="120真实Replay所有者安全复用").items()},
    **{"LQ-REPLAY." + k: v for k, v in dict(causes="真实原因0..11逐个反馈完成", feedback="replay握手后S3反馈才完成", update="同owner更新再执行后释放", backpressure="三路输出背压保持", metadata="完整原load元信息不串单", banks="真实三个bank分别执行完成").items()},
    **{"LQ-STORE." + k: v for k, v in dict(address="真实SQ地址指针位图及STA唤醒", data="真实STD与数据位图唤醒", strict="strict不被仅ready位清除", disabled="禁用反馈不能解除strict").items()},
    **{"LQ-HINT." + k: v for k, v in dict(refill="两channel正确MSHR回填", l2="L2首尾beat窗口", tlb="慢TLB匹配和全唤醒", fast_tlb="快TLB精确身份").items()},
    **{"LQ-UNCACHE." + k: v for k, v in dict(nc="NC完整bus与反馈完成", mmio="ROB头MMIO完整完成", wake="真实内部Uncache wake唤醒Replay", bypass="三路bypass的s1地址和s2原始数据", errors="原始错误保留至消费", all_entries="全部16真实entry完成", sid_reuse="已返SID新回包不覆盖旧数据", full="真实满Uncache池恢复与拒绝").items()},
    **{"LQ-RECOVER." + k: v for k, v in dict(partial="共享redirect取消年轻后缀", all="全部取消排空五队列", concurrent="在途查询和反馈恢复无ghost", reuse="同槽取消后新UID完成", sent_uncache="已发总线取消须安全接收回包").items()},
    "LQ-SPECIAL.threshold": "ROB头eligible达到2048边界进入特殊模式",
    "LQ-REPLAY.checkpoint_pool": "真实父级两生命周期全部120个公开Replay槽保持高低checkpoint并反馈后有序释放",
    "LQ-SPECIAL.head_change": "下一ROB头改变撤销旧特殊模式",
    "LQ-CONCURRENT.directed": "多个真实子队列同拍活动不串共享输入",
    "LQ-CONCURRENT.seeded": "合法固定种子并发完整UID排空",
    "LQ-CONCURRENT.fair_drain": "公平代理排空所有owner与总线义务",
}


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {key: Bin.values(key) for key in SCENARIOS}, description="; ".join(f"{k}: {v}" for k, v in SCENARIOS.items()))
        metadata = dict(dut="load_queue", test=nodeid)
        self.reached = CoverGroupDef("lsq.lq.reached", (point,)).instantiate("lsq.load_queue.reached", run_metadata=metadata, contract="five-real-children.observed/v1")
        self.checked = CoverGroupDef("lsq.lq.checked", (point,)).instantiate("lsq.load_queue.checked", run_metadata=metadata, contract="five-real-children.checked/v1")

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            (self.checked if checked else self.reached).sample({"scenario": name}, metadata={"tick": tick}, details=False)
