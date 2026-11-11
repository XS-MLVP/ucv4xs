# SBT-TOGGLE-RESIDUAL：Sbuffer 顶层 toggle 82.0% 的剩余分类

状态：**覆盖缺口，保留 open**。Sbuffer 顶层 toggle 为 70275/85706 = 82.0%；
剩余点主要集中在高槽存储输出位、行状态位和内部写流水。功能覆盖为 8 组 100%，
toggle 不作为硬件功能通过标准，但该残余不能当作已完成。当前默认基线
`public-a0c2a26cb` 尚未重新构建或回归，`versions` 记该基线为 `unverified`；下面的
计数只属于 `public-893e1580b`。

## 问题

| 类别 | 未翻转点 |
|---|---:|
| storage_output_bit | 2938 |
| line_state_bit | 3946 |
| internal_write_pipeline | 1338 |
| forward_bit | 986 |
| other | 5244 |

这些点多数属于已有功能点 `SBT-WRITE-01` / `SBT-ENQ-01` 的情形缺失：高槽和整 lane
写入没有走满，导致宽存储输出和行状态位的 0→1/1→0 未全部出现。

## 独立预期

toggle 是结构覆盖指标，不是行为正确性 oracle。可以补合法情形提高翻转，但不能为了
翻转数字构造不可达输入或修改 RTL。对每个剩余类别应回答：

- 是否由合法输入可达；
- 是否属于已有功能点的情形缺失；
- 是否需要新功能点（通常不需要）；
- 是否存在工具/常量/未驱动端口造成的不可达位。

## 下一步

全 16 槽写 0/1/0 饱和，并对转发地址高位做定向/合法随机；保持固定 seed 和资源上限。
补例后重新统计并更新分类，不删除原始分母，也不把 toggle 提升作为功能通过结论。

## 证据

- 报告 [coverage-loop-20261024.md](../../spec/verification/evidence/coverage-loop-20261024.md)
- 功能点 [SBT-WRITE-01/SBT-ENQ-01](../../spec/design/functional-points-sbuffer.md)
- `results/sbuffer-top-contract-03/coverage-audit.json`（历史运行产物，不随 Git 发布）；[manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "SBT-TOGGLE-RESIDUAL",
  "title": "Sbuffer 顶层 toggle 82.0% 的剩余点分类与补例计划",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "suites/memblock/sbuffer/docs/spec/verification/evidence/coverage-loop-20261024.md",
        "suites/memblock/sbuffer/tests/sbuffer/test_sbuffer.py"
      ],
      "note": "toggle 70275/85706；功能覆盖 8 组 100%，不能据此宣称 toggle 完成"
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
