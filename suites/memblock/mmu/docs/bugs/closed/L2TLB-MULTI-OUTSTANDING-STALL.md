# L2TLB-MULTI-OUTSTANDING-STALL — L2TLB 多 outstanding 停顿被归因为 RTL

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-MULTI-OUTSTANDING-STALL",
  "title": "L2TLB 多 outstanding 停顿被归因为 RTL",
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
        "tests/l2/test_l2tlb.py::test_four_outstanding_translations",
        "tests/l2/test_l2tlb.py::test_memory_latency_and_two_outstanding",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧 RTL 根因不成立。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_l2tlb.py::test_four_outstanding_translations",
      "tests/l2/test_l2tlb.py::test_memory_latency_and_two_outstanding",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧 RTL 根因不成立。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

全边沿 A 捕获后，4 个不同 4KB 翻译在 `mem_latency` 0/1/7 下完成；旧 double-D-beat 解释撤回，实际是 D 服务期间 A fire 未被记录。

## 结论

旧 RTL 根因不成立。

## 历史证据

- [tests/l2/test_l2tlb.py::test_four_outstanding_translations](../../../tests/l2/test_l2tlb.py)
- [tests/l2/test_l2tlb.py::test_memory_latency_and_two_outstanding](../../../tests/l2/test_l2tlb.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
