# VAGQ-SPARSE-SEGMENT-MASK-CANARY：稀疏 v0 字节掩码下的 segment 元素归属仍保留反例

状态：**已知限制，未复验修复，保留 open**。显式 canary
[tests/vagq/test_sparse_segment_canary.py](../../../tests/vagq/test_sparse_segment_canary.py)::test_sparse_segment_masks_preserve_element_ownership
默认 SKIP；用例说明明确写着“unresolved RTL stays FAIL”。本工程历史外部复盘还记录了
顶层 sparse-mask 的 2 个反例；本次整理没有重新执行 internal 证据。

## 问题

在 `nf>0`、强制公开端口的 sparse `v0` 字节掩码场景中，DUT 的请求边界可能把被掩码
元素或字节错误地纳入 ownership。canary 使用两个变体 `v0=0x0F0F`、`v0=0xF0F0`；
期望由 RVV 架构 element mask 计算，字节复制只提供给 DUT，不从 MaskGen 或 DUT 输出
反推期望。

## 独立预期

- 架构 element mask 决定哪些元素 active；被 mask 的 body 元素不得产生内存访问。
- 每个 active 元素只允许其 EEW 对应字节范围；字节复制不能扩大或缩小元素所有权。
- 若请求边界不满足上述关系，应保留 FAIL；不能用 canary 的 SKIP 或“预期失败数”把它
  改成 PASS。
- 该 canary 是 `nf>0` 强制端口范围，不代表当前生产 decoder 的 segment 可达性；生产
  边界见 [manifest/source-contract.json](../../../manifest/source-contract.json) 与 Design spec。

## 复现与范围

```sh
RUN_VAGQ_SPARSE_CANARY=1 ./scripts/ucv run vagq --workers 1 \
  -- tests/vagq/test_sparse_segment_canary.py
```

- 普通回归不设置该环境变量，因此该用例计 SKIP；SKIP 不是通过。
- 历史外部复盘记录 2 个顶层 sparse-mask 反例，但证据保持外部接入，不复制 internal
  源码或波形。
- 在重新运行并完成根因判定前，不能把该条记为 closed，也不能把 56 个 MaskGen
  policy mismatch 与本条合并成同一个问题。

## 证据

- [tests/vagq/test_sparse_segment_canary.py](../../../tests/vagq/test_sparse_segment_canary.py)
- [tools/build_vagq_reference_fix_report.py](../../../tools/build_vagq_reference_fix_report.py) 中的历史外部报告说明（只引用结论，不含 internal 源码）
- [Design spec](../../spec/design/README.md) 与 [Verification spec](../../spec/verification/README.md)
- 根 [docs/lessons/README.md#vagq-external-evidence](../../../../../../docs/lessons/README.md#vagq-external-evidence) 的外部复盘入口

```ucv-bug
{
  "id": "VAGQ-SPARSE-SEGMENT-MASK-CANARY",
  "title": "稀疏 v0 字节掩码下 segment 元素归属仍保留反例",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "internal-d4566d58a",
      "status": "unverified",
      "evidence": [
        "suites/vector/vagq/tests/vagq/test_sparse_segment_canary.py",
        "suites/vector/vagq/tools/build_vagq_reference_fix_report.py"
      ],
      "note": "显式 canary 默认 SKIP；外部复盘记录 2 个反例，本次未重跑或复制证据"
    }
  ]
}
```
