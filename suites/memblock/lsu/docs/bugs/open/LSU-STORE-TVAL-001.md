# LSU-STORE-TVAL-001 — Store 故障 tval 未使用 TLB 指针掩码后的 fullva

## 状态与范围

```ucv-bug
{
  "id": "LSU-STORE-TVAL-001",
  "title": "Store 故障 tval 未使用 TLB 指针掩码后的 fullva",
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
      "note": "上游 #6742 修复晚于固定提交；本地固定 RTL 未修。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

带指针掩码的 Store 发生 page fault 时，回写的 `exceptionInfo.vaddr` 使用输入 tagged VA，而不是 TLB 返回的 `fullva`。期望 `0xff00000080200048`，实际 `0xab00000080200048`。

## 预期依据

异常 `mtval/stval` 应使用架构指针掩码后地址；TLB fullva 不只是尾段专用。

## 复现与对照

原生 NewStoreUnit：`stin.vaddr=0xab00000080200048`，TLB 返回 `fullva=0xff00000080200048` 且 `excp_0_pf_st=1`；写回 `io_exceptionInfo_bits_vaddr` 实际为 tagged 输入。

## 根因

`NewStoreUnit.scala:473-474` 只把 `paddr/gpaddr` 写回 stage data，`:823` 再用 `sxData.fullva` 产生 tval；上游 #6741/#6742 同根因。

## 适用范围与仍未证明

确认公开异常地址字段错误；未声称整核异常处理一定失败。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/05-upstream-review-20261026.md](../evidence/bug-reports-20261026/05-upstream-review-20261026.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6741>
