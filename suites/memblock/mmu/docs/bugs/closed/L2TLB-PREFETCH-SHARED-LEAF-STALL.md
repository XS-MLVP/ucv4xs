# L2TLB-PREFETCH-SHARED-LEAF-STALL — 共享叶表零间隔 prefecth 抢占 demand 的根因结论

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-PREFETCH-SHARED-LEAF-STALL",
  "title": "共享叶表零间隔 prefecth 抢占 demand 的根因结论",
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
        "tests/l2/test_l2tlbwrapper.py::test_wrapper_back_to_back_shared_leaf_miss",
        "tests/l2/test_l2tlbwrapper.py::test_wrapper_shared_leaf_one_cycle_gap",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧 RTL 调度归因不成立。"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "tests/l2/test_l2tlbwrapper.py::test_wrapper_back_to_back_shared_leaf_miss",
      "tests/l2/test_l2tlbwrapper.py::test_wrapper_shared_leaf_one_cycle_gap",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "旧 RTL 调度归因不成立。 closed 仅关闭旧基线问题；当前基线未复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（closed 仅关闭旧基线误报/归因错误；当前基线未复验，不代表通过）。**

## 观察与处置

旧 memory service 在发送 D beats 时跳过 A 监视；修正全边沿 A 捕获后零间隔 shared-leaf 请求全部完成，prefetch/LLPTW 根因撤回。

## 结论

旧 RTL 调度归因不成立。

## 历史证据

- [tests/l2/test_l2tlbwrapper.py::test_wrapper_back_to_back_shared_leaf_miss](../../../tests/l2/test_l2tlbwrapper.py)
- [tests/l2/test_l2tlbwrapper.py::test_wrapper_shared_leaf_one_cycle_gap](../../../tests/l2/test_l2tlbwrapper.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
