# LLPTW-STAGE2-CACHE-UNVERIFIED — LLPTW 独立 harness 无法捕获 stage2/cache-retry

## 状态与范围

```ucv-bug
{
  "id": "LLPTW-STAGE2-CACHE-UNVERIFIED",
  "title": "LLPTW 独立 harness 无法捕获 stage2/cache-retry",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧版本已处置（旧基线验证缺口完成）。2026-11-11 本轮当前 16 DUT 构建及统一选跑 421 PASS，最后 loader 修补定向 21 PASS；本问题完整覆盖/关闭条件未重新审计，仍为 unverified，不因局部 PASS 自动关闭。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "closed",
      "evidence": [
        "tests/l2/test_llptw.py::test_stage2_identity_translation",
        "docs/spec/verification/evidence/reports/llptw-20261025.md"
      ],
      "note": "验证缺口由 `llptw-final-03/04` 补齐。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "tests/l2/test_llptw.py::test_stage2_identity_translation",
      "docs/spec/verification/evidence/reports/llptw-20261025.md"
    ],
    "note": "验证缺口由 `llptw-final-03/04` 补齐。 当前基线待复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（旧版本已处置；本轮已有局部真实回归，完整问题关闭条件未验收）。**

**2026-11-10 当前接口/MXR 复核**：当前 a0c2 的 PTW/LLPTW 生成接口已裁剪 `io_csr_priv_mxr`，且
`PageTableWalker.scala` 的隐式 G-stage 页表读只要求 `R=1`。独立 RISC-V privileged v20260120
（hypervisor §14.1.5.1、preface）规定该访问按 implicit load 检查、MXR 只作用于 explicit access；
因此旧 `test_stage2_first_perm_mxr_pass` 的“MXR=1 + X=1 + R=0 可继续”是危险旧期望，已按用户授权
在同 nodeid 内纠正为拒绝，并保留 R=1 合法控制。合同与证据见
[implicit-gstage-mxr-contract.md](../../spec/design/contracts/implicit-gstage-mxr-contract.md) 和
`results/transaction-adapters-20261110/mmu/baseline-and-port-diff.json`。此差异不属于原事务迁移零差分。

2026-11-11 独立复验：当前 16 DUT 统一 421 PASS（PMP 未选），最后 loader 小修补定向
21 PASS；旧 893e 的定向对照仍为 5 PASS / 2 FAIL，两个 FAIL 分别对应 PTW/LLPTW
危险 MXR 期望被纠正后的真实错误放行。各选择有重叠，不累计通过数，也不证明本问题
所有 stage2/cache-retry 覆盖义务已闭合。收据为
`results/transaction-adapters-20261110/mmu/independent-acceptance.json`；旧报告原字节保留。

## 观察与处置

修正组合刷新与响应捕获后，allStage 首/末 HPTW、gpf/gaf、权限/MXR、onlyStage2 和 cache retry 均验证，功能覆盖 38 samples 达 100%。

## 结论

验证缺口由 `llptw-final-03/04` 补齐。


## 历史处置

旧基线 `XiangShan 893e1580b705d81f113c30c7a05734e09a08050e` 上该验证缺口已完成并关闭；当前基线 `public-a0c2a26cb` 未复验，因此按当前主线状态规则将目录移回 open，保留旧 closed 版本与历史 resolution。旧证据和结论不删除、不改写。本次文档整理未运行 native。

## 历史证据

- [tests/l2/test_llptw.py::test_stage2_identity_translation](../../../tests/l2/test_llptw.py)
- [docs/spec/verification/evidence/reports/llptw-20261025.md](../../spec/verification/evidence/reports/llptw-20261025.md)
