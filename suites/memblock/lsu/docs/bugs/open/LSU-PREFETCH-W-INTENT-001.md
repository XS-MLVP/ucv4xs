# LSU-PREFETCH-W-INTENT-001 — prefetch.w 丢失写意图，DCache 请求发成 M_PFR

## 状态与范围

```ucv-bug
{
  "id": "LSU-PREFETCH-W-INTENT-001",
  "title": "prefetch.w 丢失写意图，DCache 请求发成 M_PFR",
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
      "note": "上游 #6158 仍 open；固定 RTL 未修。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

所有预取都发 `M_PFR`（读意图），`prefetch.w` 仍应发 `M_PFW`。在只读页上，prefetch.w 不应被当作读预取放行。

## 预期依据

prefetch.w 的写意图必须进入 DCache 请求，供 TLB/PMP/PMA/DCache 权限与副作用检查使用。

## 复现与对照

LoadUnitS0 输入 `fuOpType=0x05`（该提交 prefetch.w 编码），`dcacheReq.valid=1`；实际 `cmd=2`（M_PFR），期望 `3`（M_PFW）。旧回归曾用 0x0B，结论相同；以 -02 的 0x05 为准。

## 根因

`NewLoadUnit.scala:424` 的 `Mux(isPrefetch, M_PFR, M_XRD)`。

## 适用范围与仍未证明

确认请求语义字段错误；未把 DCache 侧效应当作本 UT 已验证。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/05-upstream-review-20261026.md](../evidence/bug-reports-20261026/05-upstream-review-20261026.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6158>
