# FTQ 设计规格

状态：**待设计 owner 确认**。本页由现有接口合同、生成 RTL 可观察结构和工程验证记录
归纳；未取得独立设计签核，不能当作完整微架构规格。具体行为要求以
[功能点](functional-points.md)和[责任边界](requirements-boundary.md)的稳定 ID 为准。

## 范围与层次

```text
Ftq
├── ResolveQueue   分支解析归并、训练所有权与重定向冲刷
└── CommitQueue    call/return 退休动作的保序队列
```

`EntryQueue`、`CfiQueue`、`MetaQueue`、`SpeculationQueue` 当前未被 `Ftq` 实例化，
不进入 DUT 闭包。FTQ 自身维护的 entry/meta/pointer 状态由顶层功能点验证。

基线：`public-a0c2a26cb` / DefaultConfig / 单核。`ResolveQueue` 和 `CommitQueue` 的
Scala 与生成 RTL 与 `public-893e1580b` 逐字节相同；`Ftq` 新增 8 槽软件预取队列并把
redirect PC 扩为 51 位 GuardedVAddr。

## 配置与接口

| 项 | 当前值/合同 |
|---|---|
| FTQ 深度 | 64 entry |
| ResolveQueue | 16 entry，容量保留 4；每 entry 8 个分支槽 |
| CommitQueue | 64 entry，容量保留 8；退休宽度 8 lane |
| 预取深度 / 训练背压 | `PrefetchDepth=32`，`BpTrainStallLimit=8` |
| 软件预取队列 | 8 槽、容量保留 1；3 个 LDU 输入端口 |
| 地址坐标 | 50-bit 字节 VAddr；51-bit GuardedVAddr；公开 `Pc.addr` 为 49-bit 半字 |
| Ftq 固定 ABI | 439 个非 clock 输入、470 个输出（metadata 329 项） |
| 上游生产者 | BPU、IFU、后端 redirect/commit、ICache 预取消费者 |

端口级合法域、每通道坐标和禁止副作用见[责任边界](requirements-boundary.md)。

## 行为要求

- **ResolveQueue**：`RQ-001..011`，包括身份合并、8 分支槽、IFU 独立来源、后端过滤、
  单条背压出队、重定向冲刷、BPU 新入队冲突、保留区、复位与超容量丢弃。
  其中 `RQ-011` 的超容量行为当前被真实 RTL 违反，见
  [未解决问题](../../bugs/open/resolve-queue-branch-overflow.md)。
- **CommitQueue**：`CQ-001..005`，只接纳 RAS 动作、多 lane 保序、同拍入/出队、
  容量保留和复位。
- **Ftq 顶层**：`TOP-001..019`，覆盖所有权指针、预测准入、1/2-prefetch、1/2-fetch、
  PNR 边界、s2/s3 override、后端/IFU 重定向、异常与 satp 标记、退休指针、
  call/return commit、训练缓存、meta 队列、topdown 和软件预取队列。

每条要求的语义、期望来源和用例见[功能点](functional-points.md)；等价类和组合边界见
[行为等价类](equivalence-classes.md)。

## 时序、复位与不变量

- 一个 driver 只写自己声明的引脚；monitor 在 `DriveStable`/`RisingEdge` 双相冻结输入
  与输出，测试使用受检快照，不把组合预览当成 fire。
- 所有权指针满足 `fetch/pf ≤ bpu`、`pnr ≤ bpu`、`commit` 落后不超过一 lap；内部指针
  只作 actual 和不变量，不作为 expected owner 的来源。
- 生成 RTL 去除了 `XSError` 的 `$fatal`，因此 `InvariantMonitor` 提供每拍外部不变量
  检查；它不覆盖未导出的内部断言。
- 复位后五个所有权指针归零；异步复位合同按当前导出闭包记录，运行期复位行为必须
  通过 `RQ-010`/`CQ-005`/`TOP-001` 验证。

## 未确认项与开放问题

- 设计 owner 尚未确认超容量解析的期望实现；当前合同要求丢弃第 9 条及同拍超量报告。
- `R-06` 的第二个 fetch block 异常标记在现有 PNR/重定向合同下未构造出合法序列，
  保留为分析项，见[残余](../verification/residuals.md)。
- 上游差分只覆盖到锁定 commit 的 FTQ 路径；不据此外推其他前端模块。
