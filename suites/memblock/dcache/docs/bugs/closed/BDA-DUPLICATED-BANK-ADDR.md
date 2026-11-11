# BDA-DUPLICATED-BANK-ADDR：bank 0..15 使用 addr_dup 是设计等价，不是缺陷

状态：**已关闭（仅历史误报分类），非缺陷**。该 `closed/invalid` 只关闭历史基线的误报，
当前默认基线 `public-a0c2a26cb` 另未复验（JSON 记 `unverified`）。
BankedDataArray 的读地址对 bank 0..15 取 `addr_dup`、对
bank 16..31 取 `addr`；两者在同一个 div 内，功能上等价于两套物理副本。

## 原问题

验证模型曾怀疑 bank 0..15 的读地址与 bank 16..31 不一致会导致读错 set。实际 RTL 的
`DuplicatedQueryBankSeq = 0 until DCacheBanks/2`，前一半 bank 使用 duplicated query
地址，后一半使用普通地址；这是复制存储的寻址方式。

## 独立预期与对照

- 读某个 bank 返回的数据必须由该 bank 自己的 `way_en` 和 set 地址决定。
- `addr_dup == addr` 时，两个半区行为一致；显式构造 `addr_dup` 与 `addr` 不同的 set
  时，前半区按 `addr_dup`、后半区按 `addr`，两者都符合各自副本的地址。
- 参考模型 `read_result` 已按 bank<16 使用 `addr_dup` 的 set 实现；定向用例覆盖了
  相同和不同 set 两种形态。

## 根因与范围

不是缺陷，是 duplicated query bank 的实现事实。该结论只适用于当前
`DCacheBanks=32`、`DCacheSetDiv=1` 的生成配置；其他配置需要重新核对半区划分和地址函数。

## 证据

- 功能点 [BDA-FP-001](../../spec/design/functional-points-banked-data-array.md)
- 报告 [banked-data-array-20261024.md](../../spec/verification/evidence/banked-data-array-20261024.md)
- `BankedDataArray.scala` 的 duplicated query bank 定义；生成 RTL 的 bank 地址路径
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "BDA-DUPLICATED-BANK-ADDR",
  "title": "bank 0..15 使用 addr_dup 是 duplicated query 设计，不是地址缺陷",
  "kind": "investigation",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/dcache/docs/spec/design/functional-points-banked-data-array.md",
        "suites/memblock/dcache/docs/spec/verification/evidence/banked-data-array-20261024.md"
      ],
      "note": "模型显式按 half-bank 选择 addr_dup/addr，相同和不同 set 均已覆盖"
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
      "suites/memblock/dcache/docs/spec/design/functional-points-banked-data-array.md"
    ],
    "note": "复制 query bank 的地址选择与两套物理副本一致，不是功能缺陷"
  }
}
```
