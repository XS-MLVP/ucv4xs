# L2TLB-INDEPENDENT-SUBBLOCKS-MISSING — L2 子块与 wrapper 缺少独立 DUT

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-INDEPENDENT-SUBBLOCKS-MISSING",
  "title": "L2 子块与 wrapper 缺少独立 DUT",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "closed",
      "evidence": [
        "manifest/baseline.json",
        "ucv.json",
        "tests/l2",
        "docs/spec/verification/functional-points"
      ],
      "note": "结构性关闭：当前仓库 ucv.json/组件目录和 L2 测试仍包含 HPTW、PTW、PMP、Bitmap、BitmapCache、PtwCache、LLPTW、L2TLBWrapper 的独立 DUT；该关闭不依赖当前基线回归通过，当前基线仍未重建/未复跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "closed",
      "evidence": [
        "manifest/baseline.json",
        "docs/spec/verification/evidence/reports/final-delivery-phase2-20261025.md"
      ],
      "note": "独立证据已补；多 allStage 等残余由其他记录跟踪。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "manifest/baseline.json",
      "docs/spec/verification/evidence/reports/final-delivery-phase2-20261025.md"
    ],
    "note": "独立 DUT/测试在当前仓库仍存在，结构性关闭；不依赖当前基线回归通过，当前基线未重建/未复跑。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：closed（结构性关闭：独立 DUT 在当前仓库仍存在；当前基线未跑回归，不代表运行通过）。**

## 观察与处置

HPTW、PTW、PMP、Bitmap、BitmapCache、PtwCache、LLPTW 和 L2TLBWrapper 均已有独立 DUT/运行。

## 结论

独立证据已补；多 allStage 等残余由其他记录跟踪。

## 历史证据

- [manifest/baseline.json](../../../manifest/baseline.json)
- [docs/spec/verification/evidence/reports/final-delivery-phase2-20261025.md](../../spec/verification/evidence/reports/final-delivery-phase2-20261025.md)
