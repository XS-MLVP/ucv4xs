# FTQ 验证工程

基于 Picker 与 toffee 验证香山 FTQ：

```text
Ftq
├── ResolveQueue   分支解析归并、重定向冲刷与 BPU 训练出队
└── CommitQueue    call/return 退休动作的保序队列
```

`EntryQueue`、`CfiQueue`、`MetaQueue`、`SpeculationQueue` 当前未被 `Ftq` 实例化，
不进入本工程 DUT 闭包。FTQ 自己维护的 entry/meta/pointer 状态由顶层用例验证。

当前原生加载器按 `ucv run --seed` 传入 Verilator seed；每次构造解析
`ucv.runtime.native_seed`，构造器正反对照见根 `tests/test_frontend_runtime_seed.py`。
此前仅登记 CLI seed 的历史结果不自动成为已复现的原生多 seed 证据。

## 当前结论

基线 `public-a0c2a26cb` / DefaultConfig / 单核；三个 DUT 已按统一基线
prepare/build，均为 `BUILT + SMOKE PASS`。

- 最新完整回归：**931 PASS / 2 XFAIL**（933 nodeid，seed 2、2 workers，
  `results/ftq-a0c2a26cb-closeout-seed2b-20261108`）；同源码 seed 1 同为 931/2，
  逐 nodeid 判定一致。0 FAIL、0 SKIP、0 ERROR。
- 两个 strict XFAIL 是 ResolveQueue 真实 slot7/slot0 容量缺陷，登记为
  [RQ-011](docs/bugs/open/resolve-queue-branch-overflow.md)；可达性追踪确认
  3 backend + 1 IFU 同索引和跨拍 9 条报告都是合法生产者序列，另以 `--runxfail`
  保留真实 FAIL 证据。未实施 RTL 修复。
- 相对旧基线的 RTL 变化只在 `Ftq` 顶层：新增 8 槽软件预取队列、3 个
  `softPrefetch` 输入和 `source` 输出；redirect PC 扩为 51 位。`ResolveQueue` /
  `CommitQueue` 的 Scala 与生成 RTL 逐字节不变。顶层固定 ABI 为 **439 个
  非 clock 输入、470 个输出**。
- 覆盖（seed 2）：`resolve_queue` 行 100.0% / 分支 99.9% / toggle 89.2%；
  `commit_queue` 100.0% / 99.8% / 100.0%；`ftq` 行 100.0% / 分支 99.8% /
  toggle 84.3%。剩余 6 个分支计数来自 4 个 distinct Verilator 初始化 reset else。
- 2026-10-30 的 109/2、51996/51996 等检查点属于旧 `public-893e1580b`，保留原义，
  不与本轮拼接。2026-11-02 的 905/2、410/2 同样属于旧基线，证据见
  [组合机器证据](../../../docs/history/transaction-goal-ftq-top-frontend-20261102.json)、
  [整槽检查点](../../../docs/history/transaction-goal-ftq-top-slots-20261102.json) 与
  [ResolveQueue 机器证据](../../../docs/history/transaction-goal-ftq-resolve-transactions-20261102.json)。

本工程结果只对锁定基线、DefaultConfig RTL 和实际运行源码/原生包成立；不是整机取指
或 BPU 训练验收。

## 文档入口

- [文档总览](docs/README.md)
- [设计规格](docs/spec/design/README.md)：层次、配置、接口、合法输入与未确认设计
- [功能点](docs/spec/design/functional-points.md)、[责任边界](docs/spec/design/requirements-boundary.md)、
  [行为等价类](docs/spec/design/equivalence-classes.md)
- [验证规格](docs/spec/verification/README.md)：方法、判定、完成条件
- [新基线适配记录](docs/spec/verification/reports/baseline-adaptation-a0c2a26cb.md)
- [事务迁移复核](docs/spec/verification/transaction-adaptation.md)
- [功能点追溯](docs/spec/verification/traceability.md)、[残余与退出状态](docs/spec/verification/residuals.md)
- [历史覆盖率闭环（893e1580b）](docs/spec/verification/coverage/coverage-analysis-20261030.md)、
  [历史运行证据（893e1580b）](docs/spec/verification/evidence/evidence-20261030.md)
- [问题索引](docs/bugs/README.md)

## 验证包结构

环境按 agent / driver / monitor / checker / transaction 分层，测试只持有事务：

```text
suites/frontend/ftq/      import suites.frontend.ftq（workspace schema 2）
├── __init__.py           ROOT：工程资源根，不构造 DUT
├── conftest.py           唯一 fixture / pytest 插件注册入口
├── testbenches/shared/env/harness.py        DUT 装载、时钟/执行上下文、引脚所有权与生命周期
├── testbenches/shared/env/ports.py         跨 DUT 的引脚所有权视图；具体映射仍在各 DUT bundle
├── testbenches/shared/env/fixtures.py      DUT + Execution + agent 的 pytest fixture
├── testbenches/shared/env/monitors/cycle.py SDK 双阶段采样的不可变 snapshot 及 decoder/cache view
├── testbenches/ftq/env/harness.py          Ftq 专属指针安全网（共享 harness 子类）
├── testbenches/ftq/model.py                独立参考模型（CallRetFifo / ResolveMergeModel）
├── testbenches/ftq/                        固定 ABI、SDK 整槽、全部通道比较、输入祖先与有界本地收尾
├── testbenches/resolve_queue/              agent、bundle、driver、monitor、checker、transaction
└── testbenches/commit_queue/               8 lane、FIFO 监视与 checker；agent 自持 SDK 相位监视
```

旧 `runtime/drivers/signal.py` 手动驱动在迁移前已被三个 agent 停用；schema2 没有
`runtime/` 角色，按哈希清单移除，不进入 `shared`。`shared` 只保留三个 DUT 实际使用的
装载、引脚、采样和 fixture 机制。

约束：

- 一个 driver 只能写自己声明的引脚；重复声明会在同一 DUT 上直接报错。
- monitor 在 DriveStable/RisingEdge 分别冻结全部通道；测试使用受检快照或明确的组合
  预览，不把预览当成 fire/完成。checker 的 payload 期望来自输入或独立模型，不能从
  内部状态取答案。
- 内部指针只作 actual 和不变量；输入计划决定 expected owner，不从内部状态反推 UID
  或 payload。
- 生成 RTL 去掉了 `XSError` 的 `$fatal`，因此 `InvariantMonitor` 每拍检查
  CircularQueuePtr 语义：`fetch/pf ≤ bpu`、`pnr ≤ bpu`、`commit` 落后不超过一 lap。

## 配方与构建

`ucv.json` 从完整 DefaultConfig 香山 RTL 提取三个闭包：

| DUT | RTL top | 用途 |
|---|---|---|
| `resolve_queue` | `ResolveQueue` | 最底层子模块 |
| `commit_queue` | `CommitQueue` | 最底层子模块 |
| `ftq` | `Ftq` | 上级组合与跨子模块交互 |

```sh
.venv/bin/ucv prepare ftq --jobs 12
.venv/bin/ucv build ftq --jobs 24
```

## 运行

当前回归使用根目录的 `.venv`（uc-toffee 2.1.0），每次创建新结果目录；历史
`results/ftq-final-20261030b` 属于当时环境，不覆盖或重标为新版本结果。

```sh
.venv/bin/python suites/frontend/ftq/tools/run_regression.py \
  --output results/<new-ftq-run>
.venv/bin/ucv run ftq --workers 2 --seed 2 --require-unified-baseline \
  --output results/<new-ftq-run>
.venv/bin/ucv report results/<new-ftq-run>
```

`tools/run_regression.py` 写入 `run.json`、`pytest.xml`、`traceability.md`，再合并
每个 DUT 的 Verilator 原生数据库，生成 `coverage-report/coverage.json` 与
`coverage-gaps.md`。覆盖率行分母只统计 RTL 闭包中的 `v_line`/`v_branch` LCOV 行，
不计 Picker wrapper；toggle 和 branch 分别保留为独立点。

统一入口全量运行的 `manifest.json` 为 `state=committed`、`coverage_complete=true`，
`ucv report` 无产物缺口。该工具的 `hardware_verdict` 不把 XFAIL 计为失败；本工程
仍明确保留 2 个 XFAIL，不把工具 PASS 改写成“无缺陷”。
