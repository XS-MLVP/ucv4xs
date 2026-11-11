# SBD-SAME-LANE-PORT-HALVES：SbufferData 高槽同一 lane 的另一半字节端口路径未覆盖

状态：**验证覆盖缺口，保留 open**。SbufferData 的每个 lane 由两个端口交替拥有低/高
半区；当前没有让目标端口写满整 lane，因此高槽同一 lane 的另一半字节端口路径未覆盖。
这是已有功能点 `SBT-ENQ-01` / `SBT-WRITE-01` 的情形缺失。当前默认基线
`public-a0c2a26cb` 尚未重新构建或回归，`versions` 记该基线为 `unverified`；下面的覆盖
证据只属于 `public-893e1580b`。

## 问题

顶层 `SbufferData.sv` 的 512 行/16 组高槽 lane 区间中，部分路径需要“端口 0 和端口 1
各拥有同一 lane 的一半字节”才能激活。现有用例要么使用低槽，要么只让一个端口覆盖整
lane；独立 SbufferData DUT 已 100% 行覆盖，但父层没有重复走全。

## 独立预期

- 同一 lane 的两个半区可以分别由两个端口写入，字节掩码和数据在 lane 内正确合并；
- 后端口覆盖重叠字节，未重叠字节保留前端口内容；
- 目标行/ lane 的 mask 和 data 与模型逐字节一致，不影响其他 lane/行。

## 范围与下一步

- 影响：已有功能点的情形缺失，不是新的功能点；父层未覆盖的路径已在独立 SbufferData
  DUT 验证过，但不能用子块结果替代父层观察。
- 下一步：在父块未满或可安全替换时先建立行，再用零掩码占住另一个端口，让目标端口
  写满整 lane；当前满容量时端口 1 的 ready 依赖端口 0。补例前保留缺口。
- 证据：`results/sbuffer-top-contract-03/coverage-audit.json`；`SbufferData.sv` 的 16 组
  高槽 lane 区间；功能点 `SBT-ENQ-01`、`SBT-WRITE-01`。

## 证据

- 功能点 [SBT-ENQ-01/SBT-WRITE-01](../../spec/design/functional-points-sbuffer.md)
- 报告 [coverage-loop-20261024.md](../../spec/verification/evidence/coverage-loop-20261024.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "SBD-SAME-LANE-PORT-HALVES",
  "title": "SbufferData 高槽同一 lane 的另一半字节端口路径未覆盖",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "suites/memblock/sbuffer/docs/spec/verification/evidence/coverage-loop-20261024.md",
        "suites/memblock/sbuffer/tests/sbuffer/test_sbuffer.py"
      ],
      "note": "独立 SbufferData DUT 已 100% 行覆盖；父层未重复走全，不作为父层完成"
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
