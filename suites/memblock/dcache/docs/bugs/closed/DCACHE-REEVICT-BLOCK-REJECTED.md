# DCACHE-REEVICT-BLOCK-REJECTED：Release 未接受时的同块拒绝是写回阻塞契约

状态：**已关闭（仅历史误报分类），非缺陷**。该 `closed/invalid` 只关闭历史基线的误报，
当前默认基线 `public-a0c2a26cb` 另未复验（JSON 记 `unverified`）。
被替换 block 的再次 miss 返回 `handled=0`/`replay=1`，
不是永久拒绝，而是 WritebackQueue 尚未完成 C 通道 Release 时的 block 级阻塞。

## 原问题

填满 4 way 后访问第 5 个 block 触发替换；此后再次访问被替换 block，load 恒为
`miss=1, handled=0`，store 恒为 `replay=1`。等待 0/50/400 周期都不恢复，看起来像
“永久拒绝”。

## 独立预期

Release 未被 L2 接受（`c_ready=0`）时，WritebackQueue 条目仍占用该 block；MissQueue
通过 `io_block_miss_req` 拒绝为同一 block 分配新 MSHR。`handled=0` 表示 LSU 应重试，
store 的 `replay=1` 同理。C 通道放行并收到 `ReleaseAck` 后，同一 block 的 miss 必须
立即恢复 `handled=1`。阻塞是 block 级、暂时的，不是永久拒绝。

## 复现与对照

新增用例 [test_pending_release_blocks_remiss_until_drained](../../../tests/dcache/test_dcache.py)::test_pending_release_blocks_remiss_until_drained：

1. 填满 4 way，访问第 5 个 block（`c_ready=0`）触发替换。
2. 对被替换 block 的 load 得到 `miss=1, handled=0`。
3. `c_ready=1` 并回 `ReleaseAck`。
4. 同一 block 的 load 得到 `miss=1, handled=1` 并完成 refill。

此前“永久拒绝”的观测是因为测试环境 `_idle()` 默认把 `c_ready` 清 0，替换产生的
Release 从未被接受；不是 RTL 卡死。随机流量生成器现在保持 L2 侧常开，并在
`handled=0` 时重试。

## 范围

不是缺陷。真实系统里 L2 会接受写回并回 ack；替换语义由定向用例覆盖。该结论不证明
其他 C 通道反压形态或错误响应，只覆盖已验证的 Release/ReleaseAck 生命周期。

## 证据

- [P0 收口报告第 2.5 节](../../spec/verification/evidence/p0-closure-20261026.md)
- 功能点 [DC-FP-005](../../spec/design/functional-points-dcache.md) 与
  [WQ-FP-005](../../spec/design/functional-points-writeback-queue.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "DCACHE-REEVICT-BLOCK-REJECTED",
  "title": "Release 未接受时同 block 的 miss 被拒是写回阻塞契约",
  "kind": "investigation",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
        "suites/memblock/dcache/tests/dcache/test_dcache.py::test_pending_release_blocks_remiss_until_drained"
      ],
      "note": "c_ready=0 时 handled=0；drain + ReleaseAck 后恢复 handled=1"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/dcache/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md"
    ],
    "note": "原观测由测试默认 c_ready=0 造成；行为符合写回阻塞契约"
  }
}
```
