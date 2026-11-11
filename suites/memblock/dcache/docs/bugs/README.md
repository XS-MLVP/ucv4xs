# DCache 问题记录

本目录保存 DCache 工程的稳定问题 ID。**open/closed 目录表示当前处理状态**，正文和
`ucv-bug` JSON 中的 `versions` 保留各基线的结论与证据；历史修复不自动迁移到当前版本。

- 已修复但未在当前默认基线复验的条目仍留在 `open/`，并在正文说明历史证据范围。
- `closed/` 只用于已经完成处置的问题：历史误报（`invalid`）、重复（`duplicate`）或
  确实退役的设计/接口（`retired`）。`invalid` 只关闭历史误报分类，正文和 `versions`
  仍标明当前默认基线未复验。
- 范围、资源或既有接口约束不放在本目录；稳定 ID、说明和原依据见
  [verification/constraints.md](../spec/verification/constraints.md)。
- 历史台账 [manifest/known-issues.json](../../manifest/known-issues.json) 仅作为迁移来源和旧记录证据；当前状态以本目录为准。

修复或重新分类后，确认对应测试/证据仍可读，再运行 `./scripts/ucv docs dcache --write`
刷新自动索引。不要通过修改期望、增加豁免或删除反例来关闭问题。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（2）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [CF-DEQUEUE-PIPELINE-NO-RESET](open/CF-DEQUEUE-PIPELINE-NO-RESET.md) | 短复位后 CounterFilter 出队流水可能永久偏移 FIFO 指针 | rtl | 未复验 | — |
| [MQ-STORE-MERGE-DATA-PENDING](open/MQ-STORE-MERGE-DATA-PENDING.md) | 同一 cache line 第二笔部分 store 合并后字节丢失 | rtl | 未复验 | — |

## 已关闭（5）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [BDA-DUPLICATED-BANK-ADDR](closed/BDA-DUPLICATED-BANK-ADDR.md) | bank 0..15 使用 addr_dup 是 duplicated query 设计，不是地址缺陷 | investigation | 未复验 | invalid |
| [BDA-ECC-DELAYED-FLAG](closed/BDA-ECC-DELAYED-FLAG.md) | 未初始化 SRAM 行的 ECC 告警被误判为编解码缺陷 | investigation | 未复验 | invalid |
| [DCACHE-DENIED-ERROR-PADDR-ZERO](closed/DCACHE-DENIED-ERROR-PADDR-ZERO.md) | L2 denied/corrupt 的 io_error.paddr 只保留 vaddr[11:0] | investigation | 未复验 | invalid |
| [DCACHE-REEVICT-BLOCK-REJECTED](closed/DCACHE-REEVICT-BLOCK-REJECTED.md) | Release 未接受时同 block 的 miss 被拒是写回阻塞契约 | investigation | 未复验 | invalid |
| [DCACHE-REFILL-NOT-RESIDENT](closed/DCACHE-REFILL-NOT-RESIDENT.md) | 冷 load refill 后不命中（原 RTL 指控不成立，当前基线未复验） | verification | 未复验 | invalid |

<!-- ucv:bugs:end -->
