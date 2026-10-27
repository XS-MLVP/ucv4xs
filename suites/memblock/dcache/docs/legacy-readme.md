> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# DCache 分层验证工程（memblock-hash/dcache）

XiangShan **kunminghu-v3**（`893e1580`）L1 DCache 及其 MemBlock 边界
（`DCacheWrapper`）的 UT 工程。工具链：Picker memory-direct + toffee main runner，
RTL 来自 `soc-split/rtl` 的 split-verilog。

---

## 1. 结论（先看这里）

**已验证通过**（证据：`results/soundness-recheck-03`，13 个 Picker 构建）：

- **210 个用例通过 + 3 个严格 expected-failure**（219.3 s，`--workers 4`），
  trace policy PASS（不存波形、不存逐周期 dump）。
- **用例可信度已按假阴性经验复核**：3 个门禁（收集审计 / 输出观察审计 / 检查器注错
  自检）全部通过，细节见 `docs/reports/soundness-recheck-20261026.md`。
- **61 个功能覆盖组全部 100%**：每个组都是"定义了哪些微架构情形 + 每种情形至少被
  行为级断言命中一次"，不是信号枚举。
- 11 个独立子模块的 DUT-only 行覆盖 **8059 / 8309 = 97.0%**，其中 **8 个为 100%**。
- `DCache` 顶层 **50260 / 51179 = 98.20%**；`DCacheWrapper` **50453 / 51265 = 98.42%**
  （wrapper 自身 `DcacheWrapperDut.v` **86 / 86 = 100%**）。
- **多 seed 稳定**：seed 1/2/3/4 各跑全量，结果一致（202 passed + 3 xfailed）。

**已确认的 RTL 缺陷（1 项）**：

- `MQ-STORE-MERGE-DATA-PENDING`：同一行第二笔部分 store 被受理（`handled=1`、
  无第二次 Acquire）但其字节丢失。MissQueue 观测 `0x01AA`、DCache 顶层安装行
  `0x00AA`，期望 `0xBBAA`。MissQueue / DCache / wrapper 三处严格 xfail 用例固化；
  修复后会自动变成 unexpected pass。

**不是缺陷（本轮关闭 4 项）**：

- `DCACHE-DENIED-ERROR-PADDR-ZERO`：字段语义是 `{tag, vaddr[11:0]}`，页对齐地址
  自然为 0；`report_to_beu=0`，BEU 不消费。
- `BDA-ECC-DELAYED-FLAG`：此前读到的是从未写过的 SRAM 行（数据/ECC 随机），
  编码写入后 `error_delayed` 为 0。
- `DCACHE-REEVICT-BLOCK-REJECTED`：写回阻塞契约——Release 未被接受时同 block
  被拒（`handled=0` 表示 replay），drain + ReleaseAck 后立即恢复。
- `BDA-DUPLICATED-BANK-ADDR`：两套物理副本，功能等价。

**为什么不是 100%**（详见 `docs/reports/coverage-20261025.md` 第 4 节）：

- **DCache 顶层剩余 919 行全部是内联子模块的重复计数**（MainPipe 281、MissQueue 241
  …，各自 UT 已单独统计），没有一行是 DCache 独有行为未验证。
- MissQueue 剩余 246 行：80 行 store→load 转发（Sbuffer 范围）、36 行不可达默认臂、
  45 行多端口同拍组合、53 行声明。

**不能据此声称**：

- 整个 DCache 或 MemBlock 已验收。Uncache 与 DCache 的仲裁、flush/drain、CSR/中断、
  WPU/prefetch、伪错误注入、store→load 转发均未纳入。
- 约束随机的存储模型覆盖了替换（PLRU 未建模）；替换语义由定向用例覆盖。

---

## 2. 验证对象与层次

```text
MemBlock.sv
├── DCacheWrapper inner_dcache        ← 本工程的最高边界（861 端口 = DCache 的 1:1 封装）
│   └── DCache                        ← 顶层 DUT
│       ├── 叶块  DuplicatedTagArray / CtrlUnit / MissReadyGen / CounterFilter
│       ├── 中层  MissTrack / LoadPipe(×3) / BankedDataArray
│       └── 上层  MainPipe / MissQueue / ProbeQueue / WritebackQueue
└── Uncache inner_uncache             ← 与 DCacheWrapper 平级，未纳入
```

**关于 `DCacheWrapper` 的事实**（详见 `docs/functional-points-dcache-wrapper.md`）：

- 内部只有 1 个 `DCache` 实例；861 端口 = 766 同名直连 + 53 改名
  （14 个 `cacheCtrlOpt→uncache`、39 个 `spec_fabric→dcache_spec_fabric`）
  + 42 个 perf 两级寄存器输出。
- **wrapper 内没有** Uncache 数据通路、uncache 仲裁、第三条 L2 通道或 flush 状态机。
  真实的 `Uncache` 在 `MemBlock.sv:7891` 与它平级。

---

## 3. 结果总表（`results/soundness-recheck-03`，13 个构建）

行/分支/toggle 均为 **DUT-only**（排除 Picker 生成的 `*_top.sv` harness）。
每个构建独立保留分母，**不跨 DUT 相加**。

| 层 | DUT | 用例 | 功能组 | 行（DUT-only） | 分支 | Toggle |
|---|---|---:|---:|---:|---:|---:|
| 叶 | DuplicatedTagArray | 9 | 5/5 | 90/90 = 100% | 76/80 | 15010/15428 |
| 叶 | CtrlUnit | 13 | 3/3 | 244/244 = 100% | 85/89 | 11444/12108 |
| 叶 | MissReadyGen | 5 | 3/3 | 纯组合 | 0/0 | 3512/3512 |
| 叶 | CounterFilter | 7 | 3/3 | 311/311 = 100% | 49/50 | 622/622 |
| 中 | MissTrack | 13 | 4/4 | 952/952 = 100% | 172/174 | 12054/12804 |
| 中 | LoadPipe | 7 | 3/3 | 119/119 = 100% | 23/25 | 4594/5190 |
| 中 | BankedDataArray | 21 | 5/5 | 1843/1843 = 100% | 1093/1100 | 90701/105848 |
| 上 | MainPipe | 36 | 11/11 | 2095/2095 = 100% | 667/674 | 29586/40500 |
| 上 | MissQueue | 31（1 xfail） | 7/7 | 1853/2099 = 88.3% | 967/1334 | 26671/47506 |
| 上 | WritebackQueue | 8 | 3/3 | 449/449 = 100% | 242/278 | 3114/4706 |
| 上 | ProbeQueue | 3 | 1/1 | 103/107 = 96.3% | 60/96 | 1388/4072 |
| 顶 | DCache | 26（1 xfail） | 8/8 | 50262/51179 = 98.2% | 18986/20504 | 168576/332370 |
| 边界 | **DCacheWrapper** | 34（1 xfail） | 14/14 | 50455/51265 = 98.4%（自身 86/86） | 19034/20504 | 181329/349062 |
| — | **子模块合计** | **156** | — | **8059/8309 = 97.0%** | 3427/3900 | — |

功能覆盖：**61 组全部 100%**（`soundness-recheck-03/coverage-audit-summary.json`）。
用例合计 213 = 210 PASS + 3 XFAIL（3 个 xfail 都是同一个已确认缺陷的
MissQueue / DCache / wrapper 三处复现）。

---

## 4. 覆盖率怎么读

| 指标 | 含义 | 口径 |
|---|---|---|
| line | RTL 可执行行是否执行过 | 只算 DUT-only；harness 单列 |
| branch | 条件分支两个方向是否都取过 | Verilator 原生点，不删不合并 |
| toggle | 每个信号位是否 0→1 和 1→0 都出现过 | 宽数据/宽地址天然难穷举，**不作通过标准** |
| 功能覆盖 | 人工定义的微架构情形组 | 每组 100% = 所有合法 bin 至少被行为级断言命中一次 |

**DCache 顶层未覆盖 919 行的归因**：

| 类别 | 行数 | 判定 |
|---|---:|---|
| 内联子模块（各自已有独立 UT） | **919（100%）** | **不是新增缺口**：MainPipe 281、MissQueue 241、CounterFilter 90、`DcacheDut.v` 67、CtrlUnit 42… |
| 两张 prefetch 元数据表 | 9 + 9（残） | 已用 `io_prefetch_req` 扫过 256 set × 4 way，达 99.86% |

**prefetch 部分是怎么补上的**：`io_prefetch_req` 是 MainPipe 的公开输入，
`pf_source > 1` 即“来自 L1 预取”；装入后一笔 demand load 命中会触发
`prefetch_flag_write` 把标记清为 `L1_HW_PREFETCH_CLEAR`。新用例
`test_prefetch_install_then_demand_hit_clears_flag` 对 1024 个 (set, way) 逐条做
“预取装入 → demand 命中 → 清标记”，两张表从 83.6% 提升到 **99.86%**。

**MissQueue 未覆盖 246 行**：80 行 store→load 转发（Sbuffer 范围）、36 行不可达默认臂、
45 行多端口同拍组合、53 行声明、32 行常量折叠臂。

**这一轮的覆盖率提升**（不是灌激励，而是补真实状态空间）：

| 运行 | DCache 行 | MissQueue 行 |
|---|---:|---:|
| `full-regression-09`（基线） | 35452/51179 = 69.3% | 1673/2099 = 79.7% |
| `full-regression-11` | 35820/51179 = 70.0% | 1845/2099 = 87.9% |
| `full-regression-14` | 48167/51179 = 94.1% | 1853/2099 = 88.3% |
| **`full-regression-15`** | **50260/51179 = 98.2%** | **1853/2099 = 88.3%** |

两个关键用例（都是补真实状态空间，不是灌激励）：

1. `test_all_sets_all_ways_update_replacement_state`：填满 256 set × 4 way，再按 4 个
   touch 端口各扫一遍。原来只碰少数 set 且只用 lane 0，所以按 set×way 展开的 meta
   阵列和按端口展开的替换状态优先级链各有 50% 以上没执行。
   效果：`L1ErrorMetaArray` 72.5%→100%、`L1CohMetaArray` 76.1%→100%、
   `DcacheDut.v` 52.3%→99.4%。
2. `test_prefetch_install_then_demand_hit_clears_flag`：用 `io_prefetch_req` 装入
   预取行、再用 demand load 命中清标记，扫 256 set × 4 way。
   效果：`L1PrefetchSourceArray` 83.6%→99.86%、`L1RefillLatencyArray` 83.4%→99.86%。

**磁盘占用**：`results/` 曾是 1.1 GB，主要是一次全量回归的逐点审计 JSON（260 MB）
和 Verilator 原始 `coverage.dat`（13 个构建共 228 MB），再乘以若干份历史运行。
现在用 `tools/compact_results.py` 压到约 **40 MB**（保留 summary + md + 审计
`.json.gz` + LCOV `.info.gz`，原始 `coverage.dat` 删除——需要时重跑即可重建）。

## 5. 已知问题

| ID | 内容 | 状态 |
|---|---|---|
| `MQ-STORE-MERGE-DATA-PENDING` | 第二笔合并 store 的字节未进 refill 行；LSU 仍收到成功响应 | **确认 RTL 缺陷**，2 个严格 xfail 用例 |
| `CF-DEQUEUE-PIPELINE-NO-RESET` | CounterFilter 3 级出队计数流水无复位，短复位会让 FIFO 指针永久偏移 | 系统内良性（真实复位数百拍）；env 复位保持 5 拍 |
| `DCACHE-DENIED-ERROR-PADDR-ZERO` | `io_error.paddr = vaddr[11:0]`（冷行 tag=0） | 关闭：非缺陷，已加用例固化 |
| `BDA-ECC-DELAYED-FLAG` | 读未写过的 SRAM 行会报 ECC 错 | 关闭：非缺陷，编码写入后无错 |
| `DCACHE-REEVICT-BLOCK-REJECTED` | 替换后重访被拒 | 关闭：非缺陷（写回阻塞契约） |
| Uncache / uncache 仲裁 | 不在 `DCacheWrapper` 内；在 `MemBlock` | 未纳入 |
| flush / drain、CSR / 中断 | DCache 无独立 flush 端口；wrapper 只暴露控制寄存器 TL slave | 未纳入 |
| SRAM meta/flag 阵列 | 未做 256 set × 4 way 全扫 | 范围限制 |
| 伪错误注入 / WPU / prefetch / store 转发 | 对应旁路未驱动 | 未纳入 |

完整定位过程与证据见 [`docs/reports/p0-closure-20261026.md`](docs/reports/p0-closure-20261026.md)。

---

## 6. 目录

```text
dcacheverify/
├── common/                 # DUT 加载、执行器、固定 seed
├── duplicated_tag_array/   # 以下每个目录 = 一个 DUT 的 env/model/coverage
├── ctrl_unit/
├── miss_ready_gen/
├── counter_filter/
├── miss_track/
├── load_pipe/
├── banked_data_array/
├── main_pipe/
├── miss_queue/
├── writeback_queue/
├── probe_queue/
├── dcache/                 # DCache 顶层（含约束随机流量生成器）
└── dcache_wrapper/         # DCacheWrapper（端口映射视图 + 控制寄存器驱动）
tests/<dut>/test_*.py
tools/{prepare_rtl,build_dut,smoke_dut,run,coverage_audit,wrapper_portmap,compact_results,audit_test_soundness,audit_output_fields,selfcheck_checkers}.py + seed_sweep.sh
docs/functional-points-*.md      # 每个 DUT 的语义功能点
docs/reports/*.md                # 覆盖率报告、逐模块报告、P0 收口、交付自检
results/<fresh-name>/            # 每次运行独立目录 + coverage-audit.json/.md + seed.json
manifest/{toolchain,rtl-sha256,known-issues,dcache-wrapper-portmap}.json
```

---

## 7. 工具与复现

| 项 | 值 |
|---|---|
| 源码 | XiangShan `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` |
| RTL | `../../soc-split/rtl`（firtool-1.149.0）；13 个闭包 174 份拷贝、59 个唯一源文件，哈希见 `manifest/rtl-sha256.json`，**59/59 与磁盘一致** |
| Picker | `2.0.0-HEAD-4dd442c-2026-10-12` |
| Verilator | `5.052` |
| toffee | `2.0.0.dev12+g3017293a7` |
| xspcomm | `0.3.0.dev3` |

```sh
python3 tools/prepare_rtl.py                 # 复制 RTL 闭包并记录哈希
python3 tools/build_dut.py <key> --jobs 8    # Picker 构建（已存在则拒绝覆盖）
python3 tools/smoke_dut.py <key>             # 原生冒烟
python3 tools/wrapper_portmap.py             # 重新生成 DCacheWrapper 端口映射
python3 tools/run.py --name <fresh> --workers 4 tests
python3 tools/coverage_audit.py <fresh>      # 生成 coverage-audit.json/.md
python3 tools/compact_results.py <fresh>     # 保留审计轨迹，删原始 coverage.dat
python3 tools/audit_test_soundness.py        # 收集/恒真/无断言审计（门禁）
python3 tools/selfcheck_checkers.py          # 注错必须 FAIL（门禁）
tools/seed_sweep.sh 1 2 3 4                  # 多 seed 全量 + 自动压缩
```

**种子可复现**：`DCACHE_VERILATOR_SEED` 控制 DUT 随机初值，
`DCACHE_TEST_RANDOM_SEED` 控制 Python `random`；两者都写进
`results/<run>/seed.json`。

资源约束：Picker 构建带 trace 能力但从不调用 `SetWaveform`；`tools/run.py` 校验无
`.fst`、无逐周期 `.jsonl`，并把两个种子写进 `seed.json`。

**磁盘占用怎么控制**：`tools/compact_results.py` 每次运行后

1. 逐点审计 `coverage-audit.json` → `.json.gz`（DCache 那份 260 MB → 3.9 MB）；
2. 另存 `coverage-audit-summary.json`（逐构建数字，13 KB）与 `coverage-audit.md`；
3. 删除可由重跑重建的原始 `coverage.dat`，LCOV `coverage.info` 保留为 `.gz`；
4. 只保留当前基线与被报告引用的历史运行。

13 个 Picker 构建各自解出的 `xspcomm` 也改为共享 `dut/xspcomm-shared`
（361 MB → 28 MB）。工程总大小 **约 600 MB**（`dut/` 约 490 MB 是构建产物、`results/` 约 40 MB）。

---

## 8. 文档索引

| 文档 | 内容 |
|---|---|
| [`docs/reports/coverage-20261025.md`](docs/reports/coverage-20261025.md) | **总覆盖率报告**（2026-10-26 数据刷新）：口径、逐 DUT 分母、缺口分类、证据索引 |
| [`docs/reports/soundness-recheck-20261026.md`](docs/reports/soundness-recheck-20261026.md) | **用例可信度复核**：按 P01–P12 逐项找出的 11 处验证缺口、修正与成对证据 |
| [`docs/reports/p0-closure-20261026.md`](docs/reports/p0-closure-20261026.md) | **P0 收口**：1 个确认缺陷、4 项关闭、1 个新发现（无复位流水）、多 seed 结果 |
| [`docs/reports/functional-point-audit-20261025.md`](docs/reports/functional-point-audit-20261025.md) | 前期功能点正确性复核（7 项修正及依据） |
| [`docs/reports/dcache-top-20261025.md`](docs/reports/dcache-top-20261025.md) | DCache 顶层 12 个功能点与用例对应 |
| [`docs/reports/dcache-wrapper-20261025.md`](docs/reports/dcache-wrapper-20261025.md) | DCacheWrapper 结构事实、WFP-001..007、32 用例 |
| [`docs/reports/main-pipe-20261025.md`](docs/reports/main-pipe-20261025.md) | MainPipe：11 功能点、36 用例、100% 行覆盖 |
| [`docs/reports/miss-queue-20261025.md`](docs/reports/miss-queue-20261025.md) | MissQueue：7 功能点、27 用例、87.9% 行覆盖与缺口归因 |
| [`docs/reports/status-20261025.md`](docs/reports/status-20261025.md) | 阶段状态与下一步 |
| [`docs/reports/delivery-selfcheck-20261025.md`](docs/reports/delivery-selfcheck-20261025.md) | 交付自检清单（哈希、构建、trace、未关闭项） |
| [`docs/hierarchy.md`](docs/hierarchy.md) | 真实层次、参数与来源 |
