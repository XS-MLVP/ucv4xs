# DCache 验证证据索引

本目录保存 DCache 工程的历史运行、审计和阶段报告。文件保留原日期、源码/RTL 基线、
工具版本、运行目录和结论边界；迁入本目录不改变原判定，也不表示当前基线已复现。

## 顶层与交付

- [dcache-top-20261024.md](dcache-top-20261024.md)：DCache 顶层早期 UT 报告；其中旧结论已被后续报告更正，阅读时以文件内说明为准。
- [dcache-top-20261025.md](dcache-top-20261025.md)：DCache 顶层 12 个功能点、用例映射与覆盖率归因。
- [dcache-wrapper-20261025.md](dcache-wrapper-20261025.md)：DCacheWrapper 结构事实、WFP-001..007、回放与覆盖率。
- [coverage-20261025.md](coverage-20261025.md)：总覆盖率报告，含逐 DUT 分母、缺口分类和证据索引。
- [delivery-selfcheck-20261025.md](delivery-selfcheck-20261025.md)：交付自检，含基线、哈希、构建、trace、未关闭项。
- [p0-closure-20261026.md](p0-closure-20261026.md)：P0 收口，确认 1 个 RTL 缺陷、关闭 4 项并记录无复位流水发现。
- [soundness-recheck-20261026.md](soundness-recheck-20261026.md)：用例可信度复核，记录 11 处验证缺口、修正和注错对照。
- [functional-point-audit-20261025.md](functional-point-audit-20261025.md)：功能点与 RTL/模型/断言一致性复核。
- [status-20261024.md](status-20261024.md)、[status-20261025.md](status-20261025.md)：阶段状态快照。
- [legacy-readme.md](legacy-readme.md)：迁移前工程说明，保留历史目录、工具和证据边界。

## 逐 DUT 报告

- [duplicated-tag-array-20261024.md](duplicated-tag-array-20261024.md)
- [ctrl-unit-20261024.md](ctrl-unit-20261024.md)
- [miss-ready-gen-20261024.md](miss-ready-gen-20261024.md)
- [counter-filter-20261024.md](counter-filter-20261024.md)
- [miss-track-20261024.md](miss-track-20261024.md)
- [load-pipe-20261024.md](load-pipe-20261024.md)
- [banked-data-array-20261024.md](banked-data-array-20261024.md)
- [main-pipe-20261025.md](main-pipe-20261025.md)
- [miss-queue-20261025.md](miss-queue-20261025.md)
- [writeback-probe-20261024.md](writeback-probe-20261024.md)：WritebackQueue 与 ProbeQueue 合并报告。
- [p1-leaf-closure-20261024.md](p1-leaf-closure-20261024.md)：叶块闭环汇总。

## 使用说明

- 报告中的 `results/<name>`、`manifest/`、`tools/` 路径按工程根解释；`../../soc-split` 等旧路径属于当时工作区。
- 历史数字只属于其源码/RTL 基线、构建和 seed；当前默认基线未重新运行前，不把历史 PASS/FAIL 迁移到当前版本。
- 当前问题状态以 [bugs/](../../../bugs/README.md) 的 open/closed 目录为准；`manifest/known-issues.json` 是迁移来源和历史台账。
