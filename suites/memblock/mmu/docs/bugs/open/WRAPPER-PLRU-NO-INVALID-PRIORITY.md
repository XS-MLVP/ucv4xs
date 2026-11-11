# WRAPPER-PLRU-NO-INVALID-PRIORITY — TlbStorageWrapper 的 PLRU 不优先无效 way，冷启动可能淘汰有效项

## 状态与范围

```ucv-bug
{
  "id": "WRAPPER-PLRU-NO-INVALID-PRIORITY",
  "title": "TlbStorageWrapper 的 PLRU 不优先无效 way，冷启动可能淘汰有效项",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "当前基线未重建、未复跑 native；旧基线结论不得写成当前已复现。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/spec/verification/evidence/reports/wrapper-20261024.md",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "固定 RTL 观察；非功能正确性失败。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未复验）。**

## 现象

内部 `refill_idx` 是纯 tree-PLRU，不优先 invalid way；从复位起前 60 次 refill 只覆盖 46/48 way，way 15/31 直到后续 refill 才被选中。

## 预期依据

冷启动可优先填充 invalid way；ISA 不规定 TLB 容量或 PLRU 顺序，因此这是性能/老化问题，不是 ISA 功能失败。

## 复现与对照

`test_reset_and_initial_plru_victim_sequence` 记录 victim 序列；63 次 refill/steer 后 `victim_way` 覆盖 48/48。

## 根因

`TlbStorageWrapper.sv` 使用纯 tree-PLRU，未应用 replaceWrapper 的 invalid-first helper。

## 适用范围与仍未证明

只观察替换顺序；不声称翻译结果错误。

## 历史证据

- [docs/spec/verification/evidence/reports/wrapper-20261024.md](../../spec/verification/evidence/reports/wrapper-20261024.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json)
