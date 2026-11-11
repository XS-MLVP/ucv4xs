# BPU Verification spec

状态：**现有验证资产的统一入口，完整性待审查**。
适用 `public-a0c2a26cb` / DefaultConfig。设计要求入口为 [Design spec](../design/README.md)。

## 1. 验证范围与假设

- 验证完整香山 RTL 提取的十个实际 DUT；Bpu 顶层与组件分别拥有独立测试边界。
- 激励须区分真实 producer 合法输入和单元接口能力测试。
- 独立期望来自合同、协议或输入历史模型；规格未确认的预期继续登记为待确认。
- 现有 FAIL/ERROR/XFAIL/SKIP 和不可观察义务保持原判定及范围。

## 2. 功能项、场景与实现关联

功能 ID、合同与模型/checker/覆盖的关联沿用既有功能点文档、逐模块规格和合同。
工程根的 `verification_plan.json` 已删除，不以改名计划文件替代。
`ucv check bpu` 检查布局、资源路径和当前入口；语义充分性由工程 review 判断。

- 行为与场景划分：[模块行为目录](../design/module-behavior-matrix.md)。
- 责任 DUT 与层级：[功能点辅助索引](functional/feature-classification.md)；
  [旧功能点清单](functional/functional-points.md)保留历史阶段定义与测量。
- 代表分区：[覆盖设计](coverage/behavior-coverage-design.json)。
- 已关联场景证据：[场景记录](functional/behavior-scenarios.json)。
- 新的设计要求 ID 确认后，在既有功能项中记录关联，保留已有功能 ID。

### 模块级当前入口

每个 DUT 的 `workspace.json` 登记下列当前设计规格、合同和接口历史材料；`ucv info`
会逐项展开。模块复核属于历史运行记录：端口/位宽事实可追溯，但 PASS/FAIL/覆盖数字
不自动成为当前基线判定。

| DUT | 当前设计规格 | 主要合同/功能入口 | 接口/历史记录 |
|---|---|---|---|
| bpu | [bpu.md](../design/bpu.md) | [流水合同](contracts/pipeline-transaction-contract.md)、[PHR合同](contracts/phr-transaction-contract.md) | [历史组合审查](evidence/reviews/bpu-integrated-functional-definition-review-20261016.md)、[当前检查点](evidence/runs/closeout-20261108.md) |
| mbtb | [mbtb.md](../design/mbtb.md) | [当前事务合同](contracts/mbtb-transaction-contract.md)、[shared-service owner](contracts/mbtb-shared-service-owner-contract.json) | [2026-10-30 模块复核](evidence/module-reviews/mbtb-module-review-20261030.md) |
| ras | [ras.md](../design/ras.md) | [退休动作合同](contracts/ras-original-commit-action-contract.json)、[自有返回栈合同](contracts/owned-return-stack-contract-20261020.json) | [2026-10-30 模块复核](evidence/module-reviews/ras-module-review-20261030.md) |
| ubtb | [ubtb.md](../design/ubtb.md) | [功能点索引](functional/feature-classification.md)、[行为覆盖设计](coverage/behavior-coverage-design.json) | [2026-10-29 模块复核](evidence/module-reviews/ubtb-module-review-20261029.md) |
| abtb | [abtb.md](../design/abtb.md) | [功能点索引](functional/feature-classification.md)、[行为覆盖设计](coverage/behavior-coverage-design.json) | [2026-10-30 模块复核](evidence/module-reviews/abtb-module-review-20261030.md) |
| utage | [utage.md](../design/utage.md) | [UTAGE 工作集合合同](contracts/utage-working-set-contract.json)、[学习持久合同](contracts/utage-learning-persistence-contract.json) | [2026-10-30 模块复核](evidence/module-reviews/utage-module-review-20261030.md) |
| tage | [tage.md](../design/tage.md) | [功能点索引](functional/feature-classification.md)、[行为覆盖设计](coverage/behavior-coverage-design.json) | [2026-10-30 模块复核](evidence/module-reviews/tage-module-review-20261030.md) |
| sc | [sc.md](../design/sc.md) | [功能点索引](functional/feature-classification.md)、[行为覆盖设计](coverage/behavior-coverage-design.json) | [2026-10-30 模块复核](evidence/module-reviews/sc-module-review-20261030.md) |
| ittage | [ittage.md](../design/ittage.md) | [功能点索引](functional/feature-classification.md)、[行为覆盖设计](coverage/behavior-coverage-design.json) | [2026-10-30 模块复核](evidence/module-reviews/ittage-module-review-20261030.md) |
| uras | [uras.md](../design/uras.md) | [自有返回栈合同](contracts/owned-return-stack-contract-20261020.json)、[中性恢复合同](contracts/bpu-neutral-recovery-contract.json) | [2026-10-29 模块复核](evidence/module-reviews/uras-module-review-20261029.md) |

稳定功能 ID 通过模块行为目录、功能点文档和合同追溯；未证明范围见本页完成条件与
所属模块规格。行为到场景/检查义务的有界设计以
[behavior-coverage-design.json](coverage/behavior-coverage-design.json) 为准。

### 当前材料分区

| 材料 | 入口 |
|---|---|
| 机器合同与事务接口 | [contracts/](contracts) |
| 功能点、事件、场景与语义索引 | [functional/](functional) |
| 覆盖设计、组合矩阵与缺口归因 | [coverage/](coverage) |
| 事务、scoreboard 与语义参考模型 | [architecture/](architecture) |
| 运行、复核、分析与模块闭环历史 | [evidence/](evidence) |
| 使用与构建操作 | [工程指南](../../guides) |

当前基线适配与收口仍按原范围阅读：[2026-11-03 基线适配](evidence/runs/baseline-update-a0c2a26cb.md)、
[2026-11-08 收口检查点](evidence/runs/closeout-20261108.md)。真实 FAIL、SKIP、
XFAIL 和历史非 PASS 保持原判定，不由目录整理改变。

### 入门实例：MainBTB 复位后的冷查询

| 项 | 现有入口 |
|---|---|
| 验证项 | `BPU-MBTB-001`，复位/冷查询要求见 [MainBTB 规格](../design/mbtb.md)与[事务合同](contracts/mbtb-transaction-contract.md) |
| 场景 | reset 完成后，对 `DIRECT.pc` 发起冷查询 |
| 激励 | [test_reset.py](../../../testbenches/mbtb/tests/testcase/test_reset.py) |
| 环境 | [MbtbAgent](../../../testbenches/mbtb/env/agent/main.py)；fixture 在 [conftest.py](../../../conftest.py) |
| 显式检查 | reset 等待小于 256 拍；`assert_miss(cold)` |
| 检查实现 | [assertions.py](../../../testbenches/mbtb/checker/assertions.py) |
| 范围 | 一个复位/冷查询场景；完整复位交互、学习和替换另有用例 |

运行命令由 `ucv info bpu --dut mbtb` 展示；实操见[入门教程](../../../../../../docs/tutorials/bpu-first-ut.md)。

## 3. 观察、判定与覆盖

每个验证项应有：合法前态、输入历史、预期结果、禁止副作用、观察位置、独立判定依据、
接受与完成条件。覆盖区分 reached 和 checked；独立组件的结果不代替顶层组合的观察。

原生加载/复位冒烟由 `ucv build` 执行。功能测试由 `ucv run` 执行，结果与基线、源码身份、
选择范围、种子及原生哈希一同保存。`ucv report` 生成结果视图。
功能标记统计标为 `scope=collected-test-markers`，只来自实际收集标签，不代表完整需求
分母。新运行冻结问题记录；当前基线仍开放或未复验的 open 问题使纯 PASS 汇总为
`INCOMPLETE`，实际 case 计数保留，真实 FAIL/ERROR 优先。

## 4. 完成条件与开放项

- 设计要求完成 review，验证项有可追溯的要求来源。
- 场景和检查已实现，合法对照与区分性错误对照支持关键 checker。
- 当前基线下的所需运行与覆盖证据完整，未完成范围明确。
- 开放缺陷、观察与集成缺口逐项有处置依据；实际测试计数与工程验收分别报告。

当前仍需处理的范围沿用 [Bpu 规格](../design/bpu.md)中的三个标识：

- `BPU-UPGRADE-OBS-01`：公开 target/perfMeta 被裁剪，完整输出观察义务尚未建立；
  组件结果不能代替顶层集成观察。
- `BPU-UPGRADE-SEM-01`：历史 FAIL/ERROR 仍须逐项核对合同、合法前态、适配和首错，
  未确认根因不能统称 RTL 缺陷。
- `BPU-UPGRADE-SCOPE-01`：完整 producer/FTQ 可达性及联合交互证据尚未完成；
  有限 IO 矩阵的 21 个 gap 保持原范围。

上述观察/集成/验证缺口维护在所属规格；具体缺陷与调查状态进入[问题记录](../../bugs/README.md)。
旧计划的删除不关闭这些义务。重要历史结论从 [BPU README](../../../README.md) 进入，
运行统计由报告提供；旧报告中的残余字段与旧功能点审计命令只对应当时版本。
