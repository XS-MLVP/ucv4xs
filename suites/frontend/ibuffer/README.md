# IBuffer / VTypeGen 验证工程

`IBuffer` 是 `XSTile → XSCore → Frontend` 下的取指缓冲队列；它在 `Frontend.sv` 中
实例化 `VTypeGen` 作为唯一子模块，负责把队列/旁路路径上的指令转换为带
`vtype/specvtype` 的解码条目。本工程验证该模块及其真实子模块，不把 Frontend/后端对
vtype 的消费当作本层验收。

**结论边界：`IBuffer` / `VTypeGen`、DefaultConfig、`public-a0c2a26cb`。** 通过只说明
这两个 DUT 的单元合同；不是 Frontend、FTQ、ICache 或芯片验收。

## DUT 与层次

| 层 | DUT | top | 角色 |
|---|---|---|---|
| 叶 | `vtype_gen` | `VTypeGen` | 8 个 decode lane 的 vtype 生成、spec/arch 双状态、walk/commit 输入 |
| 顶层 | `ibuffer` | `IBuffer` | 48 槽队列、36-lane IFU 入队、8 lane 输出窗口、旁路、flush、前端异常；闭包保留真实 `VTypeGen` RTL |

顶层 DUT **不是 Python 模型替身**：`ucv prepare` 的闭包包含 `IBuffer.sv`、
`VTypeGen.sv`、`VSetFuncUnit.sv`，
`testbenches/ibuffer/tests/framework/test_binding_contract.py::test_ibuffer_closure_retains_the_real_vtype_gen`
从构建收据核对这一点。参考模型只提供期望值。

## 关键结构事实

- DefaultConfig：`VLEN=128`、`ELEN=64`、`IBuffer Size=48`、`NumWriteBank=4`、
  `NumReadBank=8`、`EnqueueWidth=36`、`DecodeWidth=8`。
- IFU fetch block 为 64 B/32 个指令槽；`valid/enqEnable` 的 36 lane 中只有 0..31
  可能有效，32..35 是写 bank 对齐 padding。
- 队列按 4 个写 bank 预对齐；输出窗口 8 项头部连续，stall reason 和 9 个
  `io_perf_*` 计数器由寄存器驱动。
- `IBuffer` 只导出 `walkToArchVType/walkVType/vsetvlVType/commitVType` 等后端 vtype
  输入；`VTypeBuffer`/`VtypeModule` 由 `Rob/NewCSR` 实例化，不在本工程闭包。

更完整的设计合同与未确认边界见[设计规格](docs/spec/design/README.md)和
[合同](docs/spec/design/contracts.md)。

## 当前结果

在 `public-a0c2a26cb` / DefaultConfig 上：

- `ucv prepare/build ibuffer --require-unified-baseline`：两个 DUT 均
  `BUILT + SMOKE PASS`。
- seed 1 与 seed 2 完整集合均 **83 PASS / 0 FAIL / 0 ERROR / 0 XFAIL / 0 XPASS /
  0 SKIP / 0 UNCERTAIN**（83 个 nodeid，两轮 nodeid 与 collection SHA 一致）。
  功能点账本 **23/23 PASS**（硬件 19 + 环境 4）。
- 结果目录：`results/ibuffer-seed1-final5`、`results/ibuffer-seed2-final5`。
- 覆盖（seed 1；seed 2 基本一致）：`vtype_gen` line 163/163、branch 104/106、
  toggle 1226/1596；`ibuffer` 闭包 line 4177/4209、branch 666/726、
  toggle 18524/20252。未覆盖项全部归因，见
  [覆盖率闭环](docs/spec/verification/coverage/coverage-loop.md)。
- 根门禁：`pytest -q tests` 272 PASS；布局/技能/资产审计通过；严格事务边界仍因其他
  工程的既有债务 exit 1（本工程 0 pin/signal/owner 访问）。
- `migration_acceptance=NOT_CERTIFIED` 表示本层不是 Frontend/芯片验收，不是存在未解释
  失败。

## 文档入口

- [文档总览](docs/README.md)
- [设计规格](docs/spec/design/README.md)、[合同](docs/spec/design/contracts.md)、
  [功能点](docs/spec/design/functional-points.md)
- [验证规格](docs/spec/verification/README.md)、[验证报告](docs/spec/verification/reports/verification-report.md)
- [覆盖率闭环](docs/spec/verification/coverage/coverage-loop.md)、
  [覆盖摘要](docs/spec/verification/coverage/coverage-summary.md)
- [缺陷与设计边界观察](docs/spec/verification/defects.md)、
  [退出标准与残余](docs/spec/verification/exit-criteria.md)
- [问题索引](docs/bugs/README.md)

## 运行

```sh
.venv/bin/ucv doctor ibuffer --require-unified-baseline
.venv/bin/ucv prepare ibuffer --require-unified-baseline --jobs 4
.venv/bin/ucv build ibuffer --require-unified-baseline --jobs 4
.venv/bin/ucv run ibuffer --workers 1 --seed 1 \
  --require-unified-baseline --output results/ibuffer-seed1-final5
.venv/bin/ucv run ibuffer --workers 1 --seed 2 \
  --require-unified-baseline --output results/ibuffer-seed2-final5
.venv/bin/python suites/frontend/ibuffer/tools/coverage_report.py \
  --manifest results/ibuffer-seed1-final5/ibuffer/manifest.json \
  --output results/ibuffer-seed1-final5/coverage.json \
  --markdown results/ibuffer-seed1-final5/coverage.md
```

直接调试可运行 `.venv/bin/python -m pytest -q suites/frontend/ibuffer/testbenches`；这不替代
`ucv run` 的源码、种子、构建哈希和覆盖凭据。

## 目录

- `testbenches/vtype_gen/model.py`：按 RISC-V V 规范与接口合同实现的 vtype oracle。
- `testbenches/ibuffer/model.py`：48 槽队列、bank 指针、旁路、输出窗口、异常、flush、stall
  reason 的独立模型；内部包含 `VTypeGenModel`。
- `testbenches/vtype_gen/`、`testbenches/ibuffer/`：每个 DUT 的 `ports/agent/checker/types`；
  输入由 `SyncSingleCycleDriver` 槽驱动，`SamplingMonitor(DriveStable/RisingEdge)` 双相采样。
- `testbenches/shared/env/`：两个 DUT 共用的 Picker 加载/周期约定、driver、monitor、
  fixture 机制和 feature 插件；DUT 专属 fixture 绑定在各 DUT `tests/fixtures.py`。
- `testbenches/vtype_gen/tests/`、`testbenches/ibuffer/tests/`：功能点定向与双 seed 随机用例；
  `testbenches/ibuffer/tests/framework/` 是绑定、真实子模块证据、checker 区分力、非法激励和
  oracle 自检（`selftest`，不计硬件功能 credit）。
- `conftest.py`：唯一的 pytest 根 plugin 注册表。
- `tools/coverage_report.py`：逐 DUT、逐真实 RTL 文件输出 line/branch/toggle。

目录遵循 workspace schema 2：`workspace.json` 的 `duts.<name>.testbench` 登记实现，
`ucv.json` 收集根和 `pytest.ini` 的 `testpaths` 均为 `testbenches`；两个 DUT 各自独立，
不共用一个参数化实现。

## 残余与剩余范围

无 blocking 残余；`R-FRONTEND`、`R-CONFIG`、`R-LANE-PAD`、`R-OBS-PERF` 等为非阻塞
边界，完整清单见[退出标准](docs/spec/verification/exit-criteria.md)。

未证明：Frontend redirect/FTQ/ICache 交互、`satpFlushFirstFetchFault` 的消费者、
真实 CSR vtype 写入、其他 VLEN/ELEN 或 IBuffer 尺寸配置、芯片验收。
