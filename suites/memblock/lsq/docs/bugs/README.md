# LSQ 问题记录

本目录记录 LSQ 验证中确认的 RTL/接口/参数问题。目录决定当前状态：`open/` 为仍需处理或未在当前基线复验的问题，`closed/` 为已给出处置结论的问题。旧错误包和运行证据在 [evidence/](evidence/)。

正式记录使用稳定 ID；每个文件开头的 ```ucv-bug``` JSON 块给出机器可读状态、基线和证据。正文保留现象、预期依据、复现/对照、根因和适用范围。历史报告的日期、基线、FAIL 和结论边界不因迁移改写。

当前 `closed/` 的 `FWD-SQID-001`、`LRQ-STRICT-001` 依据 `docs/history/lsq-regression-a0c2a26cb-20261102.json` 的 `public-a0c2a26cb` 完整回归记录（对应节点 FAIL→PASS）和进入基线的上游提交；旧基线版本仍为 open，旧报告不删除。本次文档整理未重跑 native。


<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（17）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [DEQ-FINISH-ORDER-001](open/DEQ-FINISH-ORDER-001.md) | 第二head的NC/IO handleFinish被无身份PopCount加入释放计数，能越过未消费旧普通项提前释放其SQ所有权 | rtl | 未解决 | — |
| [DEQ-SPLIT-WLINE-001](open/DEQ-SPLIT-WLINE-001.md) | 普通跨16B store尾段的wline错误继承相邻CBO.zero字段，即使相邻项未committed仍输出整line写控制 | rtl | 未解决 | — |
| [DEQ-WB-001](open/DEQ-WB-001.md) | CBO Cache响应的denied/corrupt在writeBack背压等待一拍后被无条件清零，实际ready/valid消费时也丢失异常7/19 | rtl | 未解决 | — |
| [DEQ-ZERO-001](open/DEQ-ZERO-001.md) | CBO.zero处于writeZero时，旧普通store的Sbuffer fire可被误当自己的零写，随后WB并释放SQ但没有零写副作用 | rtl | 未解决 | — |
| [FWD-ALIAS-001](open/FWD-ALIAS-001.md) | 年轻store经VA别名跨16B覆盖load字节时，VA相对重叠域漏掉其PA命中，返回更老store值且全部重放/依赖标志为0 | rtl | 未解决 | — |
| [FWD-RANGE-001](open/FWD-RANGE-001.md) | 跨16B store的mask旋转在单候选时把另一段字节折回本段未写地址，未要求重放或等待 | rtl | 未解决 | — |
| [IWL-UQ-SECOND-PAGE](open/IWL-UQ-SECOND-PAGE.md) | 跨页 Store 第二页在第一页写出后离开 UQ，年轻 Load 可无阻塞读到旧值 | rtl | 未解决 | — |
| [LQU-MMIO-IF-001](open/LQU-MMIO-IF-001.md) | 多个MMIO selector有效时所有selector收到共同ready，只有高ID输出总线，低ID也进入等待响应而丢失其请求 | rtl | 未复验 | — |
| [LQU-SID-001](open/LQU-SID-001.md) | 已回包但未消费的旧entry保留slaveId有效，合法重用该sid的新response覆盖旧数据/错误 | rtl | 未解决 | — |
| [LSQ-BUS-OWNERSHIP-001](open/LSQ-BUS-OWNERSHIP-001.md) | NC outstanding期间旧Load响应无身份清除后来IO Store的串行占用，Store尚欠自身响应就提前暴露下一Load请求 | rtl | 未解决 | — |
| [LSQ-UPSTREAM-6229](open/LSQ-UPSTREAM-6229.md) | 真实 mask 只覆盖部分字节时被当作完整覆盖，缺失字节未重放 | rtl | 未解决 | — |
| [LSQ-UPSTREAM-6634](open/LSQ-UPSTREAM-6634.md) | 多个 Uncache 异常候选按物理槽顺序仲裁，正常完成可遮挡真实故障 | rtl | 未解决 | — |
| [LSQ-UPSTREAM-6688](open/LSQ-UPSTREAM-6688.md) | ColdDownThreshold=0 会禁用 Replay，现有参数断言未拒绝 0 | spec | 未复验 | — |
| [LSQ-UPSTREAM-6704](open/LSQ-UPSTREAM-6704.md) | 跨 16B Store 首包已接受、尾包未到窗口内 Load 读到旧值 | rtl | 未复验 | — |
| [LSQ-UPSTREAM-6714](open/LSQ-UPSTREAM-6714.md) | 已退休的 MDP 等待目标仍被误判越域，Load 保持地址依赖 | rtl | 未解决 | — |
| [RAR-REL-001](open/RAR-REL-001.md) | 孤立release的valid比地址多延迟一拍，导致前拍窗口漏报和过期窗口误报 | rtl | 未解决 | — |
| [VSQ-REDIR-IF-001](open/VSQ-REDIR-IF-001.md) | 同拍dispatch与redirect的接口边界中，entry写入被禁止但虚拟tail仍计入新请求，恢复返回被取消的旧end而非幸存end | rtl | 未复验 | — |

## 已关闭（2）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [FWD-SQID-001](closed/FWD-SQID-001.md) | load越过physicalUpper且跨到新SQ generation时，低年龄段缺数据依赖错误沿用load flags，返回错误store epoch | rtl | 已处置 | fixed |
| [LRQ-STRICT-001](closed/LRQ-STRICT-001.md) | 没有真实入队的lane仍可能按schedIndex或不可用allocateSlot清除活动strict，导致地址ready位使严格依赖提前重放 | rtl | 已处置 | fixed |

<!-- ucv:bugs:end -->

## 旧证据

- [2026-10-22 错误包](evidence/bug-reports-20261022/)：11 个旧根因、4 个关系核验新增根因、1 个配置问题及误报/同源复核。
- 机器可读清单仍保留在 [`manifest/known-issues.json`](../../manifest/known-issues.json)；问题目录是当前状态入口。
