---
name: rtl-verification-soundness
description: RTL 验证执行与复核方法的兼容导航。按阶段和具体问题选择独立方法文件，说明如何构造合法激励、建立独立 oracle、实现 checker/活性检查、归因失败与审计证据；历史案例保存在 docs/lessons。
---

# 执行与复核方法入口

这里只导航，不再拼接完整手册。可执行正文采用 `skills/<阶段>/<问题>.md`，每篇独立说明准备、步骤、产出和验收。

| 要做的事 | 读取方法 |
|---|---|
| 组织验证包、driver/monitor 分层和测试边界 | [包结构与分层](../execution/package-layout.md) |
| 构造合法且实际到达 DUT 的输入 | [合法激励](../execution/legal-stimulus.md) |
| 推导独立答案并选对抽象层级 | [独立 oracle](../execution/independent-oracle.md) |
| 实现比较器、同拍采样、账本和自检 | [checker 与运行时](../execution/checker-and-runtime.md) |
| 定位失败、验证修复和绑定证据 | [归因与证据](../review/triage-and-evidence.md) |

需求到实现的设计方法见 [设计问题索引](../verification-completeness/SKILL.md)；全部入口见 [skills 索引](../README.md)。原十二类案例及历史建议已原文保留在 [案例文档](../../docs/lessons/rtl-verification-soundness-20261026.md)，不是本次新增运行结果。
