# BPU 问题报告

本目录记录 BPU 的 RTL 差异、验证差异和待核调查。问题的当前状态只看
`open/` 与 `closed/`：`open/` 是仍未证实修复的问题，`closed/` 只放有真实
处置依据的关闭项。历史基线结论、未复现范围和原证据保留在各篇正文中，不因
当前目录位置改变原判定。

- `open/`：现有 `BPU-BUG-01` 至 `BPU-BUG-10` 及待核调查。
- `closed/`：已按 `fixed`、`invalid`、`duplicate` 或 `retired` 关闭的问题。
- `evidence/`：输入合法性、历史失败归因和早期模块复核；不代表当前状态。

每篇 Markdown 开头有一个 ```ucv-bug 结构化块，记录稳定 ID、类型和各基线状态。
修复或关闭需要对应基线的复现、对照或设计结论；旧版已确认不自动等于当前默认
基线已确认。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（11）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [BPU-BUG-01](open/BPU-BUG-01-mainbtb-direction-counter-missing-tag.md) | MainBTB 把一条分支的反馈用于另一条分支的方向计数 | rtl | 未复验 | — |
| [BPU-BUG-02](open/BPU-BUG-02-microtage-nonconditional-learns-direction.md) | MicroTAGE 为同一位置的非条件跳转更新了条件分支学习 | rtl | 未复验 | — |
| [BPU-BUG-03](open/BPU-BUG-03-microtage-shadowbuffer-dirty-lost.md) | MicroTAGE 用过期槽号清掉了另一条分支的新学习 | rtl | 未复验 | — |
| [BPU-BUG-04](open/BPU-BUG-04-ras-spec-pushpop-ignores-enable.md) | RAS 禁用时仍处理推测调用 | rtl | 未复验 | — |
| [BPU-BUG-05](open/BPU-BUG-05-microras-ignores-enable.md) | MicroRAS 禁用后仍把旧返回地址标为可用 | rtl | 未复验 | — |
| [BPU-BUG-06](open/BPU-BUG-06-mainbtb-multihit-clear-wipes-survivor.md) | MainBTB 要求清理 way 1，写缓冲却从 way 0 写出了清零内容 | rtl | 未复验 | — |
| [BPU-BUG-07](open/BPU-BUG-07-ittage-unpublished-original-allocates.md) | ITTAGE 重启后接受了禁用期间那次预测的反馈 | spec | 未复验 | — |
| [BPU-BUG-08](open/BPU-BUG-08-microbtb-fallthrough-revives-dead-entry.md) | MicroBTB 因一次不跳转反馈重新给出跳转预测 | investigation | 未复验 | — |
| [BPU-BUG-09](open/BPU-BUG-09-aheadbtb-target-correction-wrong-destination.md) | AheadBTB 把不同分支的待写纠正合并，丢掉较早更新 | rtl | 未复验 | — |
| [BPU-BUG-10](open/BPU-BUG-10-return-and-call-treated-as-no-action.md) | RAS 和 MicroRAS 漏掉“返回并调用”操作 | rtl | 未复验 | — |
| [BPU-INV-UBTB-DISABLED-TAKEN-20261108](open/investigation-ubtb-disabled-taken-20261108.md) | 关闭预测器后 Bpu 仍发布 taken | investigation | 未解决 | — |

## 已关闭（0）

暂无登记条目。

<!-- ucv:bugs:end -->

## 阅读约定

- 先看正文的“怎样触发 / 已观察到的结果 / 上游输入审核 / 复现与对照”。
- 模块差异、输入合法和整条事件序列可由 SoC 产生是三件不同的事。
- 复现应保留真实 FAIL；修复后同时验证失败场景和通过的对照。
- 历史实测的日期、基线和结论边界不变，详见 [问题证据](evidence/) 与
  [验证运行记录](../spec/verification/evidence/runs/)。
