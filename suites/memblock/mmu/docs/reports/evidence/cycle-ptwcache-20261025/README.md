# PtwCache 覆盖闭环证据（2026-10-25）

本目录保存 PtwCache 独立叶级验证的前/后 compact 审计。完整 run 与覆盖数据库在
`results/ptwcache-final-02`（50 PASS，`state=committed`，`coverage_complete=true`）。

| 时点 | run | 用例 | 行覆盖 | branch | toggle | 功能 |
|---|---|---:|---:|---:|---:|---:|
| 首轮基线（重放） | `ptwcache-before-replay` | 24 | 11585/13748 = 84.267% | 2076/3226 = 64.352% | 60160/110892 = 54.251% | 100% |
| 中期 | `ptwcache-tests-08` | 44 | 13357/13748 = 97.156% | 2761/3226 = 85.586% | 70527/110892 = 63.600% | 100% |
| 中期 | `ptwcache-tests-09` | 45 | 13733/13748 = 99.891% | 3140/3226 = 97.334% | 70837/110892 = 63.879% | 100% |
| 中期 | `ptwcache-tests-10` | 47 | 13733/13748 = 99.891% | 3142/3226 = 97.396% | 77298/110892 = 69.706% | 100% |
| **最终** | **`ptwcache-final-02`** | **50** | **13741/13748 = 99.949%** | **3179/3226 = 98.543%** | **87398/110892 = 78.814%** | **100%** |

说明：

- `ptwcache-before-replay` 用首轮 24 个用例在当前代码上重放，行/branch/toggle
  与首轮 `ptwcache-tests-03` 完全一致（84.2668% / 64.352% / 54.251%），因此
  `ptwcache-before-audit.json` 作为可复核的 before 端点。
- 中间 run 的目录在提取审计后按资源策略裁剪；表中数字来自当时
  `coverage_audit.py` 的审计输出。最终 run 保留完整 `coverage-audit.json`。
- 首轮 `ptwcache-tests-03` 的功能覆盖曾为 83.33%，原因是 stage 1/2 两个
  sample bin 未采样；后续用例补上 `stage` 采样后为 100%。replay 使用补采样后的
  首轮用例，因此功能为 100%，行/branch/toggle 仍与首轮一致。
- 覆盖分母包含 Picker harness 和 MBIST/SRAM 宏；`lcov_lines_dut_only` 按源文件
  分离；未覆盖项未删除或重算。残余分类详见
  [PtwCache 报告](../ptwcache-20261025.md) §5。

文件：

- `ptwcache-before-audit.json`：首轮 compact 审计（24 用例）
- `ptwcache-final-audit.json`：最终 compact 审计（50 用例）
- `ptwcache-final-functional.json`：最终功能覆盖原始 JSON
- 完整审计与数据库：`results/ptwcache-final-02/`
