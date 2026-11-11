# BPU 资料入口

## 开始工作

- [工程入口](../README.md)与[首次运行教程](../../../../docs/tutorials/bpu-first-ut.md)。
- 从仓库根运行 `./scripts/ucv info bpu --dut mbtb`：生成规格、源码、RTL、环境和测试资源地图。
- `./scripts/ucv check bpu`：检查布局、登记文件和当前页面链接。
- 实现与用例从 [`testbenches/`](../testbenches) 进入；共用组件与自检见
  [`shared`](../testbenches/shared/README.md)，按[目录职责](guides/repository-layout.md)归属。

## 当前规格与证据

| 内容 | 入口 |
|---|---|
| 设计职责、接口、行为要求与待确认项 | [Design spec](spec/design/README.md)（含 bpu/abtb/mbtb/ubtb/tage/utage/ittage/sc/ras/uras 逐模块当前规格） |
| 验证范围、场景、检查、覆盖和完成条件 | [Verification spec](spec/verification/README.md)（含逐模块当前入口） |
| 功能点、责任 DUT 与合同入口 | [功能点辅助索引](spec/verification/functional/feature-classification.md)、[模块行为目录](spec/design/module-behavior-matrix.md) |
| 当前问题与待核调查 | [问题报告](bugs/README.md) |

验证规格下的具体材料：

- [验证合同与事务接口](spec/verification/contracts)：机器 JSON 和事务合同。
- [功能点、事件与场景](spec/verification/functional)：功能点清单、事件目录和场景记录。
- [覆盖设计、矩阵与归因](spec/verification/coverage)：代表分区、组合矩阵和覆盖缺口。
- [架构、参考模型与检查设计](spec/verification/architecture)：事务、scoreboard 和语义参考模型。
- [运行、复核与历史材料](spec/verification/evidence)：按运行、评审、分析和模块复核保留原日期与基线。

历史材料中的 `results/`、`rtl/`、`dut/` 和 `REPORT.md` 指向当时的运行或生成产物；
本检出未携带这些对象时，链接保留原对象但表示不可用，不代表当前证据。
工程根的 `verification_plan.json` 已删除。旧[功能点清单](spec/verification/functional/functional-points.md)、
[功能点定义与事件证据](spec/verification/functional/verification-point-semantics.md)、覆盖分析和
历史报告中的旧计划路径、统计与审计命令属于当时版本；当前工作沿用规格、合同和问题入口。

设计侧现有 [模块行为目录](spec/design/module-behavior-matrix.md)、
[Scala 交互审查](spec/design/scala-interactions-20261106.md) 和逐模块当前规格
（[bpu](spec/design/bpu.md)、[abtb](spec/design/abtb.md)、[mbtb](spec/design/mbtb.md)、
[ubtb](spec/design/ubtb.md)、[tage](spec/design/tage.md)、[utage](spec/design/utage.md)、
[ittage](spec/design/ittage.md)、[sc](spec/design/sc.md)、[ras](spec/design/ras.md)、
[uras](spec/design/uras.md)）。旧模块复核与历史合同在各自 evidence 位置保留原
日期、基线和判定；当前条款以逐模块规格为准。

## 操作与维护

- [产物策略](guides/artifact-policy.md)、[DUT 重建](guides/dut-rebuild.md)、
  [回归配置](guides/regression-profiles.md)、[目录职责](guides/repository-layout.md)。
- 工具使用指南采用 Diátaxis；文档维护约定见
  [文档维护](../../../../docs/how-to/maintain-docs.md)。
- 普通运行的计数、覆盖表和汇总放在运行结果目录，由工具生成。带日期的材料保留
  原基线、用途和程序引用；当前状态以规格、实际运行证据和问题目录为准。
- 目录迁移只重定位文档路径；合同与分析 JSON 的历史哈希、判定和运行目录未改写，
但当前规格文本可能因路径更新而不同于原字节，不能当作原始证据。
本次 testbench 整理保留历史材料及场景执行记录原字节，旧源码路径由
[`path-migrations.json`](path-migrations.json) 多跳导航到当前实现。
