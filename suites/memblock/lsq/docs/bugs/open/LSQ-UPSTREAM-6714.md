# LSQ-UPSTREAM-6714 — 已退休的 MDP 等待目标仍被误判越域，Load 保持地址依赖

## 状态与范围

```ucv-bug
{
  "id": "LSQ-UPSTREAM-6714",
  "title": "已退休的 MDP 等待目标仍被误判越域，Load 保持地址依赖",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md",
        "tests/forward/test_github_gap_relationship.py",
        "docs/spec/verification/evidence/reports/same-source-audit-20261022.md"
      ],
      "note": "2026-11-02/03 新基线关系核验记录 3 个 lane 的已退休 MDP 目标仍保持 addrInvalid；本次未重跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "旧基线/关系核验阶段 3 个 lane 失败；保留为历史复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：open（历史记录显示仍存在；本次未重跑 native）。**

## 现象

Load 记着的等待目标已经退休，但在 flag/value 上同时表现为物理窗口之外时，`addrInvalid.valid` 仍为 1，Load 等待一个永远不会再来的 STA。

## 预期依据

已退休目标必须排除越域等待；`addrInvalid.valid` 应为 0。

## 复现与对照

`test_retired_mdp_target_must_not_be_out_of_range` 使用 `deq=131`、`upper=195`、等待目标 66，3 lane 均实际 `addrInvalid_valid=1`、期望 0；普通 retired 对照通过。

## 根因

`NewStoreQueue.scala:579-584` 计算了 `s2MdpTargetRetired`，却未用它排除 `s2MdpHitOutOfRange`。

## 适用范围与仍未证明

本地已复现公开引脚；完整生命周期/Backend 停滞后果未证明。上游 PR #6714。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261022/14-relationship-11-vs-5.md](../evidence/bug-reports-20261022/14-relationship-11-vs-5.md)
- [docs/spec/verification/evidence/reports/upstream-audit-20261103.md](../../spec/verification/evidence/reports/upstream-audit-20261103.md)
- <https://github.com/OpenXiangShan/XiangShan/pull/6714>
