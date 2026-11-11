# MissQueue 功能点（本轮 UT 范围）

DUT：`MissQueue`（`soc-split/rtl/MissQueue.sv` + `MissEntry.sv` + `CMOUnit.sv`），
层次：DCache 的 16 项 MSHR 阵列与 L2 请求/回填/完成逻辑。端口包括 4 个 miss 申请口
（MainPipe 的 `queryMQ_0` 与 LoadPipe 的三个口）、A/D/E 通道（Acquire/Grant/Finish）、
MainPipe 安装接口、probe/replace 阻塞、CMO 与 store-miss 状态。

MissQueue 的内部流程是：S0 判断 allocate/merge/compress，S1 真正分配或合并；分配后向
L2 发 Acquire；两个 32B GrantData beat 组成 64B 行，最后一个 beat 后请求 MainPipe 安装；
MainPipe 写回完成并通过 `main_pipe_resp.ack_miss_queue` + `s3_refill_resp` 确认后释放
entry，同时回 Finish。本 UT 只驱动公开端口，用 64B 行模型核对回填数据与 store 合并；
speculative miss、L2 hint、WFI、BtoT 占位集合等旁路未纳入本轮。

## MQ-FP-001 miss 分配与 Acquire 发起

`queryMQ_<port>` 在 `ready=1` 时接收 miss 申请，随后（同一拍或下一拍）在对应 L2 通道
发出 Acquire：`opcode=AcquireBlock(6)`（整行 store 为 `AcquirePerm(7)`）、
`size=6`（64B）、`address` 为块地址、`user.alias` 为 `get_alias(vaddr)`、
`user.vaddr` 为 `vaddr[49:6]`、`source` 为分配的 MSHR id。
`io_misstrack_alloc_<port>` 在分配后一拍给出 `paddr/vaddr/mshr_id`，MSHR id 按空闲槽
低位优先分配。

## MQ-FP-002 MSHR 合并（merge）

同一 64B 块的第二个 miss 在首个 refill beat 之前到达时，不重新分配也不重发 Acquire，
而是合并到已有 entry（`resp.handled=1` 且返回该 entry 的 id）；首个 beat 之后合并窗口
关闭，`ready=0` 表示拒绝。合并要求块地址相同且 `vaddrAlias` 一致；alias 不同即视为
不同 set 的别名冲突，同样拒绝。

**多口并行合并**：同一拍在多个 `queryMQ` 口上请求同一块时，每口独立判定
`secondary_ready`，都返回 `handled=1` 且 `id` 指向同一 entry；不会分配新 entry，也
不会重发 Acquire。用例 `test_parallel_merge_into_one_pipe_reg`、
`test_parallel_store_merge_accounting` 覆盖该记账路径。

**已知缺陷（`MQ-STORE-MERGE-DATA-PENDING`）**：第二笔**store** 合并被受理后，其
`store_data/store_mask` 没有进入 `refill_and_store_data`；refill 行只含第一笔 store
的字节，第二笔覆盖的字节要么保留 L2 值、要么被 0 覆盖。独立 UT 观测
`refill_info.store_data` 低 16 位为 0x01AA（期望 0xBBAA），DCache 顶层观测安装行为
0x00AA。用例 `test_second_store_merge_carries_its_bytes`（严格 expected-failure）与
`test_parallel_store_merge_accounting`（多口记账）固定该现状。

## MQ-FP-003 store/AMO miss 的权限与数据

store miss 的 `req_coh` 决定增长权限：整行覆盖时发 `AcquirePerm`（NtoT），部分写时发
`AcquireBlock`（NtoB）。store 数据/掩码保存在 entry 中，refill 时与 L2 数据按字节合并，
Mask 为全 1 时整行取 store 数据。AMO miss 透传 `cmd/amo_data/amo_mask/amo_cmp/word_idx`
并在 refill 后交给 MainPipe 执行；BtoT 请求透传 `occupy_way` 供 refill 选路。

## MQ-FP-004 两拍 refill 与 MainPipe 安装

64B 行由两个 32B GrantData（`opcode=5`, `size=6`）组成，按 beat 顺序拼成 512-bit 行。
第二个 beat 后 `io_main_pipe_req` 发起安装（`miss_id` 为本 entry，`cmd/addr/vaddr/
source/store_data/store_mask/occupy_way` 来自保存的 miss 请求）；MainPipe 在 S2 用同一
`miss_id` 拉高 `io_mainpipe_info.s2_valid` 时，`io_refill_info` 返回该行的
`store_data`（全 1 `store_mask`）、`miss_param`（grant 权限）与错误位。

## MQ-FP-005 refill 错误与 Finish

GrantData 的 `denied`/`corrupt` 在 entry 中累积，并在 `refill_info`
（`error_tl_denied` / `error_tl_corrupt`）中上报给 MainPipe，用于错误标记与 BEU 上报。
AcquireBlock/Perm 对应的 Finish 在收到 grant 后以 grant 的 `sink` 回发。

## MQ-FP-006 entry 释放与槽位复用

`Finish` 已回、MainPipe 已确认 `ack_miss_queue`、且 `s3_refill_resp` 命中同一 miss id
后 entry 释放；释放后的槽位可被后续 miss 立即重新分配（id 从 0 重新开始），并再次
正常发出 Acquire。

## MQ-FP-007 in-flight 块对 probe/replace 的阻塞

entry 处于有效状态且已完成最后一个 beat 时，若 probe（或 replace）的块地址与 entry
相同且 alias 一致，`io_probe_block`（`io_replace_block`）为 1，阻止上层对该块的
probe/替换；块地址或 alias 不同则为 0。refill 未完成前不阻塞。

## MQ-FP-008 CMO 通道

`io_cmo_req` 支持 cbo.clean/flush/inval（opcode 0/1/2），分别映射为 A 通道 opcode
12/13/14、`size=6`、`source=nMissEntries+1`，并按块地址 bit6 选择 L2 通道。
D 通道 CBOAck 的 `denied`/`corrupt` 在 `io_cmo_resp` 中回传，随后可接受下一个 CMO。

## MQ-FP-009 L2 通道选择

同一块的低 6 位地址决定通道：`block_addr[6]` 为 0/1 时 Acquire 走通道 0/1，
`io_mem_acquire_<ch>` 的 source 仍是该 entry 的 MSHR id，地址保持块地址。

## MQ-FP-010 store miss 状态标志

`io_mshr_store_empty` 在没有 store miss 的 entry 时为 1；存在 store miss 时变 0，
该 store miss 完成释放后恢复为 1，供 Sbuffer 判断是否还有未写出的 store。

## 未纳入本轮范围

- speculative miss 预留（`io_spec_query_*` / `io_spec_fabric_*`）；
- L2 hint（`io_l2_hint_*`）、WFI 与 prefetch 统计；
- `io_forward_*`、`io_rob_head_query`、`io_wfi`；
- BtoT 占用集合对 LoadPipe 的 `occupy_fail`（由 DCache 顶层用例覆盖）；
- 与 MainPipe/LoadPipe 的真实跨模块时序（由 DCache 顶层用例覆盖）。
