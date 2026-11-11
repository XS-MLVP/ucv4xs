# FTQ 文档

当前摘要、构建与运行入口见[工程 README](../README.md)。本目录只保留设计规格、
验证规格和问题记录；完整运行结果、波形与生成 RTL 留在忽略目录。

## 当前边界

- 基线：`public-a0c2a26cb` / DefaultConfig；DUT：`ResolveQueue`、`CommitQueue`、`Ftq`。
- 最新完整回归为 **931 PASS / 2 XFAIL**（933 nodeid，seed 1 与 seed 2 判定一致）。
  两个 strict XFAIL 是 `ResolveQueue` 超 8 分支容量的真实 RTL 缺陷，保持
  [未解决](bugs/open/resolve-queue-branch-overflow.md)；不能据此写成硬件通过。
- 覆盖、逐 nodeid 对账和 RTL 差分见[新基线适配记录](spec/verification/reports/baseline-adaptation-a0c2a26cb.md)；
  2026-10-30 的 109/2 与 51996/51996 属于 `public-893e1580b`，不并入当前数字。

## 文档入口

| 主题 | 入口 |
|---|---|
| 设计职责、层次、配置与合法输入 | [设计规格](spec/design/README.md) |
| 功能点语义与责任矩阵 | [功能点](spec/design/functional-points.md)、[责任边界](spec/design/requirements-boundary.md) |
| 行为等价类与组合策略 | [等价类](spec/design/equivalence-classes.md) |
| 验证策略、追溯与当前证据 | [验证规格](spec/verification/README.md) |
| 事务适配与边界 | [事务迁移复核](spec/verification/transaction-adaptation.md) |
| 覆盖率闭环与残余 | [覆盖分析](spec/verification/coverage/coverage-analysis-20261030.md)、[残余](spec/verification/residuals.md) |
| 历史运行证据（893e1580b） | [2026-10-30 证据](spec/verification/evidence/evidence-20261030.md) |
| Testbench 工作入口 | [ftq](../testbenches/ftq/README.md)、[resolve_queue](../testbenches/resolve_queue/README.md)、[commit_queue](../testbenches/commit_queue/README.md)、[shared](../testbenches/shared/README.md) |
| 问题状态 | [问题索引](bugs/README.md) |

## 维护约定

- 设计要求与验证场景分开维护；功能点 ID 稳定，新增用例继续使用同一 ID 或显式新增。
- `tools/traceability.py` 以[功能点](spec/design/functional-points.md)为 ID 来源，生成
  [追溯表](spec/verification/traceability.md)。
- 新基线或新 seed 使用新的结果目录，不覆盖、不改写旧结论；旧基线 PASS 不能自动升级为
  当前已修。缺陷关闭必须在 `docs/bugs/closed/` 提供复验证据。
