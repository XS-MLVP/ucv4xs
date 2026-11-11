# BITMAP-PMP-BACKTOBACK-LOST — Bitmap back-to-back 第二个请求看似丢失

## 状态与范围

```ucv-bug
{
  "id": "BITMAP-PMP-BACKTOBACK-LOST",
  "title": "Bitmap back-to-back 第二个请求看似丢失",
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
        "tests/l2/test_bitmap.py::test_back_to_back_requests",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧“丢失”是观察缺口，不是 RTL 行为。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_bitmap.py::test_back_to_back_requests",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧“丢失”是观察缺口，不是 RTL 行为。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

旧 monitor 在 service loop 处理另一 pending response 时没有记录 ready-high 的第二请求；全边沿监视后两个 ID 都完成，未建立 PMP alias。

## 结论

旧“丢失”是观察缺口，不是 RTL 行为。

## 历史证据

- [tests/l2/test_bitmap.py::test_back_to_back_requests](../../../tests/l2/test_bitmap.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
