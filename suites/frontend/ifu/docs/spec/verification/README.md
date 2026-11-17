# IFU 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `rvc_expander` / `RvcExpander` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/rvc_expander/README.md) |
| `instr_boundary` / `InstrBoundary` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/instr_boundary/README.md) |
| `pred_checker` / `PredChecker` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/pred_checker/README.md) |
| `uncache_unit` / `IfuUncacheUnit` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/uncache_unit/README.md) |
| `frontend_trigger` / `FrontendTrigger` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/frontend_trigger/README.md) |
| `perf_analysis` / `IfuPerfAnalysis` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/perf_analysis/README.md) |
| `ifu` / `Ifu` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/ifu/README.md) |

<!-- ucv:work-index:end -->

## 当前工作（public-e716c7658）

负责人：各 DUT **待认领**。每个对象按对应功能点认领，当前工作为接口与合同复核，
随后按 DUT 适配、构建并复验；历史七 DUT 的运行结果不继承到当前基线。

- `ifu`：先核对裁剪端口、生产者合法域和事务身份，再分别复验缓存/非缓存取指与取消。
- `instr_boundary`、`frontend_trigger`：保留 R-14/R-13 原反例、合法对照及可达性边界，
  在当前基线重新定位；问题状态只维护在原记录。
- `rvc_expander`、`pred_checker`、`uncache_unit`、`perf_analysis`：按各自功能点核对
  端口、独立预期与观察覆盖，分别记录实际选择与结果。

阻塞：当前基线适配与原生资源尚未准备完整；本机工具身份问题见[全仓状态](../../../../../../docs/status.md)。
当前硬件验收证据尚无。认领后在本节或关联任务补责任人、下一项合同条款与运行证据。

## 历史验证范围（public-a0c2a26cb）

`public-a0c2a26cb` / DefaultConfig 的七个 DUT 曾完成构建、完整/定向回归
和 6 条真实 RTL FAIL 的逐条归因；**硬件未签核**。详细证据、覆盖和残余链接到各正文。
工程根的 `verification_plan.json` 已删除；功能点与追溯关系由既有功能点文档、观察覆盖
和事务合同维护，真实缺陷见问题记录，配置/观察/集成边界见退出标准。

## 范围与假设

- DUT 与层次见[设计规格](../design/README.md)；验证按自底向上顺序进行，顶层只复核
  子模块对外可观察行为。
- 基线/配置：`public-a0c2a26cb` / DefaultConfig / 单核；完整 seed 1 与定向 seed 2。
- 非 PASS 原样保留：`R-13` 两条 FAIL、`R-14` 三条 FAIL（另有一条 GE 探针不常驻），
  不登记 XFAIL、不删除反例、不改期望。`R-09` 已于 2026-11-08 有证据关闭。
- 技术边界：生成 RTL 无 `$fatal`；参考模型只依据架构/规范；生产者宽度优先。

## 历史结果（2026-11-08）

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
