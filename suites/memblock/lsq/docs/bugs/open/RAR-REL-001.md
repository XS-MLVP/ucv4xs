# RAR-REL-001 — 孤立release的valid比地址多延迟一拍，导致前拍窗口漏报和过期窗口误报

## 状态与范围

```ucv-bug
{
  "id": "RAR-REL-001",
  "title": "孤立release的valid比地址多延迟一拍，导致前拍窗口漏报和过期窗口误报",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/history/lsq-regression-a0c2a26cb-20261102.json",
        "docs/lessons/lsq-baseline-regression-20261103.md",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
      ],
      "note": "2026-11-02/03 新基线完整回归记录 19 个失败节点，release2Cycle.valid 仍为 RegNext；本次未重跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/bugs/evidence/bug-reports-20261022/README.md",
        "manifest/known-issues.json"
      ],
      "note": "旧基线 893e1580 的原回归证据；保留为历史复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：open（历史记录显示仍存在；本次未重跑 native）。**

## 现象

孤立release的valid比地址多延迟一拍，导致前拍窗口漏报和过期窗口误报



## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueRAR.scala:130-138,183-189`。
- 生成 RTL 位置：`soc-split/rtl/LoadQueueRAR.sv:4834-4845,11865-11868`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/lsq-expanded-06/memory-history-audit-v1.json：真实53文件Wrapper中三个入口的前拍release失败，tick30旧Load实际RAR nuke=0而前拍同line年轻缓存Load应已released；current/no-release/revoke对照及真实VIOLATION Replay/S3完成均独立核验。不以NC假标签激活，未修改RTL。`
- [tests/rar/test_extended.py::test_release_allocation_windows_and_data_valid[True-previous]](../../../tests/rar/test_extended.py)
- [tests/rar/test_release_boundaries.py::test_isolated_release_age_is_exactly_current_or_previous[True-1-0]](../../../tests/rar/test_release_boundaries.py)
- [tests/rar/test_release_boundaries.py::test_isolated_release_age_is_exactly_current_or_previous[True-1-1]](../../../tests/rar/test_release_boundaries.py)
- [tests/rar/test_release_boundaries.py::test_isolated_release_age_is_exactly_current_or_previous[True-1-2]](../../../tests/rar/test_release_boundaries.py)
- [tests/rar/test_release_boundaries.py::test_isolated_release_age_is_exactly_current_or_previous[True-2-0]](../../../tests/rar/test_release_boundaries.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

固定生成RTL在独立RAR、真实LoadQueue及LsqWrapper公开边界均有严格复现；尚未重新elaborate完整Chisel基线或证明完整Backend/ISA后果，不修改或修复原始RTL。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/11-RAR-REL-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
