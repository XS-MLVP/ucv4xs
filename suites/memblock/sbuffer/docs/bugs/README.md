# Sbuffer 问题记录

本目录保存 Sbuffer 工程的稳定问题 ID。**open/closed 目录表示当前处理状态**，正文和
`ucv-bug` JSON 中的 `versions` 保留各基线的结论与证据；历史修复不自动迁移到当前版本。

- 已修复但未在当前默认基线复验的条目仍留在 `open/`，并在正文说明历史证据范围。
- `closed/` 只用于已经完成处置的问题：历史误报（`invalid`）、重复（`duplicate`）或
  确实退役的设计/接口（`retired`）。`invalid` 只关闭历史误报分类，正文和 `versions`
  仍标明当前默认基线未复验。
- 范围、资源或既有合法输入域约束不放在本目录；稳定 ID、说明和原依据见
  [verification/constraints.md](../spec/verification/constraints.md)。
- 历史台账 [manifest/known-issues.json](../../manifest/known-issues.json) 仅作为迁移来源和旧记录证据；当前状态以本目录为准。

功能点、用例和覆盖缺口的关系见 [Verification spec](../spec/verification/README.md)。
修复或重新分类后，确认对应测试/证据仍可读，再运行
`./scripts/ucv docs sbuffer --write` 刷新自动索引。不要通过修改期望、增加豁免或删除
反例来关闭问题。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（5）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [PICKER-DEFAULT-DUMPFILE](open/PICKER-DEFAULT-DUMPFILE.md) | Picker 默认 dump 已在旧基线验证隔离，当前基线未复验 | verification | 未复验 | — |
| [SBD-SAME-LANE-PORT-HALVES](open/SBD-SAME-LANE-PORT-HALVES.md) | SbufferData 高槽同一 lane 的另一半字节端口路径未覆盖 | verification | 未复验 | — |
| [SBD-TIME0-INIT](open/SBD-TIME0-INIT.md) | SbufferData initial 的 if(reset) else 分支不可由运行期激励到达 | verification | 未复验 | — |
| [SBT-SAMEBLOCK-SLOT-SWEEP](open/SBT-SAMEBLOCK-SLOT-SWEEP.md) | 同块 inflight 时 follower 高槽插入路径未全部激活 | verification | 未复验 | — |
| [SBT-TOGGLE-RESIDUAL](open/SBT-TOGGLE-RESIDUAL.md) | Sbuffer 顶层 toggle 82.0% 的剩余点分类与补例计划 | verification | 未复验 | — |

## 已关闭（1）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [FLUSH-EMPTY-TWO-LEVELS-REVIEWED](closed/FLUSH-EMPTY-TWO-LEVELS-REVIEWED.md) | CMO 期间 flush.empty 受 sqempty 门控是两级空语义，不是缺陷 | investigation | 未复验 | invalid |

<!-- ucv:bugs:end -->
