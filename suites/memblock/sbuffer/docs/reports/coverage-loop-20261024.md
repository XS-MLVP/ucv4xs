# Sbuffer 覆盖率闭环

本文件记录实际执行的“功能点 → 用例 → 运行 → 行/toggle/branch 分析 → 补功能点情形 →
补用例 → 重跑”闭环。数字来自各 run 的 committed manifest、`coverage.dat` 和
`coverage-audit.json`；分母不跨 DUT 合并。

## 1. SbufferData（独立子块 DUT）

| 运行 | 用例 | toggle | branch | DUT LCOV 行 | 过程未覆盖 |
|---|---:|---:|---:|---:|---:|
| `sbuffer-data-initial-01` | 13 PASS | 55419/70684（78.4%） | 2111/2116 | 6740/8518（79.1%） | 1778 |
| `sbuffer-data-initial-02` | 14 PASS | 66483/70684（94.1%） | 2115/2116 | **8518/8518（100%）** | **0** |
| `sbuffer-data-initial-04` | 15 PASS | **70684/70684（100%）** | 2115/2116 | **8518/8518（100%）** | **0** |

### 01 → 02

首轮未覆盖行集中在每个 16B lane 的 port 1 写数据路径、高位 lane 的写缓冲捕获，以及
部分行/lane 的 data/mask 写入。分类为 **SBD-WRITE-01/07/08 的情形缺失**，不是新的
微架构功能点。

补例 `test_exhaustive_cell_and_port_sweep`：16 行 × 4 lane × 16 字节逐字节写，每个位置
分别通过 port 0 和 port 1 写互补数据，每行结束后做完整 mask/known-data 检查，再逐行清理。

结果：过程行未覆盖 1778 → 0，DUT 行 79.1% → 100%，toggle 78.4% → 94.1%。

### 02 → 04

toggle 剩余方向主要是 `line_write_buffer_wline_*` 与 lane offset 高位。分类为
**SBD-WRITE-02/03 的情形缺失**。补例：

- `test_wline_both_ports_all_lines`：16 行 × 两个端口 × wline/普通写；
- `test_vword_offset_selects_low_two_bits_only`：高位 2..43 逐位别名；
- `test_data_bit_saturation`：数据位 0/1/0 饱和。

结果：toggle 94.1% → **100%**，branch 2115/2116（唯一剩余是时间零 `initial` 的 else）。

## 2. Sbuffer 顶层（单 DUT，内部真实 SbufferData）

| 运行 | 构建 | 用例 | 功能覆盖 | DUT LCOV 行 | toggle | branch |
|---|---|---|---:|---:|---:|---:|
| `sbuffer-top-initial-01` | 历史 `--vpi` 构建 | 11 PASS | 99.405% | 8915/13191（67.58%） | 49.8% | 64.6% |
| `sbuffer-top-initial-02` | 历史 `--vpi` 构建 | 15 PASS | 99.405% | 10939/13191（82.93%） | 73.8% | 97.8% |
| `sbuffer-top-clean-02` | 当前构建的早期基线：`mem_direct`、无 VPI、无 internal-cfg、seed=1 | 16 PASS | 100% | 12248/13191（92.85%） | 78.6% | 97.8% |
| **`sbuffer-top-contract-03`** | **当前合同基线**：同上，wline 只用零 payload、flush 期望由消费者合同定义 | **16 PASS** | **100%** | **12648/13191（95.88%）** | **82.0%** | **98.8%** |

`sbuffer-top-initial-01/02` 只作为早期功能缺口闭环的历史证据保留；`--vpi` 会改变生成
RTL 的初始化和覆盖率计数，且早期运行没有固定 Verilator seed。`clean-02` 是去掉 VPI、
固定 seed 后的早期基线，但它的 `wline` 用例使用了父块不可达的非零 payload，数值只作
历史对比。**当前结论以 `sbuffer-top-contract-03` 为准。**

### initial 阶段：功能缺口

首轮只覆盖单行入队、转发、超时写出、普通 flush、复位。未覆盖行/分支定位为：

| 缺口 | 分类 | 补例 |
|---|---|---|
| 16 槽的 port 1 写入、`waitInflightMask`、高槽 merge | SBT-ENQ-01/04 情形缺失 | `test_port1_same_tag_fills_all_slots`、`test_each_lane_merge_and_forward` |
| 16 槽的 replay/重试计数 | SBT-WRITE-02 情形缺失 | `test_replay_each_line_slot` |
| 16 槽整行写（cbo.zero 形态）、四 lane 转发 | SBT-WRITE-01/ENQ-01 情形缺失 | `test_wline_zero_all_lines` |

早期结果：SbufferDut.v 4273 → 4389/4673，SbufferData.sv 4642 → 6550/8518，
branch 64.6% → 97.8%，toggle 49.8% → 73.8%，功能覆盖 99.405%。

### clean-02 → contract-03：当前构建上的补例

在去掉 VPI、固定 seed 后重新建立基线 `clean-02`：16 例、功能覆盖 100%、DUT 行 92.85%。
剩余行集中在 `SbufferData.sv` 的高槽 lane 另一半字节路径和 `waitInflightMask`。

- 新增双端口 16 槽 × 4 lane 写入：每个 lane 由两个端口交替拥有低/高字节半区，并在
  enqueue 后通过三路转发检查整 lane mask。
- 结果：DUT 行 12248 → **12648/13191（95.88%）**，branch 97.8% → **98.8%**，
  toggle 78.6% → **82.0%**；功能覆盖保持 100%。

### 合同修正（不是覆盖率补例）

复核文档后，对两个可能产生假阳/假阴的测试点做了修正：

| 点 | 修正 | 依据 |
|---|---|---|
| `wline` payload | 顶层只用零 payload；16 个槽全写 | 父块只在 `cbo.zero` 产生 `wline`，数据恒 0；非零 payload 不可达 |
| CMO/fence 空信号 | 分别断言 `sbempty` 与 `flush.empty` | PR #6183 的两级空设计；Fence/Atomics/CBO FSM 的消费者接线 |
| CMO 是否等 SQ | 断言 MSHR 空后 `sbempty=1` 即使 `sqempty=0`；`flush.empty` 仍为 0 | CBO 在 SQ 头执行，自身条目使 `sqempty=0`；等它必死锁 |

这些修正不改变行/分支覆盖率分类，但把测试期望从“观察 RTL 后写死”改为“由规范与消费者
合同推出”。完整论证见 [flush 合同复核](flush-contract-review-20261024.md)。

## 3. 剩余缺口与归属（当前构建）

| 缺口 | 数量 | 分类 | 归属 |
|---|---:|---|---|
| `SbufferDut.v` `waitInflightMask` 高槽写路径 | 31 行、33 分支臂 | SBT-ENQ-04 情形缺失 | 需要同块 inflight 时 follower 插入全部 16 槽；容量替换与 ready 依赖限制构造 |
| `SbufferData.sv` 高槽 lane 的另一半字节端口路径 | 512 行 | SBT-ENQ-01 / SBT-WRITE-01 情形缺失 | 同 lane 两个端口的两半字节需要额外 merge 轮次；父块 ready 依赖使“单端口全掩码 merge”不能直接构造 |
| 时间零 `initial` 的 `if(reset)` 分支 | 1 分支 | 工具/时间零边界 | 周期 reset 已由 always 块覆盖 |
| toggle 残余 | 15431 点 | SBT-WRITE-01/ENQ-01 情形缺失 | 全 16 槽 0/1 饱和、地址高位随机、同 lane 双端口两半都写 |
| Picker harness 行 | 3/577 | 非 DUT | 生成的端口连线顶层，保留分母、不计入 DUT 闭合 |

这些缺口保留原始分母和源行，没有删除；它们不改变“已有功能点全部命中”的结论，也不
声称整体 MemBlock 验收。

## 4. 运行策略对结果的影响

- 当前构建 `mem_direct`，无 `--vpi`、无 `--internal`；测试只使用公开端口。
- `-w` 只编译 trace 能力；运行时 `conftest.py` 把 cwd 切到 `/tmp/opencode` 临时目录，
  默认 `$dumpfile` 不进入项目，`tools/run.py` 再清理并写 `trace-policy.json`。
- 不启用 `--keep-coverage-inputs`，不写 JSONL/逐拍信号或事务 dump。
- 顶层 `wline` 只用零 payload；`SbufferData` 的非零广播测试单列为模块能力，不作为
  父块行为证据。
- 固定 `+verilator+seed+1`；两次独立重复运行（`seed1-a/b`，已作为中间产物删除）在相同
  用例下得到完全相同的覆盖率计数，验证可复现性。
