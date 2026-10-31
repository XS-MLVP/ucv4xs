# Sbuffer 顶层：入队/写出/排空/转发 UT

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 1. 结论

真实 `Sbuffer` DUT（内部保留真实 `SbufferData`）完成 **16/16 PASS**，功能覆盖 8 组
全部 100%。DUT-only LCOV 行 **12648/13191 = 95.88%**，原生 toggle
**70275/85706 = 82.0%**，branch **2690/2724 = 98.8%**。剩余 543 行已逐项分类，
未删分母、未使用 xfail/skip。

运行目录：`results/sbuffer-top-contract-03/`（toffee runner committed，
`coverage_complete=true`）。构建不启用 VPI、不启用 internal-cfg；运行时关闭波形、
不写逐周期信号/事务 dump，证据树 0 个 fst/vcd、0 个 JSONL。
`trace-policy.json` 为 PASS。

## 2. 功能点

见 [`../functional-points-sbuffer.md`](../functional-points-sbuffer.md)。语义级功能点：

| 编号 | 语义 |
|---|---|
| SBT-ENQ-01 | 新行分配、已有行 merge、两端口同拍、同新行两端口写入 |
| SBT-ENQ-02 | 物理行被不同虚标签写入时触发 uarch drain |
| SBT-ENQ-03 | 16 行容量、`sbFull` 阻塞、释放后恢复 |
| SBT-ENQ-04 | 同块 inflight 时新行可分配但不得提前写出 |
| SBT-WRITE-01 | 写出请求的行地址/lane data/mask 与存储内容一致 |
| SBT-WRITE-02 | replay 后同一行槽重发，最终 hit 释放 |
| SBT-FLUSH-01 | 普通/CMO/uarch 三种排空的完成条件；CMO 内部状态机不看 SQ，但公开 `flush.empty` 仍包含 `sqempty` |
| SBT-FLUSH-02 | 排空期间阻塞入队，按行写出，全部释放后 empty |
| SBT-FWD-01 | 三路 load 转发，active 优先于 inflight，按行/lane 返回字节 mask/data |
| SBT-FWD-02 | 虚/实标签单向不一致告警，kill 抑制告警 |
| SBT-RESET-01 | 复位清空行和在途请求 |

## 3. 用例

| 用例 | 覆盖 |
|---|---|
| `test_reset_and_idle` | 空闲复位、sbempty/sbFull/无请求 |
| `test_merge_and_forward` | merge、三路转发、虚实不一致、kill、4 lane 查询 |
| `test_dual_port_enqueue` | 同拍异行/同行异 lane/同字节覆盖 |
| `test_timeout_writeout_all_lanes` | 行超时写出、四个 lane 的请求 payload |
| `test_replay_resends_same_line` | replay → 同一行重发 → hit；inflight-only 转发 |
| `test_fence_flush_empty_requires_sqempty` | 普通 flush：排空后 `sbempty=1`，但 `flush.empty` 等 sqempty |
| `test_cmo_completion_uses_sbempty_without_sqempty` | CMO 等 MSHR；MSHR 空后 `sbempty=1` 即使 sqempty=0 |
| `test_uarch_drain_on_vtag_mismatch_merge` | 跨虚标签 merge → uarch drain → 恢复入队 |
| `test_capacity_full_and_resume` | 16 行满、sbFull、替换释放、恢复 |
| `test_sameblock_serialization` | 同块 inflight 时新行不写出，hit 后才写出 |
| `test_reset_with_entries` | 有行时复位 |
| `test_port1_same_tag_fills_all_slots` | 16 槽 × 4 lane 的双端口写入，两个端口交替拥有低/高字节半区 |
| `test_replay_each_line_slot` | 16 个槽逐一 replay/retry/hit |
| `test_wline_zero_all_lines` | 16 槽 cbo.zero 形态（零 payload wline）、四 lane 转发与全零检查 |
| `test_each_lane_merge_and_forward` | 8 行 × 4 lane × 两端口 merge、三路转发 |
| `test_data_bit_saturation` | 8 槽全 lane 写 0/1/0，饱和 data 输出 toggle |

独立参考 `sbufferverify/sbuffer/model.py` 以物理标签行、字节 mask/data 和生命周期建模。
写出请求不预测 PLRU 槽号，而是按 payload 匹配唯一活行，再检查 id 合法、非 inflight、
同块不 inflight；这样不把实现相关的槽选择写进参考。

## 4. 覆盖率

### 4.1 总览

| 指标 | 结果 |
|---|---|
| Verilator line points | 809 / 1269（63.8%） |
| Verilator toggle | 70275 / 85706（82.0%） |
| Verilator branch | 2690 / 2724（98.8%） |
| LCOV 全部唯一行 | 12651 / 13768（91.89%） |
| LCOV DUT-only | **12648 / 13191（95.88%）** |
| DUT-only 过程语句未覆盖 | 543 |
| 功能覆盖 | 8 组 100% |

### 4.2 分文件

| 文件 | 角色 | 行命中/唯一行 | 过程未覆盖 |
|---|---|---:|---:|
| `SbufferDut.v` | DUT | **4642/4673（99.34%）** | 31 |
| `SbufferData.sv` | DUT 子块 | **8006/8518（93.99%）** | 512 |
| `SbufferDut_top.sv` | Picker harness | 3/577（0.52%） | 408 |

harness 是 Picker 生成的端口连线顶层，不计入 DUT 覆盖闭合；保留原始分母供核对。

### 4.3 未覆盖项逐项定位

| 缺口 | 行数 | 分类 | 归属 |
|---|---:|---|---|
| `SbufferDut.v` 11133–11286 | 31 | `waitInflightMask` 在高槽的写路径；已有 SBT-ENQ-04 只命中部分槽，缺“同块 inflight 时 follower 插入全部 16 槽”的情形枚举 | SBT-ENQ-04 缺失情况 |
| `SbufferData.sv` 16 组高槽 lane 区间 | 512 | 每个槽/ lane 的另一半字节只由另一个端口写；同 lane 双端口两半都写需要额外 merge 轮次，父块 ready 依赖与容量替换限制了构造 | SBT-ENQ-01 / SBT-WRITE-01 缺失情况 |
| `SbufferData.sv` 时间零 `if(reset)` else | 1 分支 | 生成 `initial` 只在时间 0 执行一次 | 工具/时间零边界 |

分支 34 项：33 项在 `waitInflightMask` 区域，1 项是时间零 `initial` 的 `if(reset)`。

Toggle 剩余 15497 点（18.1%）：

| 类别 | 数量 | 说明 |
|---|---:|---|
| `other` | 5244 | 声明/内部组合/未激活配置位 |
| `storage_output_bit` | 2938 | 高槽 data/mask 输出位的双向翻转 |
| `line_state_bit` | 3946 | 高槽 valid/inflight/timeout/同块位图的双向翻转 |
| `internal_write_pipeline` | 1338 | 高槽 lane 的另一半字节写缓冲 |
| `forward_bit` | 986 | 转发地址高位组合 |
| 其余 | ~305 | 入队/写出/输入位 |

归属：SBT-WRITE-01 / SBT-ENQ-01 的“全 16 槽 0/1 饱和、地址高位随机、同 lane 双端口
两半都写”情形缺失，不是新的微架构功能点。

## 5. CMO/fence 两级空语义（已由文档确认）

Sbuffer 的两个空信号有不同消费者：

- `sbempty` = Sbuffer 行 + 输入 + MSHR 空，接 LSQ 的 `SbufferCtrlIO.Resp.empty`，
  由 CBO FSM 消费；CMO 只要求这一级。
- `flush.empty` = `sbempty && sqempty`，接 `MemBlock.stIsEmpty`，由 Fence 的
  `sbIsEmpty` 和 AtomicsUnit 消费；fence/atomics 要求整条 store 路径空。

CMO 必须在 SQ 头部执行，其自身 SQ 条目在 writeback 前不释放，因此 CMO 期间
`sqempty` 必为 0；若 CMO 等 `flush.empty` 会死锁。上游 PR #6183 明确拆分了
`cmo_empty`/`all_empty`，`MemBlock` 的接线也把 `sbempty` 和 `flush.empty` 分给不同
消费者。测试按这一合同检查：CMO 排空后即使 `sqempty=0` 也要求 `sbempty=1`，而
`flush.empty` 继续保持 0，直到 `sqempty=1`。

完整证据链（RISC-V CMO 规范、PR #6183、Fence/Atomics/CBO FSM 接线）见
[flush 合同复核](flush-contract-review-20261024.md)。结论：这不是缺陷，之前的怀疑是
把两个不同层级的 empty 混为一个信号造成的假阳性。

## 6. 复现与资源

```sh
cd memblock-hash/sbuffer
python3 tools/build_dut.py            # 只在 dut/sbuffer 不存在时
python3 tools/run.py --name sbuffer-top-repro-01 --workers 1 tests/sbuffer
python3 tools/coverage_audit.py sbuffer-top-contract-03
```

构建参数为 `--rw mem_direct -w memory-direct.fst -c`，无 `--vpi`、无 `--internal`。
顶层 `wline` 只用零 payload（父块只对 cbo.zero 产生 wline），非零 payload 仅作为
`SbufferData` 模块能力验证，不计入父块行为证据。
`conftest.py` 把 pytest 进程切到临时 cwd，`tools/run.py` 再清理 Picker 默认 dumpfile；
因此正常运行不会在项目或证据目录留下波形。证据目录只保留 coverage.dat/info、功能覆盖
JSON、manifest、audit 和报告；单次 run 约 22MiB。
