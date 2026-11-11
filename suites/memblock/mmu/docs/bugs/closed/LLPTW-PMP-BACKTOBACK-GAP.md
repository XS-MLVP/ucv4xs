# LLPTW-PMP-BACKTOBACK-GAP — LLPTW 连续请求被要求插入 >=3 idle cycle

## 状态与范围

```ucv-bug
{
  "id": "LLPTW-PMP-BACKTOBACK-GAP",
  "title": "LLPTW 连续请求被要求插入 >=3 idle cycle",
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
        "tests/l2/test_llptw.py",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧要求与根因均被反证。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_llptw.py",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧要求与根因均被反证。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

响应者捕获修正后，连续正常输入无需插入 service gap 即可完成；旧 spacing 要求和 PMP alias 归因撤回。

## 结论

旧要求与根因均被反证。

## 历史证据

- [tests/l2/test_llptw.py](../../../tests/l2/test_llptw.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
