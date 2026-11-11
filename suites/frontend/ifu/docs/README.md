# IFU 文档

当前摘要、构建与运行入口见[工程 README](../README.md)。本目录按设计规格、验证规格
和问题记录组织；完整运行结果、波形和生成 RTL 留在忽略目录。
工程根的 `verification_plan.json` 已删除；功能点、合同和未证明范围沿用下列规格正文。
历次覆盖闭环与报告中的旧计划路径、残余插件及门禁描述属于当时版本，当前运行不再
要求旧计划或残余清单；这些历史记录不因删除计划改标为通过。

## 当前边界

- 基线：`public-a0c2a26cb` / DefaultConfig / 单核；七个 DUT 均已完成 prepare/build。
- 2026-11-08 完整 seed 1 为 **939 PASS / 6 FAIL / 0 UNCERTAIN**（945 nodeid）；
  同源码 seed 2 定向为 350 PASS / 4 FAIL。6 条 FAIL 均归因为真实 RTL，未改期望、
  未登记 XFAIL。
- `R-13`（FrontendTrigger `tdata2` 高 14 位不参与比较）和 `R-14`（InstrBoundary carry
  误标跨块导致 FTQ 归属错误）仍开放、blocking；`R-09` 已有证据关闭。
- 2026-11-07 新基线适配和 2026-10-30 历史运行是旧检查点；数字与证据边界不重标。

## 文档入口

| 主题 | 入口 |
|---|---|
| 七个 DUT 的层次、接口与合法输入 | [设计规格](spec/design/README.md) |
| 功能点语义与期望来源 | [功能点](spec/design/functional-points.md) |
| 行为等价类与组合 | [行为矩阵](spec/design/behavior-matrix.md) |
| 验证策略、事务与观察点 | [验证规格](spec/verification/README.md) |
| 退出标准、残余与结论边界 | [退出标准](spec/verification/exit-criteria.md) |
| 观察点与比较器对账 | [观察覆盖](spec/verification/observation-coverage.md) |
| 覆盖率闭环与摘要 | [闭环记录](spec/verification/coverage/coverage-loop.md)、[摘要](spec/verification/coverage/coverage-summary.md) |
| 上游复核与历史环境核验 | [上游复核](spec/verification/evidence/upstream-review-20261029.md)、[UNCERTAIN 迁移](spec/verification/evidence/uncertain-migration-20261030.md) |
| 问题状态 | [问题索引](bugs/README.md) |

## 维护约定

- 条目覆盖功能点的一部分时，使用 `@pytest.mark.uncertain(reason=..., reference=...)`；
  需要追溯时引用规格条款或问题 ID。UNCERTAIN 不计 PASS，也不改变退出码。
- 生产者宽度优先：CSR/上游能写出的最宽值参与需求，不把本层端口宽度当合同。
- 参考模型只依据架构/规范表达意图；模型里出现掩码必须说明是规范约束还是抄了 RTL。
- 新基线或新 seed 使用新的结果目录；旧 PASS 不能升级为当前已修，缺陷关闭必须有
  新证据。
