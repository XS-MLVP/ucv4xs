# IFU 设计规格

状态：**待设计 owner 确认**。本页由现有接口合同、ISA 规范、生成 RTL 可观察面和工程
验证记录归纳；未取得完整微架构设计签核。功能要求和责任边界以
[功能点](functional-points.md)与[行为矩阵](behavior-matrix.md)的稳定 ID 为准。

## 范围与层次

基线：`public-a0c2a26cb` / DefaultConfig / 单核；七个 DUT 按真实层次自底向上组织。

| 层 | DUT | RTL top | 功能点前缀 |
|---|---|---|---|
| 1 | `rvc_expander` | `RvcExpander` | `IFU-RVC-*` |
| 1 | `instr_boundary` | `InstrBoundary` | `IFU-IB-*` |
| 1 | `pred_checker` | `PredChecker` | `IFU-PC-*` |
| 1 | `uncache_unit` | `IfuUncacheUnit` | `IFU-UC-*` |
| 1 | `frontend_trigger` | `FrontendTrigger` | `IFU-TR-*` |
| 1 | `perf_analysis` | `IfuPerfAnalysis` | `IFU-PA-*` |
| 2 | `ifu` | `Ifu` | `IFU-TOP-*` |

顶层 `Ifu` 的指令流语义由 RVC 展开、指令边界、预测检查三层共同定义；`IfuUncacheUnit`、
`FrontendTrigger`、`IfuPerfAnalysis` 是并列旁路子模块，单独验证后在顶层复核对外可
观察行为。

## 接口与配置边界

- 顶层 `Ifu` 使用固定 ABI 的事务链（80 输入 / 405 输出）；子模块按各自公开端口适配。
- 取指 PC 为 50-bit 地址；随基线 `b716aade` 并入，`toFtq.wbRedirect.pc` 为 51-bit
  `GuardedPc`，cfiPc 半字投影为 50-bit。`IFU-ENV-005` 已改为正向交接对照。
- `FrontendTrigger` 的 `tdata2` 由 CSR 以 `RW(63,0)` 暴露为 64 位；PC 比较应覆盖
  完整可写宽度。当前实现只使用低 50 位，构成 `R-13`。
- `InstrBoundary` 的 carry 首槽完成前一窗口的指令，不是当前窗口的新起始；
  `isCrossBlockInstr` 不能被 carry 高半字错误置位。当前实现构成 `R-14`。
- 生成 RTL 去掉 verification layer 的 `$fatal`；不变量由工程侧监视器或比较器补齐，
  未导出断言按残余记录。

## 行为要求

- 功能点共 61 项（硬件 56 + 验证环境 5），覆盖 RVC 展开、边界/半字流、预测检查、
  非缓存访问、触发器、性能事件和顶层组合。
- 期望来源：RISC-V 规范、接口/CSR 合同、独立模型和生产者可写宽度；不能从 RTL 赋值
  反推。参考模型、激励编码器和检查器均独立于 DUT。
- 行为等价类、合法组合、样本合并与拆分见[行为矩阵](behavior-matrix.md)；责任矩阵和
  上层承接见[功能点](functional-points.md)的边界章节。

## 未确认项与开放问题

- `R-13` 的修复方向（全 64 位比较或 CSR 高位 WARL 只读 0）需要设计/CSR 确认。
- `R-14` 的端口合同 FAIL 已确认，但真实 FTQ 生产可达性未证明；不能自动当成整机缺陷。
- 其他配置、Frontend 级 flush/redirect 与 IBuffer/后端消费不在本层设计边界内。
