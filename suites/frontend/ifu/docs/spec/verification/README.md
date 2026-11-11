# IFU 验证规格

状态：`public-a0c2a26cb` / DefaultConfig 的七个 DUT 已完成新基线构建、完整/定向回归
和 6 条真实 RTL FAIL 的逐条归因；**硬件未签核**。本页是当前验证入口，详细证据、
覆盖和残余链接到各正文。
工程根的 `verification_plan.json` 已删除；功能点与追溯关系由既有功能点文档、观察覆盖
和事务合同维护，真实缺陷见问题记录，配置/观察/集成边界见退出标准。

## 范围与假设

- DUT 与层次见[设计规格](../design/README.md)；验证按自底向上顺序进行，顶层只复核
  子模块对外可观察行为。
- 基线/配置：`public-a0c2a26cb` / DefaultConfig / 单核；完整 seed 1 与定向 seed 2。
- 非 PASS 原样保留：`R-13` 两条 FAIL、`R-14` 三条 FAIL（另有一条 GE 探针不常驻），
  不登记 XFAIL、不删除反例、不改期望。`R-09` 已于 2026-11-08 有证据关闭。
- 技术边界：生成 RTL 无 `$fatal`；参考模型只依据架构/规范；生产者宽度优先。

## 当前结果

- 7/7 DUT `BUILT + SMOKE PASS`（2026-11-07 新基线适配）。
- 2026-11-08 完整 seed 1：**939 PASS / 6 FAIL / 0 UNCERTAIN**（945 nodeid，
  `results/ifu-a0c2a26cb-carry-sweep-seed1-20261108`）；同源码 seed 2 定向：
  **350 PASS / 4 FAIL / 0 UNCERTAIN**（`results/ifu-a0c2a26cb-carry-sweep-seed2-20261108`）。
- carry 扫掠扩为 217 条（16 个奇数位置 × 7 类 × 2 种前导形状，覆盖写 bank lane 0..3），
  全 PASS；相对 2026-11-07 的 727 nodeid 无删除，新增 26 项。
- 六条硬件 FAIL 的逐条归因、根因行号和上游只读检索见
  [退出标准](exit-criteria.md) §3 与两个问题记录。

## 验证内容

| 主题 | 入口 |
|---|---|
| 功能点语义、期望来源与 DUT 合同 | [功能点](../design/functional-points.md) |
| 行为等价类与组合策略 | [行为矩阵](../design/behavior-matrix.md) |
| 事务适配、驱动/采样与检查器 | [事务适配状态](transaction-adapters.md) |
| 需求→驱动→观测→比较器→nodeid 对账 | [观察覆盖](observation-coverage.md) |
| 逐模块覆盖闭环 | [覆盖闭环](coverage/coverage-loop.md)、[覆盖摘要](coverage/coverage-summary.md) |
| 退出合同、残余 R-01..R-14 | [退出标准](exit-criteria.md) |
| 上游复核 | [2026-10-29 上游复核](evidence/upstream-review-20261029.md) |
| 历史 UNCERTAIN/本地框架核验 | [2026-10-30 UNCERTAIN 迁移](evidence/uncertain-migration-20261030.md) |
| `R-13` 问题 | [FrontendTrigger tdata2 宽度](../../bugs/open/frontend-trigger-tdata2-width.md) |
| `R-14` 问题 | [InstrBoundary carry/FTQ 归属](../../bugs/open/instr-boundary-carry-ftq-owner.md) |

## 完成条件与缺口

- `R-13`、`R-14` 修复前不得写成完整验收；关闭必须有修复后的新回归证据，且原有
  in-range/正常 carry 对照不能回归。
- `R-14` 保留为端口合同 FAIL，但真实 FTQ 生产可达性未证明；文档不得把端口压力
  自动升级为整机缺陷。
- 生成 RTL 丢断言、模型掩码和未比较字段按[观察覆盖](observation-coverage.md)与
  [退出标准](exit-criteria.md)的残余边界陈述。
- 结果目录不进入 Git；结论只对锁定基线、DefaultConfig RTL、实际源码/原生包和相应
  seed 成立。
