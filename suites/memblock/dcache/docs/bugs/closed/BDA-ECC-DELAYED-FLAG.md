# BDA-ECC-DELAYED-FLAG：未初始化 SRAM 行的 ECC 告警不是编解码缺陷

状态：**已关闭（仅历史误报分类），非缺陷**。该 `closed/invalid` 只撤回历史基线的误判，
当前默认基线 `public-a0c2a26cb` 另未复验（JSON 记 `unverified`）。
原告警来自读取从未写过的 SRAM 行；这些行的数据与 ECC 都是
随机内容，解码必然报错，不是 BankedDataArray 的编解码约定不匹配。

## 原问题与预期

功能点曾要求“写入的数据读回必须 `error_delayed=0`；整线读 `readline_error_delayed=0`”。
该要求把未初始化行也当成了应无错的正确数据，导致“本配置下正确数据也报错”的误判。

独立预期应分成三件事：

1. 经编码写路径写入的数据逐位往返一致；
2. 伪错误注入按 bank/mask 生效，读出值等于原值 XOR mask；
3. 对已写入的行，读结束后错误标志回 0；未写过的 SRAM 行不要求无错。

## 复现与对照

| 场景 | 数据 | 8 个 `read_error_delayed` |
|---|---|---|
| 从未写过的 set/way | `0x8b8e` / `0xebb1` 等随机值 | 全 1 |
| 用编码器写入全零后 | 全 0 | 全 0 |
| 写入其他地址后 | 符合模型 | 全 0 |

新增/加强的用例：

- [test_zero_line_has_no_ecc_error](../../../tests/banked_data_array/test_banked_data_array.py)::test_zero_line_has_no_ecc_error：经编码器写 0 后读回 `error=0`。
- [test_ecc_error_flag_clears_after_read](../../../tests/banked_data_array/test_banked_data_array.py)::test_ecc_error_flag_clears_after_read：读结束后标志回 0。
- [test_readline_data_and_flag_clear](../../../tests/banked_data_array/test_banked_data_array.py)::test_readline_data_and_flag_clear：整线读正确数据时标志为 0。

这些用例先 `prime` 目标 set/way，再用编码写路径初始化，符合 SRAM 的未初始化语义。

## 根因与范围

根因是把未初始化 SRAM 的随机数据当成“应通过 ECC 的正确数据”。功能点已改为
“数据往返 + 伪错误注入 + 已写行错误标志”，不再把未初始化行纳入通过条件。该结论
只适用于当前 SECDED 配置和已写入行的读回，不证明任意随机数据的 ECC 行为。

## 证据

- [P0 收口报告第 2.3 节](../../spec/verification/evidence/p0-closure-20261026.md)
- 功能点 [BDA-FP-008](../../spec/design/functional-points-banked-data-array.md)
- 报告 [banked-data-array-20261024.md](../../spec/verification/evidence/banked-data-array-20261024.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "BDA-ECC-DELAYED-FLAG",
  "title": "未初始化 SRAM 行的 ECC 告警被误判为编解码缺陷",
  "kind": "investigation",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
        "suites/memblock/dcache/tests/banked_data_array/test_banked_data_array.py::test_zero_line_has_no_ecc_error"
      ],
      "note": "未写行报错是正常 ECC 检测；编码写入后无错"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/dcache/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
      "suites/memblock/dcache/docs/spec/design/functional-points-banked-data-array.md"
    ],
    "note": "撤回“正确数据也报错”的结论；读取前必须用编码写路径初始化目标 set/way"
  }
}
```
