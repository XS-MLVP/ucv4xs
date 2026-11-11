# BPU 验证工程

## 第一次使用

从[MainBTB 第一个 UT](../../../docs/tutorials/bpu-first-ut.md)开始。
只读源码和编写规格可以在安装仿真工具之前进行。

```sh
./scripts/ucv info bpu --dut mbtb
./scripts/ucv check bpu
```

资源地图由 `ucv` 从工程配方和 [workspace.json](workspace.json) 生成，包含精确版本
源码链接、RTL/原生包路径、环境和测试入口。[Design spec](docs/spec/design/README.md)与
[Verification spec](docs/spec/verification/README.md)按设计/验证工程组织，并登记到
bpu/abtb/mbtb/ubtb/tage/utage/ittage/sc/ras/uras 的逐模块当前规格；[资料入口](docs/README.md)
说明当前内容和历史材料的维护方式。

## 验证设计从这里开始

1. [模块行为目录](docs/spec/design/module-behavior-matrix.md)：先核对每个 DUT 应做什么、合同来源和
   责任边界，再反查已有 ID；目录齐全不等于行为审查或覆盖已完成。
2. [Scala交互审查](docs/spec/design/scala-interactions-20261106.md)与[覆盖设计](docs/spec/verification/coverage/behavior-coverage-design.json)：
   固定当前Scala，对33个行为族展开78条代表分区、十模块八维入口和11个关键交互；每项有
   合法前态、预期/待确认、禁止副作用、区分性错误规则和下一实验。它是**有界待映射设计**，
   不是全组合证明或新运行结果；两个无旧ID的候选需求显式保留。
   [场景证据记录](docs/spec/verification/functional/behavior-scenarios.json)仍只保留3条 MainBTB 示例及其真实历史引用，
   不把既有测试或PASS自动贴到新设计上。
3. [验证规格](docs/spec/verification/README.md)、既有功能点文档与对应模型/checker：
   沿用功能 ID、合同和实现关联；按[辅助索引](docs/spec/verification/functional/feature-classification.md)
   找 DUT/层级，别以点数代替需求分类。工程根的 `verification_plan.json` 已删除。
4. [有限 IO 矩阵及原运行证据](docs/spec/verification/coverage/io-matrix-extension-20261103.md)：只认同轮源码、
   实际 nodeid、reached/checked、负对照和完成记录。无实现/未到达/未比较各记缺口。

设计应沿“模块责任 → 行为 → 场景 → 检查义务 → 证据”推进，不把旧测试标题作为需求
全集，也不将历史 PASS 粘贴到新场景。文档/清单自检不产生新的硬件通过信用。

## 已执行的历史记录（硬件未签核）

**2026-11-08 验证侧收口进行中**：见[当前检查点](docs/spec/verification/evidence/runs/closeout-20261108.md)。严格BPU事务
审计的owner债务已实测**24→0，exit1→exit0**；真实seed1定向前后原25节点无删除/判定
变化，12个FAIL全部保留。INT041/059观察适配已推进至下一层真实阻挡，**尚未闭环**；
21gap及公开target/perfMeta不可观测义务保持，仍为**NOT_CERTIFIED**。

**2026-11-03 新基线适配交付**：当前默认 `public-a0c2a26cb` 的 guard 输入与 MainBTB
第五训练槽/学习语义更新见[版本差分与验收记录](docs/spec/verification/evidence/runs/baseline-update-a0c2a26cb.md)。
十 DUT 新构建与独立冒烟均通过；完整 seed1 为 **40930 PASS / 1687 FAIL / 5 ERROR /
7 SKIP / 3 XFAIL**，受影响关键链同源码 seed1/2 各 **834 PASS**。构建、纯自检、功能、
覆盖和历史非 PASS 分开报告，不继承旧版 PASS，也不把本次适配写成硬件全绿。

在此基础上的[输入/历史 × 输出结果矩阵扩展](docs/spec/verification/coverage/io-matrix-extension-20261103.md)另行
登记来源、输入域、实际 reached/checked、错误响应控制和 gap；前轮完整42632项是当时
冻结源码的结果，不自动变成本轮新增场景的完整回归。

## 工程与运行

验证源码统一从 [`testbenches/`](testbenches) 进入：每个 DUT 的实现和用例放在
`testbenches/<dut>/`；[shared](testbenches/shared/README.md) 存放确实共用的组件和
它们的自检，采用相同的 env、transactions、model、checker、coverage、tests 职责。
小职责用文件，复杂后再展开为包。具体边界见[目录职责](docs/guides/repository-layout.md)。

包含 10 个独立 DUT，统一使用 toffee。与其他公开工程共用 DefaultConfig 完整香山 RTL，再提取各模块闭包供 Picker 构建；不单独 elaboration BPU 或注入 Scala 入口。整芯片优化可能裁剪原独立顶层端口，旧用例的接口适配仍在进行。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
./scripts/ucv prepare bpu --rtl-source release
./scripts/ucv build bpu --jobs 4
./scripts/ucv run bpu --workers 4
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。
`ucv` 会提前注册分区选项；无显式路径时使用工程默认测试根。选择一个 DUT 使用
`--dut mbtb`，它要求该 DUT 的构建，默认选择其测试和 `shared/tests`；显式 pytest
路径仍限定实际选择。每次使用新的输出目录。
领域模型与检查器保留在本工程，历史缺陷见[问题报告](docs/bugs/README.md)，功能合同见
[验证合同](docs/spec/verification/contracts)；功能点与未证明范围从
[验证规格](docs/spec/verification/README.md)进入所属正文。

整芯片 DefaultConfig 的 `Bpu` 导出会DCE掉未被FTQ消费的 prediction target 和 perfMeta；
当前事务显式保留 `None`/valid-only 观察边界，不伪造字段。metadata没有ready输入；SDK
协议适配使用只读常量，不能进入driver所有权。依赖被裁字段的场景不能借组件DUT结果签核。
`testbenches/bpu/tests/framework/test_defaultconfig_dimensions.py`自检声明的4-way MainBTB、MicroTAGE
5/9两表和8-table TAGE/SC参数，并核对真实生成schema的公开投影及MainBTB槽数；它不证明
内部八张表的完整配置/语义都已验证。上面的历史完整回归已执行；旧 MinimalConfig 场景的迁移
债务和未确认根因保留，具体逐项结论以版本报告及证据索引为准。

PHR的当前物理投影、输入UID/fire/flush账本、收尾及给定输入流后的独立模型边界见
[PHR事务合同](docs/spec/verification/contracts/phr-transaction-contract.md)。PHR输入target的比较不是被DCE的公开BPU
target证据；旧52-cell/19-fold/flag描述不用于认证当前532-cell/33-fold value-only合同。

自主流水的20组lookup fold、真实训练沿前接受、4-way加victim metadata投影及精确原
owner计划见[流水事务合同](docs/spec/verification/contracts/pipeline-transaction-contract.md)。当前只将既有模型
与真实ABI接通，不宣称全BPU组合、短/长来源程序或MBTB写回清理已经全部完成。

MainBTB的四路owner计划、真实零tag、50/49位半字地址边界、嵌套只读metadata及有界
checked-close见[MainBTB事务合同](docs/spec/verification/contracts/mbtb-transaction-contract.md)。
旧基线 `public-893e1580b` 的完整 cleanup/训练账本数字保留在
[历史合同原文](docs/spec/verification/evidence/reviews/mbtb-transaction-contract-893e1580b.md)，
不重标为当前结果；当前基线的逐输入/训练来源账本及其余生命周期仍在审计，真实功能
FAIL不改为期望或豁免。
