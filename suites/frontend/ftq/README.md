# FTQ 验证工程

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

环境按 agent / driver / monitor / checker / transaction 分层，测试只持有事务：

```text
suites/frontend/ftq/      import suites.frontend.ftq
├── __init__.py           ROOT：工程资源根，不构造 DUT
├── ports.py              跨 DUT 的引脚所有权；具体映射仍在各 DUT bundle
├── drivers/signal.py     Pulse / Level / Reset 驱动，负责发射与撤销时序
├── monitors/cycle.py     EdgeMonitor / InvariantMonitor，每拍被动采样
├── fixtures.py           DUT + Execution + agent 的 pytest fixture
├── harness.py            DUT 装载、时钟/执行上下文、引脚所有权与指针安全网
├── oracle.py             独立参考模型（CallRetFifo / ResolveMergeModel）
├── resolve_queue/
│   ├── agent/main.py     ResolveQueueAgent：驱动、监视、checker 装配
│   ├── bundle/ports.py   后端 3 lane、IFU、训练输出、重定向/入队引脚
│   ├── driver/encoding.py
│   ├── monitor/decode.py 训练事务解码
│   ├── checker/model.py  与 oracle 对账
│   └── transaction/types.py
├── commit_queue/         同构：8 lane、FIFO 监视与 checker
└── ftq/                  同构：预测/meta/重定向/resolve/commit 与全部输出监视
```

约束：

- 一个 driver 只能写自己声明的引脚；重复声明会在同一 DUT 上直接报错。
- monitor 只在上升沿采样，测试读取 monitor 快照；checker 比较事务和独立模型，只有指针不变量读取内部所有权信号，且不把内部状态当作 payload 期望。
- 内部指针仅用于所有权身份和不变量，不作为 payload 期望来源。
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
