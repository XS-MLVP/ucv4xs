# MQ-STORE-MERGE-DATA-PENDING：同一行第二笔部分 store 合并后字节丢失

状态：**确认 RTL 缺陷，未修复**。两个严格 expected-failure 用例分别固定在 MissQueue
独立 DUT 和 DCache 顶层；修复后应转为 unexpected pass，再重新判定相关功能点。
当前默认基线 `public-a0c2a26cb` 尚未重新构建或回归，`versions` 记该基线为 `unverified`；
历史失败证据只属于 `public-893e1580b`。

## 怎样触发

1. 对一个尚未驻留的 64B cache line 发起第一笔部分 store：例如写 byte0=0xAA、mask=0x01。
2. 在该 line 的 refill 数据返回前，对同一 line 发起第二笔部分 store：写 byte1=0xBB、mask=0x02。
3. 第二笔在 MissQueue 中被合并受理（`queryMQ.ready=1`、`handled=1`，不产生第二次 Acquire）。
4. refill 完成后读回该 line，或观察 `refill_info.store_data`。

## 独立预期

第二笔被受理的 store 与第一笔一样，必须把其 `store_data/store_mask` 合并进
`refill_and_store_data`。若第一笔写 byte0、第二笔写 byte1，安装行低 16 位应为
`0xBBAA`；L2 原始 byte1 不应覆盖第二笔的新数据，第二笔字节也不能被 0 覆盖。合并
受理意味着 LSU 可以认为该 store 已被接管，因此不能静默丢失字节。

## 已观察到的结果

| 层 | 观测 | 期望 |
|---|---|---|
| MissQueue 独立 DUT | `refill_info.store_data` 低 16 位 = `0x01AA` | `0xBBAA` |
| DCache 顶层 | 安装行低 16 位 = `0x00AA` | `0xBBAA` |

两个严格 xfail 用例：

- [tests/miss_queue/test_miss_queue.py](../../../tests/miss_queue/test_miss_queue.py)::test_second_store_merge_carries_its_bytes
- [tests/dcache/test_dcache.py](../../../tests/dcache/test_dcache.py)::test_two_partial_stores_same_missing_line_merge_data

`--runxfail` 已确认失败点就是数据断言，不是环境或握手错误。多口合并记账的对照用例
[test_parallel_store_merge_accounting](../../../tests/miss_queue/test_miss_queue.py)::test_parallel_store_merge_accounting 仍保留；它只检查记账，不覆盖本缺陷的数据丢失。

## 根因与影响范围

`MissEntry.sv` 中 `refill_and_store_data` 的 store 合并分支和 `req_store_mask` 更新由
`_GEN_1 = io_miss_req_pipe_reg_merge & (io_miss_req_pipe_reg_req_source == 4'h1)` 门控。
第二笔 store 走 entry 级合并路径（`MissQueue.scala` 的 `before_data_refill_can_merge`：
`!main_pipe_refill_resp && !w_refill_resp && new_req.isFromStore && alloc_is_store`），
此时 `miss_req_pipe_reg` 上的 `merge`/`req_source` 并不表示“这笔是 store 合并”，因此
数据/掩码分支不执行。

影响：同一行连续两笔部分 store 会静默丢数据或写坏行内容，而 LSU 收到成功响应；影响
store→load 正确性和 dirty 数据完整性。修复方案待上游确认：在 entry 级 store 合并路径
写入 `refill_and_store_data`，或对第二笔 store 返回 replay 让 Sbuffer 重试。

## 证据

- [P0 收口报告第 2.1 节](../../spec/verification/evidence/p0-closure-20261026.md)
- 功能点 [DC-FP-007](../../spec/design/functional-points-dcache.md) 与
  [MQ-FP-002](../../spec/design/functional-points-miss-queue.md)
- 历史台账 [manifest/known-issues.json](../../../manifest/known-issues.json) 中的同名条目

```ucv-bug
{
  "id": "MQ-STORE-MERGE-DATA-PENDING",
  "title": "同一 cache line 第二笔部分 store 合并后字节丢失",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
        "suites/memblock/dcache/tests/miss_queue/test_miss_queue.py::test_second_store_merge_carries_its_bytes",
        "suites/memblock/dcache/tests/dcache/test_dcache.py::test_two_partial_stores_same_missing_line_merge_data"
      ],
      "note": "两个严格 xfail 复现；未修改 RTL 或放宽期望"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/dcache/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ]
}
```
