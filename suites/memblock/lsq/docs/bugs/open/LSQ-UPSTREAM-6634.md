# LSQ-UPSTREAM-6634 — 多个 Uncache 异常候选按物理槽顺序仲裁，正常完成可遮挡真实故障

## 状态与范围

```ucv-bug
{
  "id": "LSQ-UPSTREAM-6634",
  "title": "多个 Uncache 异常候选按物理槽顺序仲裁，正常完成可遮挡真实故障",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md",
        "tests/fail_review/test_uncache_exception_property.py",
        "docs/spec/verification/evidence/reports/same-source-audit-20261022.md"
      ],
      "note": "2026-11-02/03 新基线关系核验记录“正常完成+真实错误”“双真实错误”两个组合失败；本地公开端口探针已复现；本次未重跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "旧基线/关系核验阶段 2 个组合失败；保留为历史复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：open（历史记录显示仍存在；本次未重跑 native）。**

## 现象

`LoadQueueUncache` 对每次消费都产生 `exception.valid`，正常完成也会成为异常候选；父级用 `ParallelPriorityMux(entries)` 按物理槽序选第一个，而不是按 `robIdx/uopIdx` 程序年龄。真实故障可能被年轻正常完成项遮挡。

## 预期依据

只有真实总线错误才能成为异常候选；同拍多候选必须按不可变程序年龄选最老。

## 复现与对照

`test_uncache_exception_owner_is_oldest_real_bus_error` 覆盖“低槽正常完成 + 高槽真实错误”和“两个真实错误年龄相反”，均失败；需要先制造槽号与 ROB 年龄反序。

## 根因

`LoadQueueUncache.scala:236-239` 的 `io.exception.valid := RegNext(writeback)` 与 `:467-470` 的 entry 优先选择。

## 适用范围与仍未证明

本地公开端口探针已确认；完整 trap 地址/ISA 后果未证明。上游 PR #6634。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261022/14-relationship-11-vs-5.md](../evidence/bug-reports-20261022/14-relationship-11-vs-5.md)
- [docs/spec/verification/evidence/reports/same-source-audit-20261022.md](../../spec/verification/evidence/reports/same-source-audit-20261022.md)
- <https://github.com/OpenXiangShan/XiangShan/pull/6634>
