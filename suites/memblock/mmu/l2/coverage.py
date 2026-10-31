"""Functional coverage for L2 miss queue and prefetch leaves."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

MQ_DEFINITION = CoverGroupDef(
    "l2mq",
    (
        CoverPointDef("op", {"enqueue": Bin.values("enqueue"), "dequeue": Bin.values("dequeue"),
                              "flush": Bin.values("flush")},
                      description="入队、出队和 flush 三种队列事件。"),
        CoverPointDef("capacity", {"empty": Bin.values("empty"), "partial": Bin.values("partial"),
                                    "full": Bin.values("full")},
                      description="空、部分占用和 40 项满的容量状态。"),
        CoverPointDef("s2xlate", {str(v): Bin.values(v) for v in range(4)},
                      description="四种翻译阶段编码都能通过队列保持。"),
        CoverPointDef("source", {str(v): Bin.values(v) for v in range(4)},
                      description="四种请求来源编码都能通过队列保持。"),
        CoverPointDef("payload", {"llptw": Bin.values("llptw"), "normal": Bin.values("normal")},
                      description="LLPTW 标志与非 LLPTW 普通请求都被保存。"),
    ),
    description="L2TlbMissQueue FIFO 与 flush。",
)

PF_DEFINITION = CoverGroupDef(
    "l2pf",
    (
        CoverPointDef("event", {"issue": Bin.values("issue"), "suppressed": Bin.values("suppressed"),
                                 "consume": Bin.values("consume"), "flush": Bin.values("flush")},
                      description="产生预取、历史抑制、消费和 flush。"),
        CoverPointDef("s2xlate", {str(v): Bin.values(v) for v in range(4)},
                      description="预取请求的四种翻译阶段编码。"),
        CoverPointDef("next_line", {"normal": Bin.values("normal"), "wrap": Bin.values("wrap")},
                      description="普通下一行和 VPN 高位回绕的下一行计算。"),
    ),
    description="L2TlbPrefetch 下一行预取与历史过滤。",
)


class MQCoverage:
    def __init__(self) -> None:
        self.mq = MQ_DEFINITION.instantiate("l2mq")

    def sample_enqueue(self, entry, depth: int) -> None:
        cap = "empty" if depth == 0 else "full" if depth == 40 else "partial"
        self.mq.sample({"op": "enqueue", "capacity": cap, "s2xlate": entry.s2xlate,
                        "source": entry.source,
                        "payload": "llptw" if entry.is_llptw else "normal"}, details=False)

    def sample_dequeue(self, entry) -> None:
        self.mq.sample({"op": "dequeue", "capacity": "partial", "s2xlate": entry.s2xlate,
                        "source": entry.source,
                        "payload": "llptw" if entry.is_llptw else "normal"}, details=False)

    def sample_flush(self) -> None:
        self.mq.sample({"op": "flush", "capacity": "empty", "s2xlate": 0, "source": 0,
                        "payload": "normal"}, details=False)

class PFCoverage:
    def __init__(self) -> None:
        self.pf = PF_DEFINITION.instantiate("l2pf")

    def sample(self, valid: int, s2: int, flush: bool) -> None:
        event = "flush" if flush else "issue" if valid else "consume"
        self.pf.sample({"event": event, "s2xlate": s2, "next_line": "normal"}, details=False)

    def sample_event(self, event: str, s2: int = 0, next_line_kind: str = "normal") -> None:
        self.pf.sample({"event": event, "s2xlate": s2, "next_line": next_line_kind}, details=False)


REPEATER_DEFINITION = CoverGroupDef(
    "ptwrepeater",
    (
        CoverPointDef("event", {"accept": Bin.values("accept"), "issue": Bin.values("issue"),
                                "response": Bin.values("response"), "flush": Bin.values("flush")},
                      description="请求接收、向 PTW 发出、响应持有和 flush 取消。"),
        CoverPointDef("stage", {str(v): Bin.values(v) for v in range(4)},
                      description="透传的翻译阶段编码。"),
        CoverPointDef("hold", {"held": Bin.values("held"), "released": Bin.values("released")},
                      description="PTW 响应在输出未 ready 时保持，ready 后释放。"),
    ),
    description="PTWRepeaterNB 单条非阻塞重复/保持。",
)

FILTER_DEFINITION = CoverGroupDef(
    "ptwfilter",
    (
        CoverPointDef("event", {"enqueue": Bin.values("enqueue"), "issue": Bin.values("issue"),
                                "match_resp": Bin.values("match_resp"),
                                "mismatch_resp": Bin.values("mismatch_resp"),
                                "merge": Bin.values("merge"), "flush": Bin.values("flush"),
                                "full": Bin.values("full")},
                      description="入队、向 PTW 发出、匹配/不匹配响应、重复合并、flush 和满。"),
        CoverPointDef("stage", {str(v): Bin.values(v) for v in range(4)},
                      description="待处理请求的翻译阶段编码。"),
        CoverPointDef("getgpa", {"set": Bin.values("set"), "clear": Bin.values("clear")},
                      description="请求的 getGpa 属性在响应中透传。"),
    ),
    description="PTWFilter 8 项待处理队列与响应匹配。",
)


class RepeaterCoverage:
    def __init__(self) -> None:
        self.group = REPEATER_DEFINITION.instantiate("ptwrepeater")

    def sample(self, event: str, stage: int = 0, hold: str = "released") -> None:
        self.group.sample({"event": event, "stage": stage, "hold": hold}, details=False)


class FilterCoverage:
    def __init__(self) -> None:
        self.group = FILTER_DEFINITION.instantiate("ptwfilter")

    def sample(self, event: str, stage: int = 0, getgpa: int = 0) -> None:
        self.group.sample({"event": event, "stage": stage,
                           "getgpa": "set" if getgpa else "clear"}, details=False)


L2TLB_DEFINITION = CoverGroupDef(
    "l2tlb",
    (
        CoverPointDef("event", {"walk": Bin.values("walk"), "cache_hit": Bin.values("cache_hit"),
                                "fault": Bin.values("fault"), "sfence": Bin.values("sfence")},
                      description="经过真实 PTW/PtwCache 的走表、缓存命中、故障和失效后重走。"),
        CoverPointDef("page", {"1g": Bin.values("1g"), "2m": Bin.values("2m"),
                               "4k": Bin.values("4k"), "fault": Bin.values("fault")},
                      description="顶层响应代表的页大小或故障结果。"),
        CoverPointDef("stage", {"0": Bin.values(0), "1": Bin.values(1),
                                "2": Bin.values(2), "3": Bin.values(3)},
                      description="noS2、onlyStage1、onlyStage2、allStage 四类翻译。"),
        CoverPointDef("port", {"0": Bin.values(0), "1": Bin.values(1)},
                      description="两个 TLB 请求端口都能完成翻译路径。"),
    ),
    description="L2TLB 顶层集成语义。",
)


class L2TlbCoverage:
    def __init__(self) -> None:
        self.group = L2TLB_DEFINITION.instantiate("l2tlb")

    def sample(self, event: str, page: str = "1g", port: int = 0,
               stage: int = 0) -> None:
        self.group.sample({"event": event, "page": page, "port": port,
                           "stage": stage}, details=False)


L2TLBWRAPPER_DEFINITION = CoverGroupDef(
    "l2tlbwrapper",
    (
        CoverPointDef("event", {"walk": Bin.values("walk"),
                                "cache_hit": Bin.values("cache_hit"),
                                "fault": Bin.values("fault"),
                                "sfence": Bin.values("sfence"),
                                "perf": Bin.values("perf"),
                                "wfi": Bin.values("wfi"),
                                "backpressure": Bin.values("backpressure"),
                                "pmp": Bin.values("pmp"),
                                "bitmap": Bin.values("bitmap"),
                                "csr": Bin.values("csr"),
                                "reset": Bin.values("reset")},
                      description="组合包装层的透明翻译、故障、缓存、失效、性能计数、WFI、背压、PMP、bitmap 和 CSR 通路。"),
        CoverPointDef("page", {"1g": Bin.values("1g"), "2m": Bin.values("2m"),
                               "4k": Bin.values("4k"), "fault": Bin.values("fault")},
                      description="包装层返回的页大小或故障结果。"),
        CoverPointDef("port", {"0": Bin.values(0), "1": Bin.values(1)},
                      description="两个 TLB 端口都通过包装层完成翻译。"),
        CoverPointDef("stage", {"0": Bin.values(0), "1": Bin.values(1),
                                "2": Bin.values(2), "3": Bin.values(3)},
                      description="noS2、onlyStage1、onlyStage2、allStage 四类翻译。"),
    ),
    description="L2TLBWrapper 对内部 L2TLB 的组合包装语义。",
)


class L2TlbWrapperCoverage:
    def __init__(self) -> None:
        self.group = L2TLBWRAPPER_DEFINITION.instantiate("l2tlbwrapper")

    def sample(self, event: str, page: str = "1g", port: int = 0,
               stage: int = 0) -> None:
        self.group.sample({"event": event, "page": page, "port": port,
                           "stage": stage}, details=False)


HPTW_DEFINITION = CoverGroupDef(
    "hptw",
    (
        CoverPointDef("event", {"walk": Bin.values("walk"), "fault": Bin.values("fault"),
                                "sfence": Bin.values("sfence"), "hit": Bin.values("hit"),
                                "bitmap": Bin.values("bitmap"), "mask": Bin.values("mask")},
                      description="G-stage 走表、故障、失效、缓存命中提示、bitmap 和内存 mask。"),
        CoverPointDef("page", {"1g": Bin.values("1g"), "2m": Bin.values("2m"),
                               "4k": Bin.values("4k"), "fault": Bin.values("fault")},
                      description="G-stage 响应页大小或故障。"),
        CoverPointDef("hit", {"none": Bin.values("none"), "l1": Bin.values("l1"),
                              "l2": Bin.values("l2"), "l3": Bin.values("l3")},
                      description="请求携带的 level cache 命中提示。"),
    ),
    description="HPTW 独立 G-stage 走表语义。",
)


class HptwCoverage:
    def __init__(self) -> None:
        self.group = HPTW_DEFINITION.instantiate("hptw")

    def sample(self, event: str, page: str = "4k", hit: str = "none") -> None:
        self.group.sample({"event": event, "page": page, "hit": hit}, details=False)


PTW_DEFINITION = CoverGroupDef(
    "ptw",
    (
        CoverPointDef("event", {"walk": Bin.values("walk"), "fault": Bin.values("fault"),
                                "sfence": Bin.values("sfence"), "hit": Bin.values("hit"),
                                "bitmap": Bin.values("bitmap"), "llptw": Bin.values("llptw"),
                                "stage1": Bin.values("stage1"), "hptw": Bin.values("hptw")},
                      description="PTW 走表、故障、失效、命中提示、bitmap、LLPTW 移交、stage1 合并和 HPTW 两阶段。"),
        CoverPointDef("page", {"1g": Bin.values("1g"), "2m": Bin.values("2m"),
                               "4k": Bin.values("4k"), "fault": Bin.values("fault")},
                      description="PTW 响应页大小或故障。"),
        CoverPointDef("hint", {"none": Bin.values("none"), "l2": Bin.values("l2"),
                               "l3": Bin.values("l3"), "stage1": Bin.values("stage1")},
                      description="请求携带的 l2/l3/stage1 命中提示。"),
    ),
    description="PTW 独立走表语义。",
)


class PtwCoverage:
    def __init__(self) -> None:
        self.group = PTW_DEFINITION.instantiate("ptw")

    def sample(self, event: str, page: str = "4k", hint: str = "none") -> None:
        self.group.sample({"event": event, "page": page, "hint": hint}, details=False)


BITMAPCACHE_DEFINITION = CoverGroupDef(
    "bitmapcache",
    (
        CoverPointDef("event", {"refill": Bin.values("refill"), "hit": Bin.values("hit"),
                                "miss": Bin.values("miss"), "clear": Bin.values("clear"),
                                "flush": Bin.values("flush")},
                      description="bitmap cache 回填、命中、缺失、BCLEAR 和 flush。"),
        CoverPointDef("byte", {str(v): Bin.values(v) for v in range(8)},
                      description="命中时按 PPN 低 3 位选择数据字节。"),
        CoverPointDef("order", {str(v): Bin.values(v) for v in range(8)},
                      description="请求 order 原样返回。"),
    ),
    description="BitmapCache 64 位位图字缓存语义。",
)


class BitmapCacheCoverage:
    def __init__(self) -> None:
        self.group = BITMAPCACHE_DEFINITION.instantiate("bitmapcache")

    def sample(self, event: str, byte: int = 0, order: int = 0) -> None:
        self.group.sample({"event": event, "byte": byte, "order": order},
                          details=False)


BITMAP_DEFINITION = CoverGroupDef(
    "bitmap",
    (
        CoverPointDef("event", {"cache_hit": Bin.values("cache_hit"),
                                "cache_miss": Bin.values("cache_miss"),
                                "pmp_fail": Bin.values("pmp_fail"),
                                "refill": Bin.values("refill"),
                                "wakeup": Bin.values("wakeup"),
                                "flush": Bin.values("flush"),
                                "multi": Bin.values("multi")},
                      description="bitmap 检查的缓存命中/缺失、PMP 故障、回填、wakeup、flush 和多请求。"),
        CoverPointDef("level", {str(v): Bin.values(v) for v in range(4)},
                      description="页表级别决定 effective PPN 的 VPN 合并方式。"),
        CoverPointDef("result", {"pass": Bin.values("pass"), "fail": Bin.values("fail")},
                      description="bitmap 检查通过或失败。"),
    ),
    description="Bitmap 位图检查语义。",
)


class BitmapCoverage:
    def __init__(self) -> None:
        self.group = BITMAP_DEFINITION.instantiate("bitmap")

    def sample(self, event: str, level: int = 0, result: str = "pass") -> None:
        self.group.sample({"event": event, "level": level, "result": result},
                          details=False)


PMP_DEFINITION = CoverGroupDef(
    "pmp",
    (
        CoverPointDef("event", {"cfg_write": Bin.values("cfg_write"),
                                "addr_write": Bin.values("addr_write"),
                                "lock": Bin.values("lock"),
                                "tor_lock": Bin.values("tor_lock"),
                                "invalid_csr": Bin.values("invalid_csr"),
                                "all_entries": Bin.values("all_entries"),
                                "pma": Bin.values("pma")},
                      description="PMP/PMA 配置写入、地址写入、锁、TOR 锁、非法 CSR 和全 entry 覆盖。"),
        CoverPointDef("mode", {"off": Bin.values("off"), "tor": Bin.values("tor"),
                               "napot": Bin.values("napot")},
                      description="地址匹配模式（PlatformGrain=4KB，NA4 被粗化为 NAPOT，不可单独选择）。"),
        CoverPointDef("table", {"pmp": Bin.values("pmp"), "pma": Bin.values("pma")},
                      description="PMP 与 PMA 两套映射。"),
    ),
    description="PMP/PMA 配置寄存器与地址掩码语义。",
)


class PmpCoverage:
    def __init__(self) -> None:
        self.group = PMP_DEFINITION.instantiate("pmp")

    def sample(self, event: str, mode: str = "off", table: str = "pmp") -> None:
        self.group.sample({"event": event, "mode": mode, "table": table}, details=False)


TLBN_DEFINITION = CoverGroupDef(
    "tlbn",
    (
        CoverPointDef("event", {"hit": Bin.values("hit"), "miss": Bin.values("miss"),
                                "fault": Bin.values("fault"),
                                "fence": Bin.values("fence"),
                                "bare": Bin.values("bare"),
                                "pmp": Bin.values("pmp"),
                                "kill": Bin.values("kill")},
                      description="DTLB 命中、缺失/PTW、权限故障、失效、无翻译、PMP 和 kill。"),
        CoverPointDef("port", {str(v): Bin.values(v) for v in range(4)},
                      description="四个 DTLB 请求端口。"),
        CoverPointDef("stage", {str(v): Bin.values(v) for v in range(4)},
                      description="noS2、onlyStage1、onlyStage2、allStage 四类翻译。"),
        CoverPointDef("result", {"clean": Bin.values("clean"), "pf": Bin.values("pf"),
                                 "af": Bin.values("af"), "gpf": Bin.values("gpf"),
                                 "miss": Bin.values("miss"), "bare": Bin.values("bare")},
                      description="响应结果类别。"),
    ),
    description="TLBNonBlock 多端口 DTLB 语义。",
)


class TlbnCoverage:
    def __init__(self) -> None:
        self.group = TLBN_DEFINITION.instantiate("tlbn")

    def sample(self, event: str, port: int = 0, stage: int = 0,
               result: str = "clean") -> None:
        self.group.sample({"event": event, "port": port, "stage": stage,
                           "result": result}, details=False)


LLPTW_DEFINITION = CoverGroupDef(
    "llptw",
    (
        CoverPointDef("event", {"walk": Bin.values("walk"), "fault": Bin.values("fault"),
                                "bitmap": Bin.values("bitmap"), "cache": Bin.values("cache"),
                                "flush": Bin.values("flush"), "dup": Bin.values("dup"),
                                "stage2": Bin.values("stage2"), "capacity": Bin.values("capacity")},
                      description="LLPTW 8 项并行走表、故障、bitmap、cache 更新、flush、重复请求、两阶段和满。"),
        CoverPointDef("lane", {str(v): Bin.values(v) for v in range(8)},
                      description="8 个 4KB PTE 子页。"),
        CoverPointDef("result", {"pass": Bin.values("pass"), "fail": Bin.values("fail")},
                      description="PTE/权限检查结果。"),
    ),
    description="LLPTW 最后一级并行走表语义。",
)


class LlptwCoverage:
    def __init__(self) -> None:
        self.group = LLPTW_DEFINITION.instantiate("llptw")

    def sample(self, event: str, lane: int = 0, result: str = "pass") -> None:
        self.group.sample({"event": event, "lane": lane, "result": result}, details=False)


PTWCACHE_DEFINITION = CoverGroupDef(
    "ptwcache",
    (
        CoverPointDef("event", {"l0_fill": Bin.values("l0_fill"),
                                "l1_fill": Bin.values("l1_fill"),
                                "l2_fill": Bin.values("l2_fill"),
                                "l3_fill": Bin.values("l3_fill"),
                                "sp_fill": Bin.values("sp_fill"),
                                "l0_hit": Bin.values("l0_hit"),
                                "l1_hit": Bin.values("l1_hit"),
                                "l2_hit": Bin.values("l2_hit"),
                                "l3_hit": Bin.values("l3_hit"),
                                "miss": Bin.values("miss"),
                                "flush": Bin.values("flush"),
                                "bitmap": Bin.values("bitmap"),
                                "hptw": Bin.values("hptw"),
                                "prefetch": Bin.values("prefetch")},
                      description="PtwCache 各级 refill/命中/miss、失效、bitmap、HPTW 和预取。"),
        CoverPointDef("level", {str(v): Bin.values(v) for v in range(4)},
                      description="层号 0..3。"),
        CoverPointDef("stage", {str(v): Bin.values(v) for v in range(4)},
                      description="s2xlate 四类。"),
    ),
    description="PtwCache 页表缓存语义。",
)


class PtwCacheCoverage:
    def __init__(self) -> None:
        self.group = PTWCACHE_DEFINITION.instantiate("ptwcache")

    def sample(self, event: str, level: int = 0, stage: int = 0) -> None:
        self.group.sample({"event": event, "level": level, "stage": stage},
                          details=False)
