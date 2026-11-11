# LSQ 历史证据索引

本目录保存 LSQ 的历史报告和迁移前说明，供追溯，不代替当前验证结论。

- [reports/](reports/)：2026-10-18 至 2026-11-06 的模块/阶段/上游审计报告。每篇保留原日期、基线、选择范围、真实 FAIL 和结论边界。
- [legacy-readme.md](legacy-readme.md)：迁移前的工程总说明，含旧路径和旧状态；只作历史阅读。
- [../plan.md](../plan.md)：当前验证范围、层次、顺序和完成条件。
- [plan-progress-20261018-20261019.md](plan-progress-20261018-20261019.md)：原 `spec/verification/plan.md` 的逐轮进度和旧里程碑（旧基线 `893e1580…`、旧根 `memblock-hash/lsq/`）；当前计划见 `../plan.md`。
  冻结报告中的旧 `plan.md` 相对链接按原路径保留；旧计划内容以本文件为准，不能按当前 `plan.md` 重读旧结论。
- [../../../bugs/evidence/](../../../bugs/evidence/)：2026-10-22 错误包和同源复核。

2026-11-09 的文档整理没有运行 native；本目录未复制运行产物，也未把旧结果改写成当前通过。历史 baseline（如 `XiangShan 893e1580…`）与当前 `public-a0c2a26cb` 的结论不能直接合并。
历史报告中指向 `results/`、`review/` 的链接是当时本机证据路径；Git 不保存这些大目录，迁移后可能不可点击。报告正文和判定仍是有效历史记录。
