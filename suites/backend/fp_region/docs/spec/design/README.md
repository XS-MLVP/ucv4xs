# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`region`](region.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

浮点 Region、浮点发射队列/流水、寄存器文件与写回协作。FpRFReadArbiter 还被整数 DataPath 使用，复用类型不代表另一实例已验证。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `region` | `FltRegionModule` | `src/main/scala/xiangshan/backend/float/FltRegionModule.scala:59` | `XSTop.core_with_l2.core.backend.inner_fpRegion` | 骨架；待实现 |
| `fp_reg_file` | `FpRegFile` | `src/main/scala/xiangshan/backend/regfile/Regfile.scala:67` | `XSTop.core_with_l2.core.backend.inner_fpRegion.fpRegFile` | 骨架；待实现 |
| `dummy_dpic_wrapper` | `DummyDPICWrapper_PhyFpRegState` | `difftest/src/main/scala/DPIC.scala:370` | `XSTop.core_with_l2.core.backend.inner_fpRegion.difftest_pregs_frf_1` | 骨架；待实现 |
| `iq_falu_fmul_fcvt_fcmp` | `IssueQueueFaluFmulFcvtFcmp` | `src/main/scala/xiangshan/backend/float/FltIssueQueue.scala:22` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issueQueues` | 骨架；待实现 |
| `pipe_falu_fmul_fcvt_fcmp` | `IssuePipeFaluFmulFcvtFcmp` | `src/main/scala/xiangshan/backend/float/FltIssuePipe.scala:26` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issuePipes` | 骨架；待实现 |
| `flt_wb_data_path` | `FltWbDataPath` | `src/main/scala/xiangshan/backend/float/FltWbDataPath.scala:12` | `XSTop.core_with_l2.core.backend.inner_fpRegion.fpWbDataPath` | 骨架；待实现 |
| `fp_rf_read_arbiter` | `FpRFReadArbiter` | `src/main/scala/xiangshan/backend/datapath/RFReadArbiter.scala:268` | `XSTop.core_with_l2.core.backend.inner_fpRegion.fltRFReadArbiter` | 骨架；待实现 |
| `iq_falu_fmul_fdiv` | `IssueQueueFaluFmulFdiv` | `src/main/scala/xiangshan/backend/float/FltIssueQueue.scala:22` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issueQueues_1` | 骨架；待实现 |
| `iq_falu_fmul_fdiv_1` | `IssueQueueFaluFmulFdiv_1` | `src/main/scala/xiangshan/backend/float/FltIssueQueue.scala:22` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issueQueues_2` | 骨架；待实现 |
| `iq_falu_fmul` | `IssueQueueFaluFmul` | `src/main/scala/xiangshan/backend/float/FltIssueQueue.scala:22` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issueQueues_3` | 骨架；待实现 |
| `pipe_falu_fmul_fdiv` | `IssuePipeFaluFmulFdiv` | `src/main/scala/xiangshan/backend/float/FltIssuePipe.scala:26` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issuePipes_1` | 骨架；待实现 |
| `pipe_falu_fmul_fdiv_1` | `IssuePipeFaluFmulFdiv_1` | `src/main/scala/xiangshan/backend/float/FltIssuePipe.scala:26` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issuePipes_2` | 骨架；待实现 |
| `pipe_falu_fmul` | `IssuePipeFaluFmul` | `src/main/scala/xiangshan/backend/float/FltIssuePipe.scala:26` | `XSTop.core_with_l2.core.backend.inner_fpRegion.issuePipes_3` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
