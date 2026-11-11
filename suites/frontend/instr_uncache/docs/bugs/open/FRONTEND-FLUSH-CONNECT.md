```ucv-bug
{
  "id": "FRONTEND-FLUSH-CONNECT",
  "title": "Frontend 将 InstrUncache flush 恒接 false 的设计意图与集成行为待确认",
  "kind": "spec",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/spec/verification/exit-criteria.md：2026-11-08 R-FLUSH 收口，FRONTEND-FLUSH-CONNECT 保持 blocking/open",
        "docs/spec/verification/defects.md：2026-11-08 用户确认的保守口径与未决设计事项",
        "docs/spec/verification/evidence/flush-closure.json：public-a0c2a26cb / DefaultConfig 的 Scala 连接与生成 RTL 裁剪证据"
      ],
      "note": "沿用既有待设计确认事项：false.B 连接尚无设计 owner 确认，也无 Frontend 级集成验证；结构裁剪不等于 flush 行为通过，当前仍阻塞完整验收。未判为已确认 RTL 缺陷。"
    }
  ]
}
```

# FRONTEND-FLUSH-CONNECT：InstrUncache flush 连接的设计确认与集成缺口

本记录将既有 `FRONTEND-FLUSH-CONNECT` 事项纳入正式问题目录，沿用
2026-11-08 的 **blocking/open** 结论。类别为 `spec`，承接方为 `frontend/design`；
本次仅整理既有证据，没有新增硬件反例、仿真结果或修复结论。

## 范围与待确认要求

- 基线：`public-a0c2a26cb`，源码 commit
  `a0c2a26cbe3c862175174bad03a1a23c406315ed`，配置 `DefaultConfig`。
- 对象：`Frontend` 到 `InstrUncache` 的 flush 连接，以及真实 Entry 的取消路径。
- 待确认：恒接 `false.B` 是否是永久设计意图；该配置下由谁承担 flush/redirect 时的
  请求取消、迟响应处理及 Frontend 集成义务。
- 现有单元可达行为的通过不能证明上述连接正确或取消行为已验证；当前资料没有设计
  owner 的确认记录，也没有 Frontend 级集成验证依据。

## 已有结构证据

以下均引用原[flush 结构证据](../../spec/verification/evidence/flush-closure.json)与
[设计合同](../../spec/design/contracts.md)，不是本次重新生成或测量：

| 位置 | 已记录的事实 |
|---|---|
| `Frontend.scala:125,266` | 唯一实例 `LazyModule(new InstrUncache)`；`instrUncache.io.flush := false.B` |
| `InstrUncacheImp.scala:35,65` | 顶层声明 flush 输入，并将其透传至 Entry |
| `InstrUncacheEntry.scala:41,58-63,100,162` | 声明 flush、保存 needFlush，并以其控制响应与退出 |
| `Parameters.scala:632`、`SimFrontend.scala:195` | `EnableSimFrontend` 默认 false；模拟前端也把整个 instrUncache IO 接 0 |
| `InstrUncache.sv`、`InstrUncacheEntry.sv` | 分别 24、23 个端口，无 flush/needFlush；原文件 SHA-256 保存在证据 JSON |
| `Frontend.sv:2763` 的 `inner_instrUncache` | 生成实例没有 flush 连接，实例块哈希保存在同一证据 JSON |

因此 `R-FLUSH` 的 **out-of-domain / accepted-limited** 只描述当前单元闭包的结构事实。
`INC-FLUSH-012` 是裁剪与哈希一致性的环境检查点，不是 flush 行为验证；本记录也不把
常量传播或端口裁剪本身认定为 RTL 缺陷。

## 证据入口与验收影响

- [退出标准：R-FLUSH 收口与未决事项](../../spec/verification/exit-criteria.md)。
- [缺陷判定：结构事实与设计确认的区别](../../spec/verification/defects.md)。
- [原验证报告](../../spec/verification/reports/verification-report.md)：保留其日期、基线、
  用例结果和保守判定，不在本记录重算。
- 既有复核入口为 `tools/audit_flush_closure.py` 与
  `modules/instr_uncache/tests/framework/test_flush_closure_evidence.py`；它们检查结构证据，
  无法代替缺失的设计确认或 Frontend 行为验证。

在当前基线上，本项继续阻塞完整验收。新运行以
`acceptance_source='issue-records'` 冻结本问题后，即使实际用例全 PASS，汇总也应保持
`INCOMPLETE`，case 计数和真实 FAIL/ERROR 保持原判定；历史运行仍按其冻结字段解释。

## 承接与关闭条件

承接方 `frontend/design` 需提供可追溯的处置依据：

1. 确认 `false.B` 是永久设计意图并写入合同，明确取消责任与适用范围；或补上真实
   flush 连接/删除不再需要的接口，再重新评估该义务。
2. 按确定后的合同补充必要的 Frontend 集成证据；若要声称 flush 行为已验证，须在
   可驱动配置下证明 flush 期间与迟响应的取消语义。
3. 配置、接口或生成哈希变化后，按既有退出标准重新 prepare/build、回归和核对结构
   证据，单列适用基线；未经证据复核不关闭本项。

现阶段维持 `open`；删除旧计划、单元通过或登记本记录均不构成关闭依据。
