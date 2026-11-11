# TLBFA-LEVEL3-FAKE-PTE-UNREACHABLE — s1 fake PTE + s2 exception 永远选择 s1_level，文档所述 level 3 分支不可达

## 状态与范围

```ucv-bug
{
  "id": "TLBFA-LEVEL3-FAKE-PTE-UNREACHABLE",
  "title": "s1 fake PTE + s2 exception 永远选择 s1_level，文档所述 level 3 分支不可达",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "当前基线未重建、未复跑 native；旧基线结论不得写成当前已复现。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md",
        "manifest/known-issues.json"
      ],
      "note": "固定 RTL 观察；需设计确认。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未复验）。**

## 现象

`TLBFA.sv:7151` 的嵌套三元中，`s2_exception && !s1_leaf` 在 s2_exception 为真时已经成立，后面 `s2_exception && s1_fake ? 3` 分支永远选不到；测试观察到 level 0。

## 预期依据

按 `MMUBundle.scala` 注释，s1 fake PTE 加 s2 exception 应强制 level 3；生成行为与之不同。

## 复现与对照

`test_all_stage_fake_pte_with_stage2_exception_uses_s1_level` 观察 level 0；fake-PTE 结构分支覆盖恒 0。

## 根因

生成 `TLBFA.sv:7151` 的条件顺序使 level 3 分支成为死分支。

## 适用范围与仍未证明

只证明结构分支不可达；下游架构 fault/GPA 后果未验证，需设计 owner 判定。

## 历史证据

- [docs/spec/verification/evidence/reports/tlb-20261024.md](../../spec/verification/evidence/reports/tlb-20261024.md)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json)
