# FWD-RANGE-001 — 跨16B store的mask旋转在单候选时把另一段字节折回本段未写地址，未要求重放或等待

## 状态与范围

```ucv-bug
{
  "id": "FWD-RANGE-001",
  "title": "跨16B store的mask旋转在单候选时把另一段字节折回本段未写地址，未要求重放或等待",
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
      "note": "2026-11-02/03 新基线完整回归记录 28 个失败节点，rotateByteRight 环形旋转未改；2026-11-03 上游核查另行映射 #6718，但当前 RTL 仍未修。本次未重跑。"
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

跨16B store的mask旋转在单候选时把另一段字节折回本段未写地址，未要求重放或等待

SQ0的8B store起于VA0x1000c/PA0xabc00c，size3/mask0xff/cross16Byte=1/dataValid=addrValid=1；SQ1的16B load分别读0xabc000和0xabc010，3lane均实际mask0xf00f，四类重放/依赖标志全0。第一段只能mask0xf000，第二段只能mask0x000f；其余有效字节没有物理producer。

## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:606,627-644,654-663; MemCommon.scala:176-184`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/forward-bytes-random-01/ (仅接口孔洞mask压力，后续用真实生产者域确认)`
- `results/lsq-expanded-06/memory-history-audit-v1.json：真实跨word STA首末/STD形成连续8B Store，两个word×三个已dispatch Load查询lane，共6个未阻塞响应含无原PA producer的字节；独立审计按S2实际mask/data重建，不靠阶段参考判断。written-byte对照6例均原Store两片段实际消费及Load S3/VLQ完成。`
- [tests/forward/test_semantics.py::test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses[0-0]](../../../tests/forward/test_semantics.py)
- [tests/forward/test_semantics.py::test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses[0-1]](../../../tests/forward/test_semantics.py)
- [tests/forward/test_semantics.py::test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses[0-2]](../../../tests/forward/test_semantics.py)
- [tests/forward/test_semantics.py::test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses[1-0]](../../../tests/forward/test_semantics.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

原8个真实producer与2个任意孔洞mask UNIT-INTERFACE失败仍分列；后续真实PSQ/StoreQueue/LsqWrapper亦有连续size mask反例，不将接口压力混作合法流量。保留普通FAIL和原PA安全性质；未运行LoadUnit/Backend/ISA后果证明，行满不抵消字节范围功能失败。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/07-FWD-RANGE-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
