# LLPTW-MULTI-STAGE2-UNVERIFIED — 两个 allStage 并发时只完成一个

## 状态与范围

```ucv-bug
{
  "id": "LLPTW-MULTI-STAGE2-UNVERIFIED",
  "title": "两个 allStage 并发时只完成一个",
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
        "tests/l2/test_llptw.py::test_two_concurrent_all_stage",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧 RTL 调度结论是 harness 观察缺口。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_llptw.py::test_two_concurrent_all_stage",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧 RTL 调度结论是 harness 观察缺口。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

旧 priority/continue responder 驱动响应时忽略其他 ready-high 通道；每条边沿独立记录 valid&&ready 后，两个 allStage 在 latency 0/1/3 均完成，旧 RTL 调度归因撤回。

## 结论

旧 RTL 调度结论是 harness 观察缺口。

## 历史证据

- [tests/l2/test_llptw.py::test_two_concurrent_all_stage](../../../tests/l2/test_llptw.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
