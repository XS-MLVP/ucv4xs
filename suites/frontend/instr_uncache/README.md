# InstrUncache 验证工程

`InstrUncache` 是 `XSTile → XSCore → Frontend → FrontendInlined` 下、
`Frontend.sv` 单独实例化的 MMIO 取指模块。本工程只验证该模块及其真实内部层次，不把
ICache/IFU 的用例或 Frontend 的组合行为当作它的验收。

**结论边界：`InstrUncache`/DefaultConfig/`public-a0c2a26cb`。** 三个 DUT 的通过只
说明本模块单元合同，不是 Frontend 或芯片验收。

## 当前结论

seed 1 与 seed 2 各 **68 PASS / 0 UNCERTAIN / 0 FAIL / 0 ERROR**（68 nodeid，两轮
nodeid 完全一致）；功能点账本为硬件 **13/13 PASS**、环境 **4/4 PASS**（含
`INC-FLUSH-012` 结构证据）。**`ucv report` 为 `run_status=PASS`、
`hardware_verdict=INCOMPLETE`**（`FRONTEND-FLUSH-CONNECT` blocking/open，
`results/instr-uncache-seed1-incomplete-20261108`）、
`migration_acceptance=NOT_CERTIFIED`。单元可达行为通过，但 `Frontend` 把
`instrUncache.io.flush` 恒接 `false.B` 的设计决定没有 owner 签字，也没有 Frontend
级集成验证，因此不能写成硬件 PASS，也不能读成“flush 已验证”或芯片验收。

上述报告字段属于 2026-11-08 的冻结运行。工程根的 `verification_plan.json` 已删除；
新运行按实际用例与 `docs/bugs/` 问题快照报告，不读取旧计划残余。当前功能点、合同及
验收义务见[验证规格](docs/spec/verification/README.md)；
[FRONTEND-FLUSH-CONNECT](docs/bugs/open/FRONTEND-FLUSH-CONNECT.md) 已按 `kind=spec`
登记并保持当前基线 open，使采用问题记录验收的新运行在纯 PASS 时仍汇总为
`INCOMPLETE`。该事项沿用既有设计确认/集成缺口，不是新确认的 RTL 缺陷。

### R-FLUSH 收口（2026-11-08）

`Frontend.scala:266` 把 `instrUncache.io.flush` 恒接 `false.B`，唯一实例在
`Frontend.scala:125`；`EnableSimFrontend` 默认 false，`SimFrontendInlinedImp` 也把
整个 `instrUncache.io` 接 0。生成的 `InstrUncache.sv`（24 端口）和
`InstrUncacheEntry.sv`（23 端口）都没有 `flush`/`needFlush`，`Frontend.sv` 的实例也
没有 flush 连接。因此：

- DefaultConfig 下 flush 恒为 0，取消路径不可达；`R-FLUSH` 登记为
  **out-of-domain / accepted-limited**，只描述结构事实，不声称验证 flush。
- 新增 `FRONTEND-FLUSH-CONNECT`（blocking/open，owner `frontend/design`），要求确认
  `false.B` 是永久意图并入合同，或补上真实 flush 连接/删除端口；确认前整体保持
  **INCOMPLETE**。
- `INC-FLUSH-012` 是验证环境分区的结构检查点，验证裁剪与记录的 RTL 哈希一致；
  它不驱动 flush、不是行为验证，不计硬件通过率。

机器证据在 [`flush-closure.json`](docs/spec/verification/evidence/flush-closure.json)，
由 `tools/audit_flush_closure.py` 复核；证据变化时用例会失败并要求重新分类。该分类只
对 `public-a0c2a26cb` / DefaultConfig 成立。

## DUT 与层次

| 层 | DUT | top | 角色 |
|---|---|---|---|
| 1 | `instr_uncache_entry` | `InstrUncacheEntry` | 单 outstanding 四状态 MMIO 取指状态机，8B Get、4B 窗口、resend、needResend、WFI |
| 1 | `instr_uncache_resp_arbiter` | `Arbiter1_InstrUncacheResp` | `nMmioEntry=1` 时 Chisel `Arbiter` 退化成的 1:1 响应线 |
| 2 | `instr_uncache` | `InstrUncache` | 真实 Entry + 真实 Arbiter，外加 TL A/D、fromIfu/toIfu、wfi |

顶层 DUT 保留生成的真实 Entry/Arbiter RTL；Python 参考模型只提供期望值。
`Arbiter1_InstrUncacheResp` 不是独立 Scala 类名，而是
`new Arbiter(new InstrUncacheResp, nMmioEntry)` 在 `nMmioEntry=1` 后的生成模块名。

## 关键结构事实

- 生成闭包没有 `io_flush`、`io_id`、`io_mmioGrant_ready`、`io_resp_ready`，也没有
  Entry 的 `needFlush` 寄存器。理由分别是 `Frontend.scala:266`、`nMmioEntry=1`、
  `InstrUncacheImp.scala:88`、`IfuUncacheUnit.scala:133`。绑定层把这些缺失记录为
  **已证明常量**（结构事实，不是行为验证）。
- A 通道只引出 `address` 与 `user_memPageType_NC`/`user_memBackType_MM`；opcode/size/
  source/mask 由 `edge.Get(fromSource=io.id, lgSize=3)` 与 8B 对齐固定。
- 顶层 A 地址 bit47 固定为 0（Scala `Cat` 只产生 47 位）；DefaultConfig 的合法物理
  地址上限为 `2^43`，合法激励不会触及该位（`R-ADDR47`）。
- 整芯片生成缓存下的三个 `.sv` 与本工程三个闭包逐字节一致；顶层 DUT 不是 Python
  模型替身。

## 文档入口

- [文档总览](docs/README.md)
- [设计规格](docs/spec/design/README.md)、[合同](docs/spec/design/contracts.md)、
  [功能点](docs/spec/design/functional-points.md)
- [验证规格](docs/spec/verification/README.md)、[验证报告](docs/spec/verification/reports/verification-report.md)
- [覆盖率闭环](docs/spec/verification/coverage/coverage-loop.md)、
  [覆盖摘要](docs/spec/verification/coverage/coverage-summary.md)
- [flush 结构证据](docs/spec/verification/evidence/flush-closure.json)、
  [缺陷与设计边界](docs/spec/verification/defects.md)、
  [退出标准与残余](docs/spec/verification/exit-criteria.md)
- [问题索引](docs/bugs/README.md)

## 运行

从仓库根目录执行：

```sh
.venv/bin/ucv doctor instr_uncache --require-unified-baseline
.venv/bin/ucv prepare instr_uncache --require-unified-baseline --jobs 4
.venv/bin/ucv build instr_uncache --require-unified-baseline --jobs 4
.venv/bin/ucv run instr_uncache --workers 1 --seed 1 \
  --require-unified-baseline --output results/instr-uncache-seed1-flush-closure
.venv/bin/ucv run instr_uncache --workers 1 --seed 2 \
  --require-unified-baseline --output results/instr-uncache-seed2-flush-closure
.venv/bin/python suites/frontend/instr_uncache/tools/coverage_report.py \
  --manifest results/instr-uncache-seed1-flush-closure/instr_uncache/manifest.json \
  --output results/instr-uncache-seed1-flush-closure/coverage.json \
  --markdown results/instr-uncache-seed1-flush-closure/coverage.md
.venv/bin/python suites/frontend/instr_uncache/tools/audit_flush_closure.py
```

直接调试可运行 `.venv/bin/python -m pytest -q suites/frontend/instr_uncache/testbenches`；
这不替代 `ucv run` 的源码、种子、构建哈希和覆盖凭据。

## 覆盖摘要

两个 seed 的覆盖数字一致：

| DUT / 真实 RTL 文件 | line | branch | toggle | 说明 |
|---|---|---|---|---|
| `instr_uncache_entry` / `InstrUncacheEntryDut.v` | 37/37 (100%) | 13/14 (92.86%) | 628/664 (94.58%) | 唯一未覆盖臂是初始化块 `if (reset)` else（`R-COV-INIT`） |
| `instr_uncache_resp_arbiter` / `InstrUncacheRespArbiterDut.v` | 0/0 N/A | 0/0 N/A | 144/144 (100%) | 纯组合 assign，无 line/branch 插桩 |
| `instr_uncache` / 顶层结构 + 真实 Entry + Arbiter | 37/37 (100%) | 13/14 (92.86%) | 1165/1230 (94.72%) | 行覆盖只统计被插桩的 Entry 子模块；顶层结构模块无 line 点 |

未覆盖 toggle 位全部是地址 43..47 位、8B 对齐低 3 位和 2B 对齐 bit0，分别由合法
物理地址上限与对齐常量解释；未用非法高位或非对齐激励追求数字。详见
[覆盖率闭环](docs/spec/verification/coverage/coverage-loop.md)。

## 目录

工程使用 workspace schema2；DUT 实现与 shared 组件同用 env、transactions、model、
checker、coverage、tests 六职责。

- `testbenches/instr_uncache_entry/`、`testbenches/instr_uncache_resp_arbiter/`、
  `testbenches/instr_uncache/`：每个 DUT 的独立合同模型、checker、ports、agent 与
  tests；Entry 的四状态取指/窗口/resend/WFI、Arbiter 的 1:1 映射、顶层 Entry 组合与
  source 过滤分别归所属 DUT。输入由框架 `SyncSingleCycleDriver` 槽驱动，采样由
  `SamplingMonitor` 的 DriveStable/RisingEdge 双相完成。
- `testbenches/shared/env/drivers/slot.py`、`testbenches/shared/env/monitors/cycle.py`、
  `testbenches/shared/env/harness.py`：本工程跨 DUT 共享的槽、采样与 Picker 加载机制，
  不复制 IFU 的私有实现，也不建 `common/` 外壳。
- `testbenches/shared/env/fixtures.py` 提供跨 DUT 的 fixture 生命周期；各 DUT 的
  fixture 归其 `tests/fixtures.py`。`testbenches/shared/env/pytest_plugins/feature_report.py`
  汇总功能点标记；`testbenches/shared/tests/model_parameters.py` 是跨 DUT 模型再导出
  面，不参与运行时。
- `testbenches/<testbench>/tests/`：按功能点组织的定向用例；
  `testbenches/instr_uncache/tests/framework/` 是绑定、checker 区分力和非法激励自检
  （`selftest`，不计硬件功能 credit）。
- `conftest.py`：唯一的 pytest 根 fixture/插件注册表。
- `tools/coverage_report.py`、`tools/audit_flush_closure.py`：覆盖与 flush 结构证据
  工具。

## 结果与剩余范围

- 三个 DUT 均 `BUILT + SMOKE PASS`；完整 RTL、DUT 产物哈希见
  [验证报告](docs/spec/verification/reports/verification-report.md)。
- 定向覆盖：请求/对齐/4B 抽取/跨 8B resend/跨页 needResend/异常/WFI/单 outstanding/
  reset/响应丢失/D source 过滤；随机回归在 seed 1 和 seed 2 下各自 320 拍 Entry、
  320 拍顶层、400 个 Arbiter 向量，逐拍与合同模型比较。
- `flush` 取消路径在 DefaultConfig 下不可达；`R-FLUSH` 为 out-of-domain /
  accepted-limited，flush 行为仍未验证。`R-READY-PRUNED`、`R-A-CONST`、`R-DATA-X`、
  `R-ADDR47`、`R-SRC-OUT-OF-RANGE`、`R-COV-INIT`、`R-COV-TOOL`、`R-COV-TOGGLE`
  为非阻塞边界。
- 剩余范围：flush 期间/迟响应的取消语义、Frontend 级 flush/redirect 交互、TL 反压、
  真实 L2 行为、其他配置下的 `nMmioEntry`、Frontend/芯片验收。这些都不由本工程证明。
