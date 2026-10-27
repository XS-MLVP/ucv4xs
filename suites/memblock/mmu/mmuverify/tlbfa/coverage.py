"""Semantic functional coverage for the TLBFA storage leaf.

Bins describe microarchitectural events (hit under a page size, a rejected
context, a refill form, a fence form) rather than raw signal values. Sampling
happens only after the checker has accepted the corresponding response.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

NA = -1

LOOKUP_DEFINITION = CoverGroupDef(
    "tlbfa_lookup",
    (
        CoverPointDef(
            "translation_context",
            {
                "bare_no_s2": Bin.values("bare_no_s2"),
                "stage1_only": Bin.values("stage1_only"),
                "stage2_only": Bin.values("stage2_only"),
                "two_stage": Bin.values("two_stage"),
            },
            description="查找发生在无第二阶段、仅 VS 阶段、仅 G 阶段或两阶段合并的翻译上下文中。",
        ),
        CoverPointDef(
            "outcome",
            {
                "hit": Bin.values("hit"),
                "miss": Bin.values("miss"),
            },
            description="VPN 与上下文是否在存储中命中。",
        ),
        CoverPointDef(
            "hit_page_level",
            {
                "4k": Bin.values("4k"),
                "2m": Bin.values("2m"),
                "1g": Bin.values("1g"),
                "512g": Bin.values("512g"),
                "napot64k": Bin.values("napot64k"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="命中的条目代表 4KB、2MB、1GB、512GB 或 NAPOT 64KB 页。",
        ),
        CoverPointDef(
            "reject_reason",
            {
                "no_candidate": Bin.values("no_candidate"),
                "invalid_way": Bin.values("invalid_way"),
                "s2xlate": Bin.values("s2xlate"),
                "asid": Bin.values("asid"),
                "vmid": Bin.values("vmid"),
                "tag": Bin.values("tag"),
                "valididx": Bin.values("valididx"),
                "pteidx": Bin.values("pteidx"),
                "refill_same_cycle": Bin.values("refill_same_cycle"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="未命中时被拒绝的原因：无候选、way 无效、翻译阶段、ASID、VMID、标签、子页有效位、PTE 索引，或同拍回填屏蔽。",
        ),
        CoverPointDef(
            "hit_qualifier",
            {
                "global": Bin.values("global"),
                "asid_match": Bin.values("asid_match"),
                "stage2_asid_ignored": Bin.values("stage2_asid_ignored"),
                "pteidx_armed": Bin.values("pteidx_armed"),
                "single_sector": Bin.values("single_sector"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="命中路径依赖的语义条件：全局位、ASID 匹配、onlyStage2 忽略 ASID、PTE 索引门控或单子页有效位。",
        ),
    ),
    (
        CrossDef(
            "context_x_outcome",
            ("translation_context", "outcome"),
            description="每个翻译上下文都同时观察到命中与未命中，避免只测到单一结果。",
        ),
    ),
    description="TLBFA 查找：上下文、页大小、命中/拒绝原因与语义限定条件。",
)

REFILL_DEFINITION = CoverGroupDef(
    "tlbfa_refill",
    (
        CoverPointDef(
            "refill_kind",
            {
                "bare_no_s2": Bin.values("bare_no_s2"),
                "stage1_only": Bin.values("stage1_only"),
                "stage2_only": Bin.values("stage2_only"),
                "two_stage": Bin.values("two_stage"),
            },
            description="PTW 回填的翻译阶段形态。",
        ),
        CoverPointDef(
            "refill_page",
            {
                "4k": Bin.values("4k"),
                "2m": Bin.values("2m"),
                "1g": Bin.values("1g"),
                "512g": Bin.values("512g"),
                "napot64k": Bin.values("napot64k"),
            },
            description="回填条目的页大小或 NAPOT 形态。",
        ),
        CoverPointDef(
            "way_slot",
            {str(way): Bin.values(way) for way in range(48)},
            description="48 个 way 都能独立接收回填；替换策略不在本叶子内。",
        ),
        CoverPointDef(
            "refill_timing",
            {
                "normal": Bin.values("normal"),
                "same_cycle_lookup": Bin.values("same_cycle_lookup"),
                "same_cycle_sfence": Bin.values("same_cycle_sfence"),
            },
            description="回填与查找/失效的时序关系：普通回填、同拍查找被屏蔽、同拍失效优先。",
        ),
    ),
    (
        CrossDef(
            "kind_x_page",
            ("refill_kind", "refill_page"),
            description="每种翻译阶段形态都检查其页大小/NAPOT 回填组合。",
        ),
    ),
    description="TLBFA 回填：阶段形态、页大小、way 覆盖与时序。",
)

PPN_DEFINITION = CoverGroupDef(
    "tlbfa_ppn",
    (
        CoverPointDef(
            "ppn_page",
            {
                "4k": Bin.values("4k"),
                "2m": Bin.values("2m"),
                "1g": Bin.values("1g"),
                "512g": Bin.values("512g"),
                "napot64k": Bin.values("napot64k"),
            },
            description="PPN 合成使用的页大小路径。",
        ),
        CoverPointDef(
            "ppn_low_slot",
            {
                **{str(index): Bin.values(index) for index in range(8)},
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="4KB 非 NAPOT 条目由 vpn[2:0] 选择 8 个 ppn_low 槽之一。",
        ),
    ),
    description="TLBFA PPN：4KB 低槽选择、大页偏移替换与 NAPOT。",
)

PAYLOAD_DEFINITION = CoverGroupDef(
    "tlbfa_payload",
    (
        CoverPointDef(
            "payload_kind",
            {
                "stage1_perm": Bin.values("stage1_perm"),
                "stage2_perm": Bin.values("stage2_perm"),
                "fault_flags": Bin.values("fault_flags"),
                "pbmt": Bin.values("pbmt"),
                "miss_zero": Bin.values("miss_zero"),
            },
            description="命中返回 s1 权限、s2 权限/故障、PBMT；未命中 payload 不作为有效结果。",
        ),
    ),
    description="TLBFA 返回载荷语义。",
)

SFENCE_DEFINITION = CoverGroupDef(
    "tlbfa_sfence",
    (
        CoverPointDef(
            "fence_kind",
            {
                "all_all": Bin.values("all_all"),
                "all_asid": Bin.values("all_asid"),
                "addr_all_asid": Bin.values("addr_all_asid"),
                "addr_asid": Bin.values("addr_asid"),
                "hfencev_all": Bin.values("hfencev_all"),
                "hfencev_asid": Bin.values("hfencev_asid"),
                "hfenceg_all": Bin.values("hfenceg_all"),
                "hfenceg_vmid": Bin.values("hfenceg_vmid"),
                "virt_all": Bin.values("virt_all"),
                "bme_all": Bin.values("bme_all"),
            },
            description="RISC-V sfence/hfence 形式以及虚拟化/MPT 触发的全地址路径。",
        ),
        CoverPointDef(
            "fence_effect",
            {
                "stage1_cleared": Bin.values("stage1_cleared"),
                "stage1_survived": Bin.values("stage1_survived"),
                "stage2_cleared": Bin.values("stage2_cleared"),
                "stage2_survived": Bin.values("stage2_survived"),
                "global_cleared": Bin.values("global_cleared"),
                "global_survived": Bin.values("global_survived"),
                "other_asid_survived": Bin.values("other_asid_survived"),
                "other_asid_cleared": Bin.values("other_asid_cleared"),
                "other_vmid_survived": Bin.values("other_vmid_survived"),
            },
            description="失效的语义效果：目标阶段被清除或保留，全局/其他 ASID/其他 VMID 按规则存活。",
        ),
        CoverPointDef(
            "fence_timing",
            {
                "after_cycle": Bin.values("after_cycle"),
                "same_cycle_with_refill": Bin.values("same_cycle_with_refill"),
            },
            description="失效在边沿后生效；同拍回填不能绕过失效。",
        ),
    ),
    description="TLBFA sfence/hfence：地址/ASID/VMID 选择、阶段边界与时序。",
)

TIMING_DEFINITION = CoverGroupDef(
    "tlbfa_timing",
    (
        CoverPointDef(
            "response_timing",
            {
                "one_cycle_latency": Bin.values("one_cycle_latency"),
                "valid_drop": Bin.values("valid_drop"),
                "idle_hold": Bin.values("idle_hold"),
            },
            description="请求到响应一拍、撤销 valid 后响应撤销、无请求时条目不自发变化。",
        ),
    ),
    description="TLBFA 响应时序。",
)

TOUCH_DEFINITION = CoverGroupDef(
    "tlbfa_touch",
    (
        CoverPointDef(
            "touch_kind",
            {
                "hit_touch": Bin.values("hit_touch"),
                "refill_touch": Bin.values("refill_touch"),
            },
            description="命中 touch 与回填 touch 都向替换逻辑报告正确 way。",
        ),
    ),
    description="TLBFA touch way 报告。",
)

RESET_DEFINITION = CoverGroupDef(
    "tlbfa_reset",
    (
        CoverPointDef(
            "reset_context",
            {
                "empty": Bin.values("empty"),
                "with_valid_entries": Bin.values("with_valid_entries"),
            },
            description="复位清空空存储，或清除已有有效条目使旧翻译不可见。",
        ),
    ),
    description="TLBFA 复位语义。",
)


class TlbfaCoverage:
    def __init__(self) -> None:
        self.lookup = LOOKUP_DEFINITION.instantiate("tlbfa.lookup")
        self.refill = REFILL_DEFINITION.instantiate("tlbfa.refill")
        self.ppn = PPN_DEFINITION.instantiate("tlbfa.ppn")
        self.payload = PAYLOAD_DEFINITION.instantiate("tlbfa.payload")
        self.sfence = SFENCE_DEFINITION.instantiate("tlbfa.sfence")
        self.timing = TIMING_DEFINITION.instantiate("tlbfa.timing")
        self.touch = TOUCH_DEFINITION.instantiate("tlbfa.touch")
        self.reset = RESET_DEFINITION.instantiate("tlbfa.reset")

    def sample_lookup(
        self,
        context: str,
        hit: bool,
        page: str | None,
        reasons: list[str],
        qualifiers: list[str],
    ) -> None:
        if hit:
            self.lookup.sample(
                {
                    "translation_context": context,
                    "outcome": "hit",
                    "hit_page_level": page or NA,
                    "reject_reason": NA,
                    "hit_qualifier": qualifiers[0] if qualifiers else NA,
                },
                details=False,
            )
            for qualifier in qualifiers[1:]:
                self.lookup.sample(
                    {
                        "translation_context": context,
                        "outcome": "hit",
                        "hit_page_level": page or NA,
                        "reject_reason": NA,
                        "hit_qualifier": qualifier,
                    },
                    details=False,
                )
        else:
            self.lookup.sample(
                {
                    "translation_context": context,
                    "outcome": "miss",
                    "hit_page_level": NA,
                    "reject_reason": reasons[0] if reasons else "no_candidate",
                    "hit_qualifier": NA,
                },
                details=False,
            )
            for reason in reasons[1:]:
                self.lookup.sample(
                    {
                        "translation_context": context,
                        "outcome": "miss",
                        "hit_page_level": NA,
                        "reject_reason": reason,
                        "hit_qualifier": NA,
                    },
                    details=False,
                )

    def sample_refill(self, kind: str, page: str, way: int, timing: str = "normal") -> None:
        self.refill.sample(
            {"refill_kind": kind, "refill_page": page, "way_slot": way, "refill_timing": timing},
            details=False,
        )

    def sample_ppn(self, page: str, low_slot: int | None) -> None:
        self.ppn.sample(
            {"ppn_page": page, "ppn_low_slot": low_slot if low_slot is not None else NA},
            details=False,
        )

    def sample_payload(self, kinds: list[str]) -> None:
        for kind in kinds:
            self.payload.sample({"payload_kind": kind}, details=False)

    def sample_sfence(self, kind: str, effects: list[str], timing: str = "after_cycle") -> None:
        for effect in effects:
            self.sfence.sample(
                {"fence_kind": kind, "fence_effect": effect, "fence_timing": timing},
                details=False,
            )

    def sample_timing(self, value: str) -> None:
        self.timing.sample({"response_timing": value}, details=False)

    def sample_touch(self, value: str) -> None:
        self.touch.sample({"touch_kind": value}, details=False)

    def sample_reset(self, context: str) -> None:
        self.reset.sample({"reset_context": context}, details=False)
