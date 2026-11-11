# FWD-SQID-001 — load越过physicalUpper且跨到新SQ generation时，低年龄段缺数据依赖错误沿用load flags，返回错误store epoch

## 状态与范围

```ucv-bug
{
  "id": "FWD-SQID-001",
  "title": "load越过physicalUpper且跨到新SQ generation时，低年龄段缺数据依赖错误沿用load flags，返回错误store epoch",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "closed",
      "evidence": [
        "docs/history/lsq-regression-a0c2a26cb-20261102.json",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
      ],
      "note": "2026-11-02/03 新基线完整回归记录 12 个节点 FAIL→PASS；上游 302c0fe19（PA 匹配与 VA tag 解耦）已进入当前基线，remaining_root_causes 不再列本项。本次文档整理未重跑 native，关闭依据是历史新基线完整运行记录与上游提交。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/bugs/evidence/bug-reports-20261022/README.md",
        "manifest/known-issues.json"
      ],
      "note": "旧基线 893e1580 上 12 个节点失败；该历史结论保留。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "docs/history/lsq-regression-a0c2a26cb-20261102.json",
      "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
    ],
    "note": "旧基线 XiangShan 893e1580b705d81f113c30c7a05734e09a08050e 上该问题为 open；2026-11-02/03 新基线完整回归记录对应节点 FAIL→PASS，上游修复提交已进入 public-a0c2a26cb。本次文档整理未重跑 native。"
  }
}
```


**当前基线 `public-a0c2a26cb`：closed（历史新基线完整运行记录为 FAIL→PASS；本次未重跑 native）。**

## 现象

load越过physicalUpper且跨到新SQ generation时，低年龄段缺数据依赖错误沿用load flags，返回错误store epoch

deq=SQ60，physicalUpper=SQ124，slot48当前store是SQ112且addrValid=true/dataValid=false；load SQ128或129的3lane都返回dataInvalid.valid=1，bits=first1/second0/value48(SQ176)，严格期望first0/second1/value48(SQ112)

## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:390-395,550-554,564,658-659`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/forward-semantic-directed-01/`
- `results/lsq-expanded-06/memory-history-audit-v1.json：先实际写出/释放60原Store flow得到真实head60，再分配68合法虚拟flow和Load SQ128，实际slot48仅对应SQ112。三lane依赖实报SQ176而非SQ112；within-window对照分别完成124个原Store及1 Load，未人为把Load限到physicalUpper内。`
- `物理64项窗口60..123；load在虚拟SQ128容量内，距deq68或69，小于128半圈，无年龄歧义。SQ124/127同类6个对照通过，不能为规避该失败把合法load约束到physicalUpper以内。`
- [tests/forward/test_semantics.py::test_missing_data_dependency_keeps_original_sq_flags_beyond_window[128-0]](../../../tests/forward/test_semantics.py)
- [tests/forward/test_semantics.py::test_missing_data_dependency_keeps_original_sq_flags_beyond_window[128-1]](../../../tests/forward/test_semantics.py)
- [tests/forward/test_semantics.py::test_missing_data_dependency_keeps_original_sq_flags_beyond_window[128-2]](../../../tests/forward/test_semantics.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

完整SQ依赖身份错误已在叶子及真实PSQ/StoreQueue/LsqWrapper边界复现；未观察该错误身份被真实Replay消费后引起挂起或架构后果。未修改RTL或放宽完整SQ身份；跨代裁剪是既有依赖身份功能的缺失情形，旧快照不变。


## 历史处置

旧基线 `XiangShan 893e1580b705d81f113c30c7a05734e09a08050e` 上该问题为 open；`public-a0c2a26cb` 的 2026-11-02/03 完整回归记录对应节点 FAIL→PASS，上游修复提交已进入当前基线。目录因此从 open 移至 closed；旧基线版本和旧证据保留，不删除、不改写。本次文档整理未运行 native。

## 历史证据

- [当前基线完整回归与逐问题差分](../../../../../../docs/history/lsq-regression-a0c2a26cb-20261102.json)：`fixed_by_upstream.FWD-SQID-001 = 12`。
- [上游修复与本地节点复核](../../spec/verification/evidence/reports/upstream-audit-20261103.md)。
- [旧报告](../evidence/bug-reports-20261022/10-FWD-SQID-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
