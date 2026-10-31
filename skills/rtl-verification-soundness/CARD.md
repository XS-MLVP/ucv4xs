# 历史踩坑编号到现行方法的速查

这里只做导航。操作正文按 [阶段/问题](../README.md) 读取；历史问题、错误决策和原修正建议见 [十二类案例](../../docs/lessons/rtl-verification-soundness-20261026.md)。

| 历史编号 | 现行方法 |
|---|---|
| P01 生产者合法性 | [需求/边界](../design/requirements-boundary.md)、[合法激励](../execution/legal-stimulus.md) |
| P02 并发漏采 | [checker 与运行时](../execution/checker-and-runtime.md) |
| P03 过严比较与过宽放行 | [checker 与运行时](../execution/checker-and-runtime.md) |
| P04 同源 oracle | [独立 oracle](../execution/independent-oracle.md) |
| P05 身份、粒度、抽象层级 | [独立 oracle](../execution/independent-oracle.md)、[DUT 边界](../design/requirements-boundary.md) |
| P06 非区分性组合 | [行为等价类](../design/behavior-equivalence.md) |
| P07 取消副作用遗漏 | [checker 与运行时](../execution/checker-and-runtime.md) |
| P08 空跑和假完成 | [checker 与运行时](../execution/checker-and-runtime.md) |
| P09 collection、字段未受检 | [实现与追溯](../design/traceability-and-implementation.md)、[checker](../execution/checker-and-runtime.md) |
| P10 生成产物缺观察点 | [DUT 边界](../design/requirements-boundary.md)、[checker](../execution/checker-and-runtime.md) |
| P11 失败消失不等于根因明确 | [归因与证据](../review/triage-and-evidence.md) |
| P12 覆盖/归档齐备不等于语义完成 | [退出与残余](../design/closure-and-residuals.md)、[证据审计](../review/triage-and-evidence.md) |

这张表不是已执行检查清单，更不是新一轮硬件验收。
