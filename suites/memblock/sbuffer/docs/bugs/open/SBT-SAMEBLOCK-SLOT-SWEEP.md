# SBT-SAMEBLOCK-SLOT-SWEEP：同块 inflight 时 follower 高槽插入未全部激活

状态：**验证覆盖缺口，保留 open**。同块 inflight 时 follower 插入只命中了部分槽；
`waitInflightMask` 的高槽写路径未全部激活。这是已有功能点 `SBT-ENQ-04` 的情形缺失，
不是新的微架构功能点。当前默认基线 `public-a0c2a26cb` 尚未重新构建或回归，`versions`
记该基线为 `unverified`；下面的覆盖证据只属于 `public-893e1580b`。

## 问题

Sbuffer 顶层 `waitInflightMask` 的 31 行/33 个分支中，只覆盖了部分同块 follower 插入
场景。已有功能点 `SBT-ENQ-04` 要求同一物理块已有 inflight 写请求时，新 store 仍可分配
不同行接收数据，但新行在旧请求返回前不得写出；当前没有逐槽激活所有高槽写路径。

## 独立预期

构造同块 inflight 的 prime，在容量尚未触发替换的窗口内逐个空槽插入 follower；每次
检查：

- 新 store 被接受到不同行；
- 新行在旧请求 hit 前不产生写请求；
- 旧请求 hit 后新行才写出，payload 与模型一致；
- 不因高槽选择而覆盖已有行或丢字节。

## 范围与下一步

- 影响：已有功能点的情形缺失，不是功能本身失败；同块串行功能已通过部分槽验证。
- 下一步：按公开 request/hit 接口轮换目标槽，逐个空槽插入 follower；保持固定 seed
  和资源上限。补例前不把该覆盖缺口计为完成。
- 证据：`results/sbuffer-top-contract-03/coverage-audit.json`；
  `SbufferDut.v` 的 `waitInflightMask` 路径；功能点 `SBT-ENQ-04`。

## 证据

- 功能点 [SBT-ENQ-04](../../spec/design/functional-points-sbuffer.md)
- 报告 [coverage-loop-20261024.md](../../spec/verification/evidence/coverage-loop-20261024.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "SBT-SAMEBLOCK-SLOT-SWEEP",
  "title": "同块 inflight 时 follower 高槽插入路径未全部激活",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "suites/memblock/sbuffer/docs/spec/verification/evidence/coverage-loop-20261024.md",
        "suites/memblock/sbuffer/tests/sbuffer/test_sbuffer.py::test_sameblock_serialization"
      ],
      "note": "属于 SBT-ENQ-04 的情形缺失；需逐槽补例，不增加 XFAIL"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/sbuffer/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ]
}
```
