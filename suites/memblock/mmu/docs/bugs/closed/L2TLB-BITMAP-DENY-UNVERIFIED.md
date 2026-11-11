# L2TLB-BITMAP-DENY-UNVERIFIED — Bitmap deny 极性曾被误判

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-BITMAP-DENY-UNVERIFIED",
  "title": "Bitmap deny 极性曾被误判",
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
        "tests/l2/test_l2tlb.py::test_bitmap_deny_and_allow",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧观察是 checker 遗漏，不是 RTL 缺陷。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_l2tlb.py::test_bitmap_deny_and_allow",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧观察是 checker 遗漏，不是 RTL 缺陷。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

全 1 bitmap（cf=1）实际 deny 且 `s1_af=1`；早先“成功”是 checker 漏掉 `s1_af`。

## 结论

旧观察是 checker 遗漏，不是 RTL 缺陷。

## 历史证据

- [tests/l2/test_l2tlb.py::test_bitmap_deny_and_allow](../../../tests/l2/test_l2tlb.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
