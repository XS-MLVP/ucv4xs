# FTQ 验证工程

当前原生加载器按`ucv run --seed`传入Verilator seed（未设置时为1）；每次构造解析
`ucv.runtime.native_seed`，不再忽略运行收据中的seed。构造器正反对照见根
`tests/test_frontend_runtime_seed.py`。此前仅登记CLI seed的历史结果不自动成为已复现的
原生多seed证据；真实功能FAIL/XFAIL仍按原结果保留。

本工程按真实实例化层次验证香山 FTQ（Fetch Target Queue）：

```text
Ftq
├── ResolveQueue   分支解析归并、重定向冲刷与 BPU 训练出队
└── CommitQueue    call/return 退休动作的保序队列
```

`EntryQueue`、`CfiQueue`、`MetaQueue`、`SpeculationQueue` 是包内未被 `Ftq` 实例化的类，
不进入本工程的 DUT 闭包，也不冒充 FTQ 子模块。FTQ 自己直接维护的 entry/meta/pointer
状态由顶层用例验证。

## 验证包结构

2026-11-02适配边界：CommitQueue已使用SDK Driver、双阶段lossless采样和UID终态账本；
ResolveQueue已接入整槽SDK驱动、严格ABI及自动合并/完成/取消检查，双seed收据核验完成。
Ftq顶层现已具备固定全ABI、SDK唯一整槽输入、完整公开输出的双阶段比较及输入UID/
取消/重试/本地有界收尾。当前最终完整回归为**905 PASS/2 XFAIL**，495项新增selftest
通过、前412项判定保持；同源码seed1定向**122 PASS**，Ftq收集907项保持原集合/顺序。
当前三个DUT的事务适配范围已核验；不得把
结构零泄漏、旧109/2或历史行覆盖结果推广成全工程事务验收。当前合同和信用边界见
[事务迁移复核](docs/transaction-adaptation.md)。
此前callret/commit子链源码完整回归为**410 PASS/2 XFAIL**，同源码seed1选测146 PASS、
根242 PASS；原356项判定保持，新56项为输入计划/快照与commit协议selftest，不计新硬件点。
当时全仓collection47930项，原集合无删除/顺序保持；另外五通道当时缺口保留在
[commit机器证据](../../../docs/history/transaction-goal-ftq-top-commit-20261102.json)，后续实现/中间
FAIL及当前905/2结果见[组合机器证据](../../../docs/history/transaction-goal-ftq-top-frontend-20261102.json)。
较早354/2的整槽检查点见[原机器证据](../../../docs/history/transaction-goal-ftq-top-slots-20261102.json)，不重标其源码身份。
两个XFAIL此前另以`--runxfail`保持真实slot7/slot0覆盖FAIL，见
[ResolveQueue机器证据](../../../docs/history/transaction-goal-ftq-resolve-transactions-20261102.json)。

环境按 agent / driver / monitor / checker / transaction 分层，测试只持有事务：

```text
suites/frontend/ftq/      import suites.frontend.ftq
├── __init__.py           ROOT：工程资源根，不构造 DUT
├── ports.py              跨 DUT 的引脚所有权；具体映射仍在各 DUT bundle
├── drivers/signal.py     旧手动驱动留档代码，当前三个agent均不再调用
├── monitors/cycle.py     SDK双阶段采样的不可变snapshot及decoder/cache view
├── fixtures.py           DUT + Execution + agent 的 pytest fixture
├── harness.py            DUT 装载、时钟/执行上下文、引脚所有权与指针安全网
├── oracle.py             独立参考模型（CallRetFifo / ResolveMergeModel）
├── resolve_queue/
│   ├── agent/main.py     ResolveQueueAgent：驱动、监视、checker 装配
│   ├── bundle/ports.py   后端 3 lane、IFU、训练输出、重定向/入队引脚
│   ├── driver/           严格事务编码与SDK整槽SyncDriver
│   ├── monitor/decode.py 训练事务解码
│   ├── checker/          原纯参考及自动UID/合并/终态比较
│   └── transaction/      严格report、完整同时输入及不可变身份
├── commit_queue/         同构：8 lane、FIFO 监视与 checker
└── ftq/                  固定ABI、SDK整槽、全部通道比较、输入祖先与有界本地收尾
```

约束：

- 一个 driver 只能写自己声明的引脚；重复声明会在同一 DUT 上直接报错。
- monitor在DriveStable/RisingEdge分别冻结全部通道；测试使用受检快照或明确的组合预览，
  不把预览当成fire/完成。checker的payload期望来自输入或独立模型，不能从内部状态取答案。
- 内部指针只作actual和不变量；输入计划决定expected owner，不从内部状态反推UID或payload。
- 生成 RTL 去掉了 `XSError` 的 `$fatal`，因此 `InvariantMonitor` 每拍照
  CircularQueuePtr 语义检查 `fetch/pf ≤ bpu`、`pnr ≤ bpu`、`commit` 落后不超过一 lap。

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

当前回归使用根目录的 `.venv`（uc-toffee 2.1.0），每次创建新结果目录。
历史 results/ftq-final-20261030b 属于当时环境，不覆盖或重标为新版本结果。
在根目录运行独立工程工具时：

```sh
.venv/bin/python suites/frontend/ftq/tools/run_regression.py \
  --output results/<new-ftq-run>
```

也可以用统一入口执行和生成报告：

```sh
.venv/bin/ucv run ftq --workers 1
.venv/bin/ucv report results/<run>
```

`tools/run_regression.py` 写入 `run.json`、`pytest.xml`、`traceability.md`，再合并每个
DUT 的 Verilator 原生数据库，生成 `coverage-report/coverage.json` 与 `coverage-gaps.md`。
覆盖率行分母只统计 RTL 闭包中的 `v_line`/`v_branch` LCOV 行，不计 Picker wrapper；
toggle 和 branch 分别保留为独立点。

## 当前证据

2026-10-30 的运行 `results/ftq-final-20261030b`：

- 109 PASS，2 XFAIL（strict，都已确认的 ResolveQueue 容量缺陷），0 FAIL，0 SKIP。
- `resolve_queue`：行 100.0%，分支 99.9%，toggle 89.2%。
- `commit_queue`：行 100.0%，分支 99.8%，toggle 100.0%。
- `ftq`：行 **100.0%**，分支 99.6%，toggle 84.4%。

顶层闭包行覆盖达到 100%，原先记录的“IFU 命中 fallback 未逐槽枚举”缺口已由顶层
物理槽 × 分支槽 × 来源矩阵用例关闭。剩余未覆盖分支只有：三个 Verilator 初始化块的
复位 else，以及三条只能由同一拍 backend lane 与 IFU 同索引触发的 mux 臂（IFU resolve
经寄存，顶层不可同拍）。

功能点、责任边界、等价类、追溯与残余见：

- [验证包结构](docs/architecture.md)
- [功能点与语义](docs/functional-points.md)
- [责任边界与合法输入](docs/requirements-boundary.md)
- [行为等价类](docs/equivalence-classes.md)
- [功能点追溯](docs/traceability.md)
- [覆盖率闭环分析](docs/coverage-analysis-20261030.md)
- [残余与退出状态](docs/residuals.md)
- [本轮运行证据](docs/evidence-20261030.md)

统一入口的全量运行 `ucv run ftq --workers 1` 为 `PASS 109 / XFAIL 2`；其
`manifest.json` 为 `state=committed`、`coverage_complete=true`，`ucv report` 无产物缺口。
该工具的 `hardware_verdict` 不把 XFAIL 计为失败，本工程仍明确保留 2 个 XFAIL，不把工具
PASS 改写成“无缺陷”。

结果目录不进入 Git；结论只对本次 `public-893e1580b` 基线、DefaultConfig RTL
和实际运行的源码/原生包成立。
