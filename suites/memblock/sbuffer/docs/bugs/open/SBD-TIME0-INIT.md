# SBD-TIME0-INIT：SbufferData 的 initial 复位分支不可由运行期激励到达

状态：**工具边界，保留 open**。SbufferData 生成的 `initial` 块只在仿真时间 0 执行一次；
其中 `if(reset)` 的另一分支不可由运行期激励到达。这是验证工具/生成代码边界，不是
周期复位功能缺陷。当前默认基线 `public-a0c2a26cb` 尚未重新构建或回归，`versions` 记该
基线为 `unverified`；下面的分支坐标只属于 `public-893e1580b`。

## 问题

覆盖率审计显示 SbufferData 的分支为 2115/2116，唯一缺口是 `initial` 块内
`if(reset)` 的 else 分支。该块在时间 0 执行一次，后续复位不会重新进入；常规测试的
运行期 reset 走的是另一条 `always` 路径。

## 独立预期

- 周期复位应通过 `always` 复位路径验证，不能要求时间 0 的 `initial` 分支被运行期
  reset 再次触发。
- `initial` 的复位分支是否执行，属于仿真初始化语义；如果工具不能单独控制 time-zero
  reset，分母应保留，不通过删除分支或改成豁免掩盖。
- 不影响周期 reset 功能：常规 reset 路径已被覆盖。

## 复现与范围

- 证据：`results/sbuffer-data-initial-04/coverage-audit.json` 的 branch 2115/2116。
- 影响：只影响分支覆盖分母，不影响复位功能判定。
- 下一步：无功能补例；如果工具支持 time-zero reset 控制，可单独复核该分支。

## 证据

- 功能点 [SBD-RESET-01](../../spec/design/functional-points-sbuffer-data.md)
- 报告 [sbuffer-data-20261024.md](../../spec/verification/evidence/sbuffer-data-20261024.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "SBD-TIME0-INIT",
  "title": "SbufferData initial 的 if(reset) else 分支不可由运行期激励到达",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "suites/memblock/sbuffer/docs/spec/verification/evidence/sbuffer-data-20261024.md",
        "suites/memblock/sbuffer/tests/sbuffer_data/test_sbuffer_data.py"
      ],
      "note": "branch 2115/2116；保留原始分母，不删除分支或增加豁免"
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
