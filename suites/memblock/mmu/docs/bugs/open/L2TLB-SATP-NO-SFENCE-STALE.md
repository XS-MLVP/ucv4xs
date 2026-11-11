# L2TLB-SATP-NO-SFENCE-STALE — satp 写入不隐含排序/失效；旧超时使用非法 responder，未定性

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-SATP-NO-SFENCE-STALE",
  "title": "satp 写入不隐含排序/失效；旧超时使用非法 responder，未定性",
  "kind": "investigation",
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
      "status": "unverified",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "历史 timeout 使用非法 responder，未定性；旧基线也没有合法激励复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未复验）。**

## 现象

satp 写入本身不隐含 store 排序或翻译缓存失效；ISA 11.1.1.11 允许 satp active 时开始的翻译在 satp inactive 后无匹配 fence 时不必完成/终止。历史 timeout 使用了非法 responder，无法建立是哪种条件。

## 预期依据

需要合法 satp/sfence/响应者时序来确定是否存在可观察 stale translation；不能把历史 timeout 当作 RTL bug。

## 复现与对照

历史用例已撤回；当前没有合法激励的复现。[manifest/known-issues.json](../../../manifest/known-issues.json) 保留 `needs-valid-stimulus-recheck`。

## 根因

验证激励与 ISA 允许的边界未分离，不能归因 RTL。

## 适用范围与仍未证明

仅保留调查项；不声称已修复或已排除。

## 历史证据

- [docs/spec/verification/evidence/reports/isa-confirmation-20261026.md](../../spec/verification/evidence/reports/isa-confirmation-20261026.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json)
