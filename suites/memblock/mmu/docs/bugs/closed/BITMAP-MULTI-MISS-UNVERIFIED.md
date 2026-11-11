# BITMAP-MULTI-MISS-UNVERIFIED — Bitmap 多 miss 被误报为只完成一次

## 状态与范围

```ucv-bug
{
  "id": "BITMAP-MULTI-MISS-UNVERIFIED",
  "title": "Bitmap 多 miss 被误报为只完成一次",
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
        "tests/l2/test_bitmap.py::test_multi_miss",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧断言错误；distinct-block miss 另行观察两次读。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_bitmap.py::test_multi_miss",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧断言错误；distinct-block miss 另行观察两次读。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

PPN 0x80000/0x80008 属于同一 bitmap fetch block，合法合并为一次内存读；旧“至少两次读”断言错误，并被宽 XFAIL 掩盖。

## 结论

旧断言错误；distinct-block miss 另行观察两次读。

## 历史证据

- [tests/l2/test_bitmap.py::test_multi_miss](../../../tests/l2/test_bitmap.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
