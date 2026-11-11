# VAGQ 问题记录

本目录保存 VAGQ 工程的稳定问题 ID。**open/closed 目录表示当前处理状态**，正文和
`ucv-bug` JSON 中的 `versions` 保留各 internal 基线的结论与证据边界。

- VAGQ 使用 internal 来源；不复制 internal 源码、生成产物或包含 internal 源码的证据。
  外部复盘和历史运行通过根经验索引的外部入口访问。
- 当前没有已关闭条目。显式 campaign 的 SKIP 不是通过；真实 FAIL 不登记 XFAIL、不删除
  反例、不用“失败数量符合预期”改判。
- 修复或重新分类后，确认对应测试/外部证据仍可读，再运行
  `./scripts/ucv docs vagq --write` 刷新自动索引。

相关问题背景见 [Verification spec](../spec/verification/README.md) 与
[外部证据说明](../spec/verification/evidence/README.md)。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`internal-d4566d58a`。未复验项不继承历史通过结论。

## 未解决（2）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [VAGQ-MASKGEN-ELEMENT-WINDOW-56](open/VAGQ-MASKGEN-ELEMENT-WINDOW-56.md) | MaskGen 元素窗口策略保留 56/9024 个 native policy mismatch | investigation | 未解决 | — |
| [VAGQ-SPARSE-SEGMENT-MASK-CANARY](open/VAGQ-SPARSE-SEGMENT-MASK-CANARY.md) | 稀疏 v0 字节掩码下 segment 元素归属仍保留反例 | rtl | 未复验 | — |

## 已关闭（0）

暂无登记条目。

<!-- ucv:bugs:end -->
