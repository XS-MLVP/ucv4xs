# FTQ 验证规格

状态：当前验证范围已按 `public-a0c2a26cb` 核验；**不是硬件验收**。本页给出方法、
判定和入口，具体功能点到用例的映射见[追溯表](traceability.md)。

## 范围与假设

- DUT：`ResolveQueue`、`CommitQueue`、`Ftq`（真实实例化前两者）。
- 基线/配置：`public-a0c2a26cb` / DefaultConfig / 单核；seed 1 与 seed 2。
- 合法输入域、责任矩阵和上层承接见[设计责任边界](../design/requirements-boundary.md)。
  不把上层 ICache/IFU/BPU/后端行为当作本工程 PASS。
- 环境按 agent / driver / monitor / checker / transaction 分层，测试只持有事务；
  包结构与采样约定见[验证包结构](architecture.md)。

## 结果与判定

最新完整回归：**931 PASS / 2 XFAIL**（933 nodeid，seed 1 与 seed 2 的逐 nodeid
判定一致）。0 FAIL、0 SKIP、0 ERROR；两个 strict XFAIL 是同一真实 RTL 缺陷的两个
独立表现，不转正、不删除。详细 RTL 差分、构建身份、逐 nodeid 对账和覆盖归因见
[新基线适配记录](reports/baseline-adaptation-a0c2a26cb.md)。

覆盖（seed 2）：`resolve_queue` 行 100.0% / 分支 99.9% / toggle 89.2%；
`commit_queue` 100.0% / 99.8% / 100.0%；`ftq` 100.0% / 99.8% / 84.3%。
剩余分支计数来自 4 个 distinct Verilator 初始化 reset else，不是运行期功能路径。
2026-10-30 的 109/2、51996/51996 等数字属于 `public-893e1580b`，保留原义，不与本轮拼接。

## 验证内容

| 主题 | 入口 |
|---|---|
| 功能点语义与期望来源 | [功能点](../design/functional-points.md) |
| 行为等价类与组合策略 | [等价类](../design/equivalence-classes.md) |
| 功能点 → 用例 → 判定 | [追溯表](traceability.md) |
| 事务边界、驱动/采样与检查器 | [事务迁移复核](transaction-adaptation.md) |
| 覆盖率闭环与归因 | [覆盖分析](coverage/coverage-analysis-20261030.md) |
| 退出标准、残余和结论边界 | [残余与退出状态](residuals.md) |
| 历史运行证据（893e1580b） | [2026-10-30 证据](evidence/evidence-20261030.md) |

## 完成条件与缺口

- 超 8 分支的 `RQ-011` 未修复：当前验收门槛若要求“超容量解析不破坏已记录分支”，
  状态为未通过；两个 strict XFAIL 必须保留，直到有修复后的重建与复验证据。
- 顶层行覆盖 100% 不表示“FTQ 无缺陷”或“整机取指正确”。toggle 残余、未导出断言、
  上游差分和上层消费分别见[残余](residuals.md)的 R-03/R-04/R-05/R-07/R-08。
- 历史结果目录不进入 Git；本页结论只对锁定基线、DefaultConfig RTL、实际源码/原生包
  和相应 seed 成立。
