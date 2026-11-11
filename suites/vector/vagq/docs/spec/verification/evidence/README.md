# VAGQ 外部证据入口

VAGQ 使用 internal 源码和运行环境；按仓库约定，internal 源码、生成产物以及包含 internal
源码的证据**不复制到公共仓库**。本目录只说明如何访问外部复盘和历史运行，不保存这些
材料本身。

## 外部复盘

根 [经验索引 VAGQ 外部证据](../../../../../../../docs/lessons/README.md#vagq-external-evidence)
指向以下历史文件（`history://` 由本机外部历史工作区解析）：

- `history://vagq/results/vagq-xfail-contract-review-20261018-v1/README.md`：XFAIL 逐项复核。
- `history://vagq/results/vagq-exhaustive-review-20261020-v1/README.md`：失败分类与覆盖边界。
- `history://vagq/results/vagq-reference-repair-rtl-rereview-20261020-v2/README.md`：参考修正与 RTL 重新复核。

这些文件的 SHA-256、大小与导入时可用性记录在根 `docs/history/evidence/vagq.jsonl`，
分片哈希见根 `docs/history/evidence-index.json`。本次文档整理没有重新打开或复制这些证据。

## 本仓库保留的公开记录

- 运行/判定以项目 `results/` 目录中的收据为准（忽略目录，不随 Git 发布）；最近记录
  引用见 [Verification spec](../README.md)。
- 可公开的验证代码、场景矩阵、参考模型和测试在 `vagq/`、各组件目录和 `tests/`。
- `manifest/source-contract.json` 只保存源码/RTL 哈希、范围说明和迁移说明，不含 internal
  源码正文。
- 当前问题状态见 [bugs/](../../../bugs/README.md)；历史问题台账不在本仓库另建副本。

## 使用限制

- 外部证据必须在具备 internal 来源的本机环境中按 `history://` 解析；公共仓库中的引用
  不代表当前环境已复现。
- 引用外部报告时保留原日期、基线、用例集合和结论边界；不能把外部 PASS 迁移到当前
  internal 基线或公开工程。
- 需要比对 internal 源码或波形时，应使用外部工作区和独立访问控制，不在本目录生成副本。
