# LSU-CBO-NC-AF-001 — PBMT=NC 的 CBO 被误报 Store Access Fault

## 状态与范围

```ucv-bug
{
  "id": "LSU-CBO-NC-AF-001",
  "title": "PBMT=NC 的 CBO 被误报 Store Access Fault",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json"
      ],
      "note": "当前基线未重建、未复跑 native；旧基线已复现/已复核，不能写成当前基线已复现。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "results/upstream-review-regression-02/pytest.xml",
        "review/upstream_check_20261026_01/audit.json"
      ],
      "note": "上游 #6060 仍 open；固定 RTL 未修。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

CBO 目标页为 PBMT=NC 时，`isCbo && isUncache` 成立，`storeAccessFault` 被置 1；期望 CBO 继续执行而不是产生该访问异常。

## 预期依据

NC 属性不应使 CBO 报 Store Access Fault；CBO 与普通不可缓存 Store 的异常条件必须分开。

## 复现与对照

CBO store（`fuOpType[0]=1`）、TLB `pbmt=1`，等待写回；`stout.exceptionVec_7` 实际 1、期望 0。CBO + MMIO 的 IO 样本作为同一等价类的错误代表已被剔除。

## 根因

`NewStoreUnit.scala:618-628` 的 `afCboUncache = isCbo && isUncache`；上游 #6060。

## 适用范围与仍未证明

确认固定生成 RTL 公开异常位；修复方向是排除 NC 条件，不是改测试预期。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/05-upstream-review-20261026.md](../evidence/bug-reports-20261026/05-upstream-review-20261026.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6060>
