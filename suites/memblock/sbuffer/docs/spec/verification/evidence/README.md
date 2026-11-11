# Sbuffer 验证证据索引

本目录保存 Sbuffer 工程的历史运行、合同复核和审计报告。文件保留原日期、源码/RTL
基线、工具版本、运行目录和结论边界；迁入本目录不改变原判定，也不表示当前基线已复现。

## 功能与覆盖

- [sbuffer-data-20261024.md](sbuffer-data-20261024.md)：SbufferData 字节级存储/掩码语义 UT。
- [sbuffer-top-20261024.md](sbuffer-top-20261024.md)：Sbuffer 顶层入队/写出/排空/转发 UT。
- [coverage-loop-20261024.md](coverage-loop-20261024.md)：两层覆盖率闭环、逐项缺口归因和补例记录。

## 合同与独立复核

- [flush-contract-review-20261024.md](flush-contract-review-20261024.md)：CMO/fence 两级空语义复核；结论为非缺陷。
- [independent-audit-20261024.md](independent-audit-20261024.md)：对验证结果和用例的独立复核。
- [bug-recheck-20261024.md](bug-recheck-20261024.md)：对独立审核发现的二次裁决，区分假通过、helper 缺口和真实 RTL 问题。
- [legacy-readme.md](legacy-readme.md)：迁移前工程说明，保留历史目录、工具和证据边界。

## 使用说明

- 报告中的 `results/<name>`、`manifest/`、`tools/` 路径按工程根解释；旧 `sbufferverify/`、`rtl/`、`dut/` 目录属于当时结构。
- 历史数字只属于其源码/RTL 基线、构建和 seed；当前默认基线未重新运行前，不把历史 PASS/FAIL 迁移到当前版本。
- 当前问题状态以 [bugs/](../../../bugs/README.md) 的 open/closed 目录为准；`manifest/known-issues.json` 是迁移来源和历史台账。
