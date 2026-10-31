> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# Sbuffer 验证工程

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


XiangShan `kunminghu-v3 @ 893e1580` 的 Sbuffer 分层 UT。先验证 `SbufferData` 的字节级
存储/掩码语义，再验证 `Sbuffer` 顶层的入队、写出、排空和转发；每个模块先写人类可读的
微架构功能点，再开发用例，运行后分析 RTL 行/toggle/branch 覆盖率并逐项定位缺口。

## 1. 范围与基线

| 项 | 值 |
|---|---|
| 源码 | `../../XiangShan/`，提交 `893e1580b705d81f113c30c7a05734e09a08050e` |
| RTL | `../../soc-split/rtl/Sbuffer.sv`、`SbufferData.sv` 原样副本 |
| DUT | `SbufferData`（子块）→ `Sbuffer`（顶层，内部保留真实 SbufferData） |
| 工具 | Picker `2.0.0-HEAD-4dd442c`、Verilator `5.052`、toffee `2.0.0.dev12+g3017293a7` |
| 运行入口 | toffee main 分支的 `toffee run`（原 xreactor runner） |

RTL 哈希：`manifest/sbuffer-rtl.sha256`。基线/参数/层次：`manifest/baseline.json`。
工具锁：`manifest/toolchain.json`。DUT 映射：`manifest/duts.json`。

## 2. DUT 构建策略（按 toffee main 示例）

Picker 只导出一份顶层 `Sbuffer` DUT；`SbufferData` 保留为真实子块，同时另有一份
子块独立 DUT 用于字节级 UT。

```sh
python3 tools/build_dut.py
# picker export Sbuffer.sv --fs filelist.f --sname Sbuffer --tname SbufferDut \
#   --rw mem_direct -w memory-direct.fst -c \
#   --vflag='--no-coverage-expr --no-coverage-fsm' --lang python --autobuild true -j 8
```

- `--rw mem_direct`：memory-direct 访问模式。
- `-w memory-direct.fst`：编译 trace 能力，供显式诊断使用。
- `-c`：编译行/toggle/branch 覆盖率。
- **不启用 `--vpi`，不启用 `--internal`/internal-cfg**：DUT 没有任何内部信号访问面；
  测试只通过公开端口驱动和采样。
- 顶层 `wline` 只用零 payload（父块只对 `cbo.zero` 产生 wline）；非零 payload 仅作为
  `SbufferData` 模块能力验证，不计入父块行为证据。
- **运行时默认不产生波形**：不调用 `SetWaveform`；`conftest.py` 把整个 pytest 进程
  切到 `/tmp/opencode` 的临时 cwd，Picker 生成的默认 `$dumpfile` 只落在临时目录并删除。
- **不逐周期 dump 信号/事务**：不使用 `--keep-coverage-inputs`，不写 JSONL/逐拍 trace；
  只保留覆盖率数据库、功能覆盖 JSON、manifest 和审计报告。
- 不提供运行时波形开关；trace 只保留编译能力，正常运行从不打开。

固定 Verilator 种子 `+verilator+seed+1`，使 PLRU/寄存器随机初始化可复现；两次独立
运行得到完全相同的覆盖率计数。

## 3. 目录

```text
sbuffer/
├── README.md
├── conftest.py                 # DUT / env / coverage fixtures
├── pytest.ini
├── docs/
│   ├── functional-points-sbuffer-data.md
│   ├── functional-points-sbuffer.md
│   └── reports/
├── manifest/                   # baseline / toolchain / duts / RTL hashes / known issues
├── rtl/sbuffer_data/           # 原样 RTL + filelist
├── rtl/sbuffer/                # 原样 Sbuffer + SbufferData + filelist
├── dut/sbuffer_data/           # 子块 Picker DUT
├── dut/sbuffer/                # 顶层 Picker DUT（当前活动 DUT）
├── sbufferverify/
│   ├── common/                 # DUT 加载、固定 seed、Execution 辅助
│   ├── sbuffer_data/           # 独立字节模型、两拍写 env、功能覆盖
│   └── sbuffer/                # 行级模型、top env、功能覆盖
├── tests/sbuffer_data/
├── tests/sbuffer/
├── tools/                      # build_dut / run / coverage_audit / verify_delivery
└── results/
```

## 4. 运行

```sh
# 构建顶层 DUT（dut/sbuffer 已存在时拒绝覆盖，先审计旧包）
python3 tools/build_dut.py

# 顶层 16 例；输出到全新目录
python3 tools/run.py --name sbuffer-top-repro-01 --workers 1 tests/sbuffer

# 子块 15 例
python3 tools/run.py --name sbuffer-data-repro-01 --workers 1 tests/sbuffer_data

# 逐行/分支/toggle 审计
python3 tools/coverage_audit.py sbuffer-top-repro-01

# 交付自检
python3 tools/verify_delivery.py
```

`tools/run.py` 写 `trace-policy.json`，记录 trace 已编译、运行时波形关闭、无逐周期
dump；发现波形或 JSONL 时返回失败。

## 5. 当前证据

| 范围 | 运行 | 用例 | 功能覆盖 | DUT 行覆盖 | toggle | branch |
|---|---|---|---:|---:|---:|---:|
| SbufferData | `sbuffer-data-initial-04` | 15 PASS | 4 组 100% | **8518/8518（100%）** | **100%** | 2115/2116 |
| Sbuffer 顶层 | `sbuffer-top-contract-03` | 16 PASS | 8 组 100% | **12648/13191（95.88%）** | **82.0%** | **98.8%** |

Sbuffer 顶层分文件：

| 源文件 | 行命中/唯一行 | 过程语句未覆盖 |
|---|---:|---:|
| `SbufferDut.v` | 4642/4673（99.34%） | 31 |
| `SbufferData.sv` | 8006/8518（93.99%） | 512 |
| `SbufferDut_top.sv`（Picker harness，不计入 DUT） | 3/577 | 408 |

详细报告：

- [SbufferData UT](docs/reports/sbuffer-data-20261024.md)
- [Sbuffer 顶层 UT](docs/reports/sbuffer-top-20261024.md)
- [覆盖率闭环](docs/reports/coverage-loop-20261024.md)
- [flush/empty 合同复核](docs/reports/flush-contract-review-20261024.md)（CMO/fence 两级空语义；结论：不是缺陷）
- [已知缺口](manifest/known-issues.json)
- 交付自检：`results/delivery-audit.json`（`python3 tools/verify_delivery.py`，当前 PASS）

## 6. 状态边界

- 功能点与功能覆盖：两层均 100%；所有失败均修复，无 xfail/skip。
- flush/empty 语义已按 RISC-V CMO 规范、上游 PR #6183、Fence/Atomics/CBO FSM 接线复核：
  CMO 消费 `sbempty`，fence/atomics 消费 `flush.empty`；`flush.empty` 含 `sqempty`
  是正确设计，不是缺陷。
- SbufferData 独立 DUT：DUT 行 100%、toggle 100%、branch 2115/2116（唯一缺口是时间零
  `initial` 的 `if(reset)` else）。
- Sbuffer 顶层：DUT 行 95.88%、branch 98.8%；剩余 543 行已逐项分类为
  `waitInflightMask` 高槽同块写入（31 行）和 SbufferData 高槽 lane 的另一半字节端口
  路径（512 行），属于已有功能点 SBT-ENQ-01/04、SBT-WRITE-01 的情形缺失。
- 不声称整个 MemBlock 已验收；Sbuffer 通过不代表 DCache/SQ/LSQ 或全核通过。
- 所有结论绑定 RTL 哈希、DUT 构建、toffee/Verilator 版本、固定 seed 和结果目录。

## 7. 资源

- 正常运行不保留波形、逐拍信号或事务 dump；只保留 coverage.dat/info、功能覆盖 JSON、
  manifest、audit 和报告。
- 中间 run 的 `coverage.dat` 已用 zstd 压缩（约 15–17MiB → 约 0.25MiB），可由 `.dat.zst`
  解压恢复；最终 run 保留未压缩。
- 顶层 16 例回归约 21 秒；`results/` 约 72MiB，`dut/` 约 80MiB（已移除构建期
  `V*_coverage.dat` 临时文件）。
