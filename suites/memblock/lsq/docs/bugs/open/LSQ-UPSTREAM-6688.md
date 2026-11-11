# LSQ-UPSTREAM-6688 — ColdDownThreshold=0 会禁用 Replay，现有参数断言未拒绝 0

## 状态与范围

```ucv-bug
{
  "id": "LSQ-UPSTREAM-6688",
  "title": "ColdDownThreshold=0 会禁用 Replay，现有参数断言未拒绝 0",
  "kind": "spec",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/design/contracts/kind-outcome-matrix.md",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
      ],
      "note": "当前 DUT 固定 ColdDownThreshold=12，未生成 0 配置 DUT；当前基线没有该参数域复验。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "unverified",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "旧基线也未生成 0 配置 DUT；仅固定源码推导与上游记录。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未复验；旧基线结论不得写成当前已复现）。**

## 现象

`ColdDownThreshold=0` 时 `coldCounter < 0` 永远不成立，Replay 不能按该条件前进；现有断言只禁止上界，没有禁止 0。

## 预期依据

参数断言应拒绝 0，或在 0 配置下给出定义的合法行为；默认配置 12 的行为另行验证。

## 复现与对照

固定源码 `LoadQueueReplay.scala:656-663` 可静态推导；当前生成 RTL 将阈值固化为 12（`LoadQueueReplay.sv:10594-10596`、`:38143-38154`），因此没有 0 配置动态反例。

## 根因

参数合法性断言不完整；上游 #6688/#6697 的处理是增加断言，而不是支持 0 运行。

## 适用范围与仍未证明

不在默认配置 RTL 功能 bug 计数内；需要单独构建 0 配置 DUT 才能做原生验证。

## 历史证据

- [docs/spec/design/contracts/kind-outcome-matrix.md#gap-6688](../../spec/design/contracts/kind-outcome-matrix.md#gap-6688)
- [docs/spec/verification/evidence/reports/upstream-audit-20261103.md](../../spec/verification/evidence/reports/upstream-audit-20261103.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6688>
