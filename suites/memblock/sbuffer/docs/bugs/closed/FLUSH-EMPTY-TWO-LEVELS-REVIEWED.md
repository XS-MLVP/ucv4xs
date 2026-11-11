# FLUSH-EMPTY-TWO-LEVELS-REVIEWED：CMO 期间 flush.empty 受 sqempty 门控不是缺陷

状态：**已关闭（仅历史误报分类），非缺陷**。该 `closed/invalid` 只关闭历史基线的误报，
当前默认基线 `public-a0c2a26cb` 另未复验（JSON 记 `unverified`）。
Sbuffer 对外提供两个“空”信号，语义不同；CMO 消费 `sbempty`，
fence/atomics 消费 `flush.empty`。`flush.empty` 含 `sqempty` 是正确设计。

## 原问题

CMO 期间 `flush.empty` 受 `sqempty` 门控，曾怀疑会导致 CMO 无法完成。实际 CMO 消费的是
`sbempty`，不是 `flush.empty`。

## 独立预期与依据

| 信号 | 语义 | 消费者 | 是否含 SQ |
|---|---|---|---|
| `sbempty` | Sbuffer 行全空 && 在途输入为空 && MSHR 无 store miss | LSQ → `SbufferCtrlIO.Resp.empty` → CBO FSM | 否 |
| `flush.empty` | `sbempty && sqempty` | `MemBlock.stIsEmpty` → Fence 的 `sbIsEmpty`；AtomicsUnit | 是 |

- CMO flush（`isCmo=1`）完成条件是 `sbempty`。CMO 必须在 SQ 头部执行，其自身 SQ 条目
  在 writeback 前不释放，所以处理期间 `sqempty` 必为 0；要求 `sqempty` 会死锁。
- 普通 flush（fence/atomics，`isCmo=0`）完成条件是 `flush.empty`，必须等整条 store
  路径（Sbuffer + 输入 + MSHR + SQ）都空。
- uarch drain 只排空 Sbuffer 自身，不要求 MSHR/SQ。

依据：RISC-V CMO 规范 19.1.4.1、XiangShan PR #6183、`MemBlock.scala` 的接线、
`Fence.scala`/`AtomicsUnit.scala` 的消费者，以及 `NewStoreQueue.scala` 的 CMO 出队
顺序。完整论证见 [合同复核](../../spec/verification/evidence/flush-contract-review-20261024.md)。

## 复现与对照

- 普通 flush 排空后 `sbempty=1` 但 `flush.empty=0`，直到 `sqempty=1`。
- CMO 排空后 MSHR 非空时 `sbempty=0`；MSHR 空后即使 `sqempty=0`，`sbempty=1` 而
  `flush.empty=0`；`sqempty=1` 后 `flush.empty=1`。
- 对应用例：[test_fence_flush_empty_requires_sqempty](../../../tests/sbuffer/test_sbuffer.py)::test_fence_flush_empty_requires_sqempty、
  [test_cmo_completion_uses_sbempty_without_sqempty](../../../tests/sbuffer/test_sbuffer.py)::test_cmo_completion_uses_sbempty_without_sqempty。

## 范围

不是缺陷。该结论只适用于当前两个空信号的消费者接线；如果未来 `sbempty` 加入
`sqempty`、CBO 改用 `flush.empty`，或 CMO 不再等 MSHR，需要重新审查。

## 证据

- [flush/empty 合同复核](../../spec/verification/evidence/flush-contract-review-20261024.md)
- 功能点 [SBT-FLUSH-01](../../spec/design/functional-points-sbuffer.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "FLUSH-EMPTY-TWO-LEVELS-REVIEWED",
  "title": "CMO 期间 flush.empty 受 sqempty 门控是两级空语义，不是缺陷",
  "kind": "investigation",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/sbuffer/docs/spec/verification/evidence/flush-contract-review-20261024.md",
        "suites/memblock/sbuffer/tests/sbuffer/test_sbuffer.py::test_fence_flush_empty_requires_sqempty",
        "suites/memblock/sbuffer/tests/sbuffer/test_sbuffer.py::test_cmo_completion_uses_sbempty_without_sqempty"
      ],
      "note": "CMO 消费 sbempty；fence/atomics 消费 flush.empty；两者不是同一层级"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/sbuffer/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "suites/memblock/sbuffer/docs/spec/verification/evidence/flush-contract-review-20261024.md"
    ],
    "note": "依据 RISC-V CMO 规范、上游 PR #6183 和消费者接线复核；不是缺陷"
  }
}
```
