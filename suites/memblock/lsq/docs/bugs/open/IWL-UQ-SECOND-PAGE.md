# IWL-UQ-SECOND-PAGE — 跨页 Store 第二页在第一页写出后离开 UQ，年轻 Load 可无阻塞读到旧值

## 状态与范围

```ucv-bug
{
  "id": "IWL-UQ-SECOND-PAGE",
  "title": "跨页 Store 第二页在第一页写出后离开 UQ，年轻 Load 可无阻塞读到旧值",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/spec/verification/evidence/reports/interaction-probes-20261106.md",
        "tests/lsq_wrapper/test_interaction_windows.py",
        "docs/spec/design/contracts/interaction-semantics.md"
      ],
      "note": "2026-11-06 在 public-a0c2a26cb 的交互探针中 uq_released 相位 3/3 FAIL、uq_held 对照 3/3 PASS；上游 #6822 同根因。本次未重跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "unverified",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "该窗口首次在当前基线登记；旧基线未运行对应探针，不能写成旧基线已复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：open（历史记录显示仍存在；本次未重跑 native）。**

## 现象

跨 16B Store 的第一页写入 Sbuffer 后，UnalignQueue 立即释放第二页；第二页片段此时仍在 EnterSbufferQueue，ForwardModule 的页 hazard 只来自 UQ。年轻 Load 查询第二页时未收到任何阻塞标志，也未取得前递字节。

## 预期依据

第二页字节尚未进入 Sbuffer 前，年轻 Load 必须被阻塞或取得正确前递；不能静默接受旧内存数据。

## 复现与对照

`test_second_page_must_stay_blocked_until_the_store_leaves_the_queue` 的 `uq_held` 相位通过，`uq_released` 相位 3 lane 均 `blocked=False`、`forwarded_ok=False`，并断言 `second_fragment_still_pending=True` 证明窗口真实存在。

## 根因

`NewStoreQueue.scala:1299` 以 `writeSbufferWire.head.fire` 释放 UQ；`ForwardModule` 的页 hazard 仅取 `unalignQueue.forwardEntries`（`:1632`）。上游 #6822 的修复方向是改用 `headDeqPtr === sqIdx && io.sqDeqCnt.orR` 并给 PSQ 增加 `fwdHold`。

## 适用范围与仍未证明

只证明模块公开边界的时间窗口；完整 Backend/DCache 可见后果未证明。与旧 15 个 RTL 功能 bug 分列，不重算旧计数。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261022/README.md](../evidence/bug-reports-20261022/README.md)
- [docs/spec/verification/evidence/reports/interaction-probes-20261106.md](../../spec/verification/evidence/reports/interaction-probes-20261106.md)
- [docs/spec/design/contracts/interaction-semantics.md](../../spec/design/contracts/interaction-semantics.md)
