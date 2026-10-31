# MissQueue UT 报告（2026-10-25 建，2026-10-26 数据更新）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 1. 范围与证据

| 项 | 值 |
|---|---|
| DUT | `MissQueue`（`rtl/miss_queue/MissQueue.sv`，含 `MissEntry.sv`、`CMOUnit.sv`、`SpecMissGrantRegister.sv`、`Arbiter16_MainPipeReq.sv`） |
| RTL 基线 | XiangShan `kunminghu-v3 @ 893e1580`，`soc-split/rtl` split-verilog |
| 工具 | Picker `2.0.0-HEAD-4dd442c`、Verilator `5.052`、toffee `2.0.0.dev12` |
| 构建 | `results/builds/20261025T010644*-miss_queue`（mem_direct + `-c`） |
| 最终运行 | `results/full-regression-15` 的 `miss_queue` 构建（**29 passed + 1 xfailed**，共 30 个用例）；单模块历史运行 `mq-main-03`（24 passed）保留 |
| 功能点 | `docs/functional-points-miss-queue.md`（MQ-FP-001…010） |
| 驱动/模型 | `dcacheverify/miss_queue/env.py`（公开端口 + 64B 两拍 refill 模型） |
| 用例 | `tests/miss_queue/test_miss_queue.py` |

## 2. 功能点与用例对应

| 功能点 | 覆盖的微架构行为 | 主要用例 |
|---|---|---|
| MQ-FP-001 | 四口 MSHR 分配、A 通道 Acquire、misstrack 分配信息 | `test_load_miss_allocates_mshr_and_acquires`、`test_mshr_id_and_channel_selection`、`test_loadpipe_ports_and_channel1_amo`、`test_parallel_enqueue_allocates_three_mshrs` |
| MQ-FP-002 | merge 窗口（首 beat 前/后）、alias 冲突、同拍 compress、多口并行 merge 记账 | `test_merge_only_before_first_refill_beat`、`test_merge_after_grant_alias_mismatch`、`test_same_cycle_same_block_compresses`、`test_parallel_merge_into_one_pipe_reg`、`test_parallel_store_merge_accounting`、`test_second_store_merge_carries_its_bytes`（xfail） |
| MQ-FP-003 | store/整行 store/AMO 的权限与字段透传、BtoT occupy_way | `test_store_miss_modes`、`test_amo_miss_forwards_atomic_fields`、`test_btot_occupy_way_is_forwarded`、`test_amo_miss_uses_channel_one` |
| MQ-FP-004 | 两拍 GrantData 拼接、MainPipe 安装、refill_info | `test_two_beat_refill_installs_line`、`test_store_miss_refill_merges_store_data`、`test_entry_release_and_slot_reuse` |
| MQ-FP-005 | Finish（E 通道）返回 | `test_finish_is_returned_for_grant` |
| MQ-FP-006 | probe/replace 阻塞、WBQ 反压、l2hint | `test_probe_and_replace_blocked_by_inflight_mshr`、`test_wbq_backpressure_blocks_acceptance`、`test_mainpipe_feedback_reissues_install` |
| MQ-FP-007 | CMO 通道映射与响应 | `test_cmo_ops_map_to_a_channel`、`test_cmo_response_denied_and_corrupt`、`test_cmo_all_opcode_response_pairs` |
| MQ-FP-008 | refill denied/corrupt 上报 | `test_refill_error_flags` |
| MQ-FP-009 | load/store 标志位与释放后清零 | `test_store_flag_clears_after_completion` |
| MQ-FP-010 | 多 release 槽位 | `test_release_slots_one_to_three` |

## 3. 覆盖率结果（`full-regression-15` 的 miss_queue 构建）

| 指标 | 命中 / 分母 | 覆盖率 |
|---|---:|---:|
| 行（DUT-only） | 1853 / 2099 | 88.28% |
| 分支（Verilator 原生点） | 953 / 1334 | 71.44% |
| Toggle（DUT-only） | 23476 / 47506 | 49.42% |
| 功能覆盖 | 7 组 | **100.00%** |

分源文件行覆盖：

| 文件 | 行命中 / 唯一行 | 覆盖率 |
|---|---:|---:|
| `MissQueueDut.v` | 1097 / 1343 | 81.68% |
| `MissEntry.sv` | 470 / 473 | 99.37% |
| `CMOUnit.sv` | 32 / 32 | 100% |
| `SpecMissGrantRegister.sv` | 27 / 27 | 100% |
| `Arbiter16_MainPipeReq.sv` | 224 / 224 | 100% |

### 3.1 未覆盖归因（246 行 / 194 过程行）

| 位置（`MissQueueDut.v` 行号） | 过程行 | 分类 | 说明 |
|---|---:|---|---|
| `s1RespDataFwd_*` / `s1RespMask_stLdFwd_*`（8804-9078 等） | 80 | **范围限制** | 面向 LoadPipe/Sbuffer 的 store→load 转发寄存器，由 `io.forward_*` / `io.forward_stData` 驱动，不属 MSHR 语义 |
| 默认 `else` 臂（6569-6823 等） | 36 | 工具/生成代码限制 | 优先级链的兜底分支，合法输入下不可达（父块保证至少一个 valid） |
| `source_except_load_cnt` 深层链 | 26 | 情形缺失（部分） | 4 个 `queryMQ` 口的复位/自增优先级链；四口轮转用例已加，剩下的是多口同拍组合 |
| `parallel_pipe_regs_N_mshr_id` 记账 | 19 | 情形缺失（部分） | 多口 merge 到同一 entry 的更深组合 |
| 三元默认值 / 其它 | 32 | 混合 | 常量折叠臂、声明行 |
| 声明行 | 53 | — | wire/reg 声明，不是可执行语句 |
| `MissEntry.sv` | 3 | 情形缺失 | 从 160 行降到 3 行：store-merge 数据路径已由 xfail 用例实际执行 |

**没有“整体功能点缺失”**：7 个功能组全 100%，MSHR 分配/合并/refill/安装/Finish、
probe/replace 阻塞、CMO、错误上报、多 release 槽位都有行为断言。

### 3.2 与上一版（`mq-main-03`，24 passed）

| 项 | mq-main-03 | full-regression-11 | 原因 |
|---|---:|---:|---|
| 用例 | 24 passed | 29 passed + 1 xfailed | 新增双口/三口并行 merge、四口轮转 store、8 连发 store、store-merge 缺陷复现 |
| 行 | 1673/2099 = 79.7% | 1853/2099 = 88.3% | merge 数据路径与多口记账被实际执行 |
| `MissEntry.sv` | 305/473 = 64.5% | 470/473 = 99.4% | store-merge 的 `refill_and_store_data` 分支被执行 |

### 3.3 已知缺陷

`MQ-STORE-MERGE-DATA-PENDING`：第二笔 store 合并被受理（`ready=1`、`handled=1`、
无第二次 Acquire），但其 `store_data/store_mask` 未进入 `refill_and_store_data`；
`refill_info.store_data` 低 16 位为 `0x01AA`（期望 `0xBBAA`）。用例
`test_second_store_merge_carries_its_bytes` 以严格 xfail 固化。
详情见 `docs/reports/p0-closure-20261026.md` 第 2.1 节。

## 4. 结论

- MSHR 分配/合并/refill/安装/Finish、probe 与 replace 阻塞、CMO、错误上报、
  多 release 槽位的语义均已由行为级断言覆盖，7 个功能组 100%。
- `MissEntry.sv` 只剩 3 行未覆盖；剩余缺口集中在 `MissQueueDut.v` 的
  store→load 转发寄存器和更复杂的多口记账组合，已分类为范围限制/情形缺失。
- 唯一实质问题是已确认的 store-merge 数据丢失缺陷，由严格 xfail 固化，
  不计入“已通过”。
