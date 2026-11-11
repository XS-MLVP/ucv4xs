# L2TLB-SFENCE-RS1RS2-ZERO-NO-REWALK — sfence rs1=0/rs2=0 被误当作全局失效

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-SFENCE-RS1RS2-ZERO-NO-REWALK",
  "title": "sfence rs1=0/rs2=0 被误当作全局失效",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "当前基线未重建、未复跑；closed 仅关闭旧基线误报/归因错误或旧覆盖缺口，不代表当前基线通过。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "closed",
      "evidence": [
        "tests/l2/test_l2tlb.py::test_sfence_all_rewalks_after_pte_change",
        "tests/l2/test_l2tlb.py::test_sfence_scoped_rewalks_after_pte_change",
        "docs/spec/verification/evidence/reports/isa-confirmation-20261026.md"
      ],
      "note": "旧 finding 失效；正确 all-address 与 scoped 对照通过。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_l2tlb.py::test_sfence_all_rewalks_after_pte_change",
      "tests/l2/test_l2tlb.py::test_sfence_scoped_rewalks_after_pte_change",
      "docs/spec/verification/evidence/reports/isa-confirmation-20261026.md"
    ],
    "note": "旧 finding 失效；正确 all-address 与 scoped 对照通过。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

RTL rs1/rs2 是“寄存器是 x0”标志，不是 operand-present；both 1 才是 all VA/all ASID。旧测试驱动 both 0 且 addr=0 却期望全局 flush，属于预期错误。

## 结论

旧 finding 失效；正确 all-address 与 scoped 对照通过。

## 历史证据

- [tests/l2/test_l2tlb.py::test_sfence_all_rewalks_after_pte_change](../../../tests/l2/test_l2tlb.py)
- [tests/l2/test_l2tlb.py::test_sfence_scoped_rewalks_after_pte_change](../../../tests/l2/test_l2tlb.py)
- [docs/spec/verification/evidence/reports/isa-confirmation-20261026.md](../../spec/verification/evidence/reports/isa-confirmation-20261026.md)
