# PTWRepeaterNB / PTWFilter 覆盖闭环证据（2026-10-24）

本目录保存两轮覆盖闭环的 compact 审计副本，完整 run 目录为：

- `results/ptwrepeater-06`（最终）
- `results/ptwfilter-final-16`（最终）

文件：

| 文件 | 内容 |
|---|---|
| `ptwrepeater-before-audit.json` | 首轮 `ptwrepeater-01`：行 72/72、toggle 1167/3114、branch 7/8 |
| `ptwrepeater-before-functional.json` | 首轮功能覆盖 83.33%（stage 0/1/3 缺） |
| `ptwrepeater-final-audit.json` | 最终 `-05`：行 72/72、toggle 3114/3114、branch 7/8 |
| `ptwrepeater-final-functional.json` | 最终功能覆盖 100% |
| `ptwfilter-before-audit.json` | 首轮 `ptwfilter-03`：行 206/206、toggle 1938/4414、branch 82/92 |
| `ptwfilter-before-functional.json` | 首轮功能覆盖 75%（stage 仅 0、issue_filtered 未覆盖） |
| `ptwfilter-final-audit.json` | 最终 `ptwfilter-final-16`：行 206/206、toggle 4411/4414、branch 91/92，14 PASS |
| `ptwfilter-final-functional.json` | 最终功能覆盖 100% |

审计文件是 compact 摘要：保留总分母、逐文件行覆盖统计、branch/toggle 总数；
未覆盖点的完整列表在最终 run 的 `coverage-audit.json` 中（或由 `coverage_audit.py`
从 run 的覆盖数据库重新生成）。PTWFilter 残余仅 3 个 toggle 点，属于并发响应/边界
情况枚举；本目录不保存波形或逐周期 dump。
