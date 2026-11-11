# 结构整合阶段状态

更新于 **2026-11-11**。当前为十二工程、137 DUT、114 个 testbench 实现包的结构整合版。
公开工程使用 `public-a0c2a26cb` / DefaultConfig，VAGQ 使用外部
`internal-d4566d58a` / DefaultConfig；有效基线以配置和 `ucv list` 为准。

## 工程入口

具体功能范围、各基线结果和未解决问题由所属工程维护：

| 工程 | 规格与验证范围 | 问题汇总 |
|---|---|---|
| BPU | [工程资料](../suites/frontend/bpu/docs/README.md) | [问题](../suites/frontend/bpu/docs/bugs/README.md) |
| FTQ | [工程资料](../suites/frontend/ftq/docs/README.md) | [问题](../suites/frontend/ftq/docs/bugs/README.md) |
| ICache | [工程资料](../suites/frontend/icache/docs/README.md) | [问题](../suites/frontend/icache/docs/bugs/README.md) |
| IFU | [工程资料](../suites/frontend/ifu/docs/README.md) | [问题](../suites/frontend/ifu/docs/bugs/README.md) |
| IBuffer | [工程资料](../suites/frontend/ibuffer/docs/README.md) | [问题](../suites/frontend/ibuffer/docs/bugs/README.md) |
| InstrUncache | [工程资料](../suites/frontend/instr_uncache/docs/README.md) | [问题](../suites/frontend/instr_uncache/docs/bugs/README.md) |
| LSQ | [工程资料](../suites/memblock/lsq/docs/README.md) | [问题](../suites/memblock/lsq/docs/bugs/README.md) |
| DCache | [工程资料](../suites/memblock/dcache/docs/README.md) | [问题](../suites/memblock/dcache/docs/bugs/README.md) |
| MMU | [工程资料](../suites/memblock/mmu/docs/README.md) | [问题](../suites/memblock/mmu/docs/bugs/README.md) |
| Sbuffer | [工程资料](../suites/memblock/sbuffer/docs/README.md) | [问题](../suites/memblock/sbuffer/docs/bugs/README.md) |
| LSU | [工程资料](../suites/memblock/lsu/docs/README.md) | [问题](../suites/memblock/lsu/docs/bugs/README.md) |
| VAGQ | [公开资料与外部证据](../suites/vector/vagq/docs/README.md) | [问题](../suites/vector/vagq/docs/bugs/README.md) |

## 当前结构

十二工程均使用 workspace schema2：DUT 实现与测试在 `testbenches/<dut>/`，实际跨 DUT
复用的组件在 `testbenches/shared/`，双方同用六职责。参数化 DUT 显式共用实现；
工程根唯一 `conftest.py` 注册 fixture/插件，离线审计与汇总在 `tools/`。

`ucv init` 生成骨架，`ucv docs --write` 生成 DUT/shared 工作入口，`ucv check` 校验
布局与关联。公共工具保留 schema1 兼容。规格、功能要求与问题的维护位置见
[目录规范](reference/module-layout.md)和[文档维护](how-to/maintain-docs.md)。

## 最近一次结构验收

以下结果属于 **2026-11-10 testbenches 迁移**，各项选择范围分别保留：

| 检查 | 结果与范围 |
|---|---|
| 十二工程收集对账 | **49,782 项**，无增删；路径/fixture 搬迁归一后参数、标记、fixture 一致，BPU 原生分区不变 |
| 公共工具 | 根回归 **287 PASS**；最终相关接线复验 **74 PASS**，与前项重叠 |
| 结构与资产 | `ucv check full`、布局 `--strict`、Skill/framework、Git 资产审计和 `git diff --check` 通过 |
| BPU 定向自检 | **996 PASS / 3 FAIL**；三项失败在冻结的迁移前源码中重现。最后混合自检拆分后的 **105 PASS** 与前项重叠 |
| BPU 原生检查 | MainBTB、MicroRAS 按新配方真实构建及冒烟通过，各自选跑 **2 PASS** |
| 严格事务边界 | **exit 1**；DCache、LSQ、LSU、MMU、VAGQ 存在待审查的引脚/信号/环境内部访问 |

BPU 三项定向失败分别涉及依赖拒绝错误文本、项目与 Toffee CI 的 xcomm 锁差异、
short-revisit 合同几何差异。该选择未覆盖此前全部失败，未覆盖项不视为已修复。
BPU 仍有 11 个开放问题，原生选跑报告为 `hardware_verdict=INCOMPLETE`。

事务检查是保守的源码扫描，命中数不是硬件缺陷数，也不是待改用例数；
其中既有功能用例的真实底层耦合，也可能包含编码自检等需要分类的条目。
含义、实例和处理方式见[如何理解事务边界检查](maintenance.md#如何理解事务边界检查)。

## 当前事务适配

五工程事务修复的**已审查范围完成适配验收**，不是五工程硬件全绿。LSU 的
`load_s4` / `new_load_unit` 已完成独立适配验收：
原 50 项、4516 个驱动/采样事件保持一致；新输入边界自检通过。当前基线统一选跑为
**56 PASS / 3 FAIL**，三个既有失败保留；未据此验收其余 17 个 LSU DUT。
VAGQ 的已审查事务适配通过：10 DUT 当前构建/冒烟通过；本拍/下一拍 ready 调用问题
修复后定向 **48 PASS / 1 SKIP**，`hardware_verdict=INCOMPLETE`。旧 MaskGen 失败、
8 项缺历史证据与其余未验证义务保留，未执行最终全 476 项统一回归。
MMU 旧基线事务保全及压力刺激反例已闭合；16 DUT 当前构建/冒烟与身份核验通过。
当前 16 DUT 统一 **421 PASS**，最后 loader 修补定向 **21 PASS**、种子兼容 **83 PASS**；
旧权限对照 **5 PASS / 2 FAIL** 保留。MMU 已审查适配通过，硬件仍 INCOMPLETE，PMP 未选。
DCache 已审查适配通过：当前 8 DUT 完整 **162 PASS / 3 XFAIL**，统一入口定向
**20 PASS / 3 XFAIL**；原 37 项判定保全，必要时序修正单列，硬件仍 INCOMPLETE。
LSQ 由主 agent 接手，未更换或重试子 agent 模型；**已审查适配范围通过**。七族及
LoadUncache 的刺激账本、Wrapper typed 消费及历史 checker 生命周期已修复；原模型
函数无修改或删除。十族原 711 项判定保全 **665 PASS / 46 FAIL**；Replay 时序返修后
原 150 PASS，完整共有 Journal 和两 seed 输入/输出一致。四父级 96 项判定保全
**81 PASS / 15 FAIL**；最终定向字段/byte-mask/相位对账及原反例返修分别留证。
20 个受影响 DUT 的当前 key、完整基线、active 路径、100 native 文件与 164 RTL
引用核验通过。最后统一入口为 **87 PASS / 3 FAIL**（原功能 65/3，22 自检 PASS）；
随后只修 Deq 一处原未指定 valid 的过约束，全 4 原参数仍 **4 FAIL**，原 wline 反例和
断言域保留。各选择重叠不累计，源码运行期间稳定；硬件汇总保持 **FAIL**。
最近接手集成检查点根 **289 PASS**，资源/结构/技能/资产/空白检查及公开集合统一基线
核对通过；严格事务仍 **exit 1**，仅报串行场景原有 `io_load`/`io_store` 类别标签的
3 个字面量。已核对它们不是真实端口名、原参数值不变，不改扫描器或参数来消除。
最后 collection 为 2608（原 2600 无删除，8 适配自检新增），原参数/标记保留，7 个
fixture 来源搬迁单列。未执行 LSQ 全 2608 项/全部 38 DUT 功能与覆盖验收；适配接受
不扩大为未选择的 18 DUT 或硬件签核。最后源码、保护审计及限定接受依据单列存储。
逐项证据与交付审查保存在 `results/transaction-adapters-20261110/`。

## 未完成范围与证据

- BPU 完整适配与生产回归、各工程开放问题及观察/集成缺口仍需按所属合同处理。
- 本轮未执行 137 DUT 全量原生回归、统一空缓存全链路验收及完整覆盖闭环；
  整体迁移验收仍为 **NOT_CERTIFIED**。
- ICache 清理的 249 个旧 bytecode 未保留逐文件删除清单，原文件已不可用；
  源码快照完整，这一清理审计缺口保留。

本轮完整命令、种子、日志、源码快照及逐项对账在本机
`results/testbenches-all-20261110/` 与 `results/testbenches-bpu-20261110/`。
历史结果从所属工程规格/问题记录、[经验索引](lessons/README.md)及
[历史证据索引](history/evidence-index.json)进入，沿用各自日期、基线与判定。
本页只维护当前摘要，逐轮进度与旧结果不再重复追加。
