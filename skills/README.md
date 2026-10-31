# ucv4xs Skill 索引

**方法按 `skills/<阶段>/<问题>.md` 维护，案例放在 `docs/lessons/`。** 每篇方法须说明适用场景/输入、怎么做、产出和如何验收，不只是提问“是否完整”。阶段是导航，不是割裂职责：复核发现问题时应回到设计或执行补齐。

## 按阶段和问题选方法

| 阶段 | 问题与方法 |
|---|---|
| 设计 | [如何定义需求和 DUT 边界](design/requirements-boundary.md) |
| 设计 | [如何检查观察点精度与未证明义务](design/observation-precision.md) |
| 设计 | [如何划分行为等价类和关键组合](design/behavior-equivalence.md) |
| 设计 | [如何把功能点实现为测试](design/traceability-and-implementation.md) |
| 设计 | [如何制定退出标准和处置残余](design/closure-and-residuals.md) |
| 执行 | [如何组织验证包的 driver/monitor 分层](execution/package-layout.md) |
| 执行 | [如何构造合法激励](execution/legal-stimulus.md) |
| 执行 | [如何建立独立 oracle](execution/independent-oracle.md) |
| 执行 | [如何实现 checker、并发采样和完成性检查](execution/checker-and-runtime.md) |
| 复核 | [如何归因失败并审计证据](review/triage-and-evidence.md) |

## 怎么使用与积累

1. 按当前问题读取对应文件，而不是先读两个大手册。新模块从需求/边界和实现追溯开始。
2. 按步骤实施，留下实际工件与正负对照；未执行的检查标待执行，不把模板填写或文档整理当验证通过。
3. 到 [案例索引](../docs/lessons/README.md) 查错误决策、修正依据及证据边界；不要复制不适用的模块假设，也不要借用历史 PASS 数。
4. 新案例保留原问题、错误假设、反例、修正与未证明范围；可迁移的操作只更新对应问题方法，并双向链接，避免重复维护正文。

## 待审核方法

下列文件由本轮依赖升级与布局重构总结，尚未经过维护者审核；可试用，但不替代正式方法：

- [依赖升级与能力核对](pending/dependency-upgrade-and-capability-audit.md)
- [Fixture 集中与 agent 边界](pending/fixture-consolidation.md)
- [框架能力选型](pending/framework-capability-selection.md)
- [迁移边界复核：端口别名不等于事务抽象](pending/pin-schema-and-suite-migration.md)

审核通过后再移入对应阶段目录并更新上表。

## 项目工作流与兼容入口

- [ucv4xs-workflow](ucv4xs-workflow/SKILL.md)：仓库基线、构建、回归和工程接入，沿用现有入口。
- [verification-completeness](verification-completeness/SKILL.md)：仅导航到设计问题文件，不再维护独立大手册。
- [rtl-verification-soundness](rtl-verification-soundness/SKILL.md)：仅导航到执行/复核问题文件。
- [旧速查卡入口](rtl-verification-soundness/CARD.md)：历史 P01–P12 到现行方法的对照，不复制正文。

两个旧名称仅为兼容导航，不是两个必须串读的主体。带 frontmatter 的入口可按路径读取；文件存在不代表已向客户端注册或自动加载。协作与验收以 [AGENTS.md](../AGENTS.md) 和 [维护约定](../docs/maintenance.md) 为准。

## 格式与有效性核对

```sh
.venv/bin/python scripts/audit-skills.py --strict --check-framework
```

检查格式、项目命名约定、引用和框架入口，不等于安装、自动发现或内容审批。当前
三个 SKILL.md 为仓库入口，十三篇为支持文档，四篇 pending 为未审批草稿；未把草稿
隐式注册到客户端。复核发现的错误方法和目录取舍见
[2026-10-31 复核](../docs/lessons/structure-skill-review-20261031.md)。

这是项目内容分类，不是客户端发现清单。V2 可把 source 根的平铺 .md 当成 skill，
不要不加筛选地将整个 skills/ 或 pending/ 配为 source；README 可能被发现，阶段
子目录普通 .md 则不一定可发现。需要安装时应逐个明确正式入口，保持草稿未启用。
