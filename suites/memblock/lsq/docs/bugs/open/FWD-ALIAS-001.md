# FWD-ALIAS-001 — 年轻store经VA别名跨16B覆盖load字节时，VA相对重叠域漏掉其PA命中，返回更老store值且全部重放/依赖标志为0

## 状态与范围

```ucv-bug
{
  "id": "FWD-ALIAS-001",
  "title": "年轻store经VA别名跨16B覆盖load字节时，VA相对重叠域漏掉其PA命中，返回更老store值且全部重放/依赖标志为0",
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
      "note": "上游 302c0fe19 的 PA/VA 解耦只修复部分节点；2026-11-02/03 新基线完整回归仍记录 12 个失败节点。本次未重跑。"
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

年轻store经VA别名跨16B覆盖load字节时，VA相对重叠域漏掉其PA命中，返回更老store值且全部重放/依赖标志为0

SQ0在VA0x10010写PA0xabc010..13值0x11111111；SQ1在VA0x2000c跨16B写PA0xabc00c..13值0x2222222222222222；load SQ2经VA0x10010读4B，实际mask0xf/data0x11111111，matchInvalid/forwardInvalid/addrInvalid/dataInvalid全0；正确最新字节来自SQ1尾部0x22222222或必须重放/等待

## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:462-476,487-511,606-625`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/forward-initial-01/`
- `results/forward-expanded-01/ 31 PASS/3 FAIL，3lane均复现；年轻/地址无效/不重叠/同VA/其他PA页的15对照通过，64slot×3lane及回绕分支补例通过`
- `results/lsq-expanded-06/memory-history-audit-v1.json：真实STA首末+STD建立两个Store，3个已dispatch Load查询lane均无任何阻塞标志却返回旧PA字节0x11而非年轻Store的0x22，独立PA图逐字节确认。相同VA多匹配对照应保守重放；原过严helper的3个失败/317源快照保留，control-helper-correction-audit-v1证明旧采样逐bit为新用例前缀，随后真实Replay/SQ empty/原slot反馈及3原UID完成。`
- `results/forward-initial-01/initial-audit.json不导入参考模型，仅由公开SQ/VA/PA页/size/mask/原data与s2实际输出重建3lane具体反例`
- [tests/forward/test_basic.py::test_cross_word_physical_alias_never_accepts_older_word_value[0]](../../../tests/forward/test_basic.py)
- [tests/forward/test_basic.py::test_cross_word_physical_alias_never_accepts_older_word_value[1]](../../../tests/forward/test_basic.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

固定SV在叶子及真实PSQ/StoreQueue/LsqWrapper公开边界已复现字节来源失败；完整LSQ随机/恢复/全域及Backend/ISA后果尚未验收。不修改目标RTL，不因253/253 DA或必要条件对照通过而验收。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/08-FWD-ALIAS-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
