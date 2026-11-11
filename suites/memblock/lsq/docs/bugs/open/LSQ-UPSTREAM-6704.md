# LSQ-UPSTREAM-6704 — 跨 16B Store 首包已接受、尾包未到窗口内 Load 读到旧值

## 状态与范围

```ucv-bug
{
  "id": "LSQ-UPSTREAM-6704",
  "title": "跨 16B Store 首包已接受、尾包未到窗口内 Load 读到旧值",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/design/contracts/kind-outcome-matrix.md",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
      ],
      "note": "当前工程仍无“首包已接受、尾包未到”的必达窗口，未在当前基线本地复现；上游 #6704 已整核复现，但不能当作本地运行结果。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "unverified",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "旧基线也未本地重跑；仅固定源码与上游复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未复验；旧基线结论不得写成当前已复现）。**

## 现象

跨 16B Store 的首请求已写入 vaddr/paddr，但 `addrValid` 只由尾请求置位；首包后、尾包前执行的 Load 看不到该 Store，可能读到旧值。

## 预期依据

首包地址已知后，该 Store 对后续 Load 的字节必须可见或被阻塞；不能等到尾包才建立前递候选。

## 复现与对照

`memory_owners.write()` 在同一调用内连续发送首、尾包，调用者等待稳定态后才查询，现有定向与随机流都不能保证命中半完成窗口。上游 #6704 已给出整核复现；本工程尚未补 `write_head_only()` 必达探针。

## 根因

`NewStoreQueue.scala:1683-1686` 的 `addrValidSet` 只接受 `isLastRequest`；前递候选又要求 `ctrlEntry.addrValid`（`:473-476`）。

## 适用范围与仍未证明

本工程未本地复现，不能把上游报告当作本地运行结果；修复需新增 `unalignHeadValid` 并配合尾包/mask 语义。

## 历史证据

- [docs/spec/design/contracts/kind-outcome-matrix.md#gap-6704](../../spec/design/contracts/kind-outcome-matrix.md#gap-6704)
- [docs/spec/verification/evidence/reports/upstream-audit-20261103.md](../../spec/verification/evidence/reports/upstream-audit-20261103.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6704>
