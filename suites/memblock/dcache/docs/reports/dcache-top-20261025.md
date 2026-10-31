# DCache 顶层 UT 报告（2026-10-25）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 1. 范围与证据

| 项 | 值 |
|---|---|
| DUT | `DCache`（`rtl/dcache/DCache.sv`，含 3×LoadPipe、MainPipe、MissQueue、ProbeQueue、WritebackQueue、CtrlUnit、MissTrack、CounterFilter、data/tag/meta 阵列） |
| RTL 基线 | XiangShan `kunminghu-v3 @ 893e1580`，`soc-split/rtl` split-verilog |
| 工具 | Picker `2.0.0-HEAD-4dd442c`、Verilator `5.052`、toffee `2.0.0.dev12` |
| 构建 | 重定位后重建：`results/builds/20261025T021240061784Z-dcache/report.json` |
| 最终运行 | `results/soundness-recheck-03` 中的 `dcache` 构建（**25 passed / 1 xfailed**，含状态空间扫描、prefetch 标记扫描、随机流量与已知缺陷用例） |
| 功能点 | `docs/functional-points-dcache.md`（DC-FP-001…013） |
| 环境 | `dcacheverify/dcache/env.py`（公开 TL 通道 + LSU load/store/atomic/CMO 端口） |

## 2. 功能点与用例对应

| 功能点 | 行为 | 用例 |
|---|---|---|
| DC-FP-001 | 复位 + 256 拍 SRAM 清扫后才允许事务 | `DcacheEnv.reset()` + 所有用例 |
| DC-FP-002 | load 命中、3 lane 独立访问、16B 窗口数据 | `test_cold_miss_refill_then_hit`、`test_all_three_load_lanes`、`test_three_lanes_same_line`、`test_partial_load_masks` |
| DC-FP-003 | 冷 miss→AcquireBlock→2×GrantData→重放命中 | `test_cold_miss_refill_then_hit`、`test_lq_nonempty_miss` |
| DC-FP-004 | 硬件预取装入与 prefetch 标记清除（`io_prefetch_req` → demand 命中清标记） | `test_prefetch_install_then_demand_hit_clears_flag` |
| DC-FP-005 | 替换与写回阻塞契约：Release 未接受时同 block 拒绝分配，drain+ack 后恢复 | `test_pending_release_blocks_remiss_until_drained` |
| DC-FP-006 | 双 L2 通道按 paddr[6] 选择 | `test_dual_channel_selection` |
| DC-FP-007 | store 命中/掩码合并、store miss 与 refill 行合并；第二笔合并 store 为已知缺陷 | `test_store_then_load_observes_data`、`test_store_masks_and_readback`、`test_store_miss_with_refill`、`test_store_mask_classes`、`test_two_partial_stores_same_missing_line_merge_data`（xfail） |
| DC-FP-008 | MSHR 池耗尽 → handled=0 | `test_mshr_full_yields_unhandled_miss` |
| DC-FP-009 | denied/corrupt refill → io_error（paddr = vaddr[11:0]） | `test_refill_denied_reports_error`、`test_corrupt_refill`、`test_denied_refill_error_paddr_is_vaddr_low_bits` |
| DC-FP-010 | B 通道 probe → C ProbeAck(Data) | `test_probe_ack`、`test_dcache_probe.py` |
| DC-FP-011 | dirty/clean victim 的 C 通道 Release(Data) | `test_dirty_eviction_releases_line`、`test_clean_eviction_releases_without_data` |
| DC-FP-012 | AMO swap/add 命中与 miss→refill 完成 | `test_atomic_swap_and_add_hit`、`test_atomic_miss_completes_after_refill` |
| DC-FP-013 | CMO clean/flush/inval × denied/corrupt | `test_cmo_opcodes_and_responses` |
| 约束随机 | load/store 混合、L2 shadow + 未写回字节模型 | `test_constrained_random_load_store_traffic` |

## 3. 覆盖率结果（`soundness-recheck-03` 的 dcache 构建）

| 指标 | 命中 / 分母 | 覆盖率 |
|---|---:|---:|
| 行（DUT-only） | **50262 / 51179** | **98.21%** |
| 分支（Verilator 原生点） | 18986 / 20504 | 92.60% |
| Toggle（DUT-only） | 168576 / 332370 | 50.72% |
| 功能覆盖 | 8 组 | **100.00%** |

未覆盖 919 行**全部是内联子模块的重复计数**（MainPipe 281、MissQueue 241、
CounterFilter 90、`DcacheDut.v` 67、CtrlUnit 42…），这些子模块在各自 DUT 构建里
已单独统计。两张 prefetch 元数据表经新用例扫描后只剩 9+9 行。
逐项见 `coverage-20261025.md` 第 4 节。

### 3.1 与上一版（`full-regression-07`，20 passed）

| 项 | full-regression-07 | soundness-recheck-03 | 原因 |
|---|---:|---:|---|
| 用例 | 20 passed | 25 passed + 1 xfailed | 新增写回阻塞、约束随机、状态空间扫描、prefetch 标记扫描、store-merge 缺陷复现 |
| 行 | 35452/51179 = 69.27% | **50260/51179 = 98.20%** | 256 set × 4 way × 4 端口扫描 + prefetch 标记扫描 |
| 功能组 | 7 | 8 | 新增 DC-FP-004（替换与写回阻塞契约） |

覆盖率提升靠两个"扫状态空间"用例：

1. `test_all_sets_all_ways_update_replacement_state`：填满 256 set × 4 way，再按 4 个
   touch 端口各扫一遍 → `L1ErrorMetaArray`、`L1CohMetaArray` 到 100%，`DcacheDut.v`
   52.3% → 99.4%。
2. `test_prefetch_install_then_demand_hit_clears_flag`：用 `io_prefetch_req` 装入
   预取行、demand load 命中清标记，扫 256 set × 4 way →
   `L1PrefetchSourceArray` 83.6% → 99.86%、`L1RefillLatencyArray` 83.4% → 99.86%。

## 4. 未覆盖行归因（DUT-only 919 行）

| 类别 | 行数 | 判定 |
|---|---:|---|
| 内联子模块（各自已有独立 UT） | **919（100%）** | MainPipe 281、MissQueue 241、CounterFilter 90、`DcacheDut.v` 67、`NewPipelineConnectPipe_9` 64、CtrlUnit 42、BankedDataArray 32 等。**重复计数，不是 DCache 独有行为缺口**。 |
| 两张 prefetch 表残留 | 9 + 9 | 声明/默认臂；主路径已由 prefetch 扫描覆盖 |

## 5. 结论

- 12 个功能点全部有用例与行为断言，8 个功能组 100%。
- 已确认 1 个 RTL 缺陷（`MQ-STORE-MERGE-DATA-PENDING`，严格 xfail 固化），
  其余曾怀疑的问题均已澄清为非缺陷（见 `p0-closure-20261026.md`）。
- 顶层剩余行覆盖缺口 94% 来自 SRAM 阵列全扫与生成代码，不是功能未验证。
