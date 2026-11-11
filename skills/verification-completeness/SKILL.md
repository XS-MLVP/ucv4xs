---
name: verification-completeness
description: 验证设计方法的兼容导航。按独立问题文件说明如何定义需求和 DUT 边界、构造行为等价类、实现激励/oracle/checker 的追溯闭环，以及制定退出标准与处置残余；不以完整性问卷替代实施方法。
---

# 验证完备性：设计什么、怎么做到、何时算完成

这里只导航，不再维护另一份大手册。可执行正文采用 `skills/<阶段>/<问题>.md`，讲清怎么做，而不只询问是否完整：

1. 如何从需求和真实层次定义 DUT 合同与责任边界。
2. 如何划分行为等价类并设计区分性组合。
3. 如何将需求实现为合法激励、独立答案、实际检查和运行证据。
4. 如何事先制定退出标准，并据证据处置未完成项。

## 每轮迭代的强制检查（不是问卷）

开始新一轮适配、增删用例或修改期望时，先回答下面四项，并把答案落成工程内可审计的产物；
任一项没有产物，本轮不得宣称功能覆盖有提升：

1. **来源映射**：每个能到达本 DUT 的指令/上游事务族，写清本层/出域（谁承接）/未证明。
2. **类别 × 结果域矩阵**：行是事务/行为类别，列是完成、故障、重放、refill、tag 错误、
   翻译 miss 等响应域；每格 `pass`/`fail`/`gap`/`na`/`out-of-domain`，`pass`/`fail` 附 nodeid，
   `gap` 写"缺什么 + 怎么补"。
3. **未分类项清单**：本轮新增但还没归类的输入、字段或组合，显式列出，不并入"其他"。
4. **可执行门禁**：矩阵落成可机读数据 + 自检，断言"新增类别没有对应行就失败"。
    只写在文档里的矩阵会在迭代中腐烂。

这四项以[模块行为清单与来源审查](../design/requirements-boundary.md)为起点，不能仅把
已有 ID 按 DUT/测试层级分组后认作需求全集。行为族、场景、参数实例与运行判定分别
记录；清单自检通过只证明资料一致性，不证明功能行为或场景覆盖闭环。

反例：2026-11-03 LSQ 的 8 类事务只覆盖干净完成，共享 actor 用恒 0 期望吞掉随机注入的
总线错误，2575 条用例全部 PASS 却漏掉 MMIO Store 故障上报；补上结果域后同一批种子出现
8 条 PASS→FAIL。见 [LSQ 目标矩阵](../../suites/memblock/lsq/docs/spec/design/contracts/kind-outcome-matrix.md)。

## 按问题读取

| 问题 | 文档 |
|---|---|
| 需求属于哪个 DUT、哪些行为移交上层？ | [`skills/design/requirements-boundary.md`](../design/requirements-boundary.md) |
| 内部字段宽于端口、消费者还需要更多位时怎么办？ | [`skills/design/observation-precision.md`](../design/observation-precision.md) |
| 不能穷举所有指令时，如何建立行为等价类？ | [`skills/design/behavior-equivalence.md`](../design/behavior-equivalence.md) |
| 功能点如何落成用例、oracle、checker 和持续门禁？ | [`skills/design/traceability-and-implementation.md`](../design/traceability-and-implementation.md) |
| 什么条件下可以闭环，哪些必须保留为残余？ | [`skills/design/closure-and-residuals.md`](../design/closure-and-residuals.md) |

## 与 soundness 的分工

- 设计方法给出应验证什么、怎样实现及如何验收；不以阶段划分阻止复核时回到设计。
- [执行/复核入口](../rtl-verification-soundness/SKILL.md) 导航到激励、oracle、checker、归因及证据的具体实施方法。
- `docs/lessons/`：保存真实案例和证据，不再定义第三套方法。

各问题文件须形成“适用场景/输入 → 操作步骤 → 产出 → 验收 → 案例”闭环。只写“应有用例”或勾选完整性不算实施。全部方法见 [阶段/问题索引](../README.md)。
