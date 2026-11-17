# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`region`](region.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

向量 Region 的发射、执行、寄存器与写回；异常合并组件实际由 Backend 直接实例化。internal VAGQ 保持独立工程与基线。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `region` | `VecRegionModule` | `src/main/scala/xiangshan/backend/vector/VecRegionModule.scala:58` | `XSTop.core_with_l2.core.backend.inner_vecRegion` | 骨架；待实现 |
| `vf_reg_file` | `VfRegFile` | `src/main/scala/xiangshan/backend/regfile/Regfile.scala:67` | `XSTop.core_with_l2.core.backend.inner_vecRegion.vfRegFile` | 骨架；待实现 |
| `wb_data_path` | `WbDataPath` | `src/main/scala/xiangshan/backend/vector/WbDataPath.scala:12` | `XSTop.core_with_l2.core.backend.inner_vecRegion.vpWbDataPath` | 骨架；待实现 |
| `vl_reg_file` | `VlRegFile` | `src/main/scala/xiangshan/backend/regfile/Regfile.scala:67` | `XSTop.core_with_l2.core.backend.inner_vecRegion.vlRegFile` | 骨架；待实现 |
| `wb_fu_busy_table` | `WbFuBusyTable` | `src/main/scala/xiangshan/backend/vector/WbFuBusyTable.scala:8` | `XSTop.core_with_l2.core.backend.inner_vecRegion.intWbFuBusyTable` | 骨架；待实现 |
| `nf_mapped_elem_idx` | `NfMappedElemIdx` | `src/main/scala/xiangshan/backend/VecExcpDataMergeModule.scala:533` | `XSTop.core_with_l2.core.backend.inner_vecExcpMod.NfMappedElemIdx` | 骨架；待实现 |
| `get_e8_offset_in_vreg` | `GetE8OffsetInVreg` | `src/main/scala/xiangshan/backend/VecExcpDataMergeModule.scala:575` | `XSTop.core_with_l2.core.backend.inner_vecExcpMod.GetE8OffsetInVreg` | 骨架；待实现 |
| `exception_merge` | `VecExcpDataMergeModule` | `src/main/scala/xiangshan/backend/VecExcpDataMergeModule.scala:10` | `XSTop.core_with_l2.core.backend.inner_vecExcpMod` | 骨架；待实现 |
| `iq_vialu_vimac_vmove_vfcvt_vfmac` | `IssueQueueVialuVimacVmoveVfcvtVfmac` | `src/main/scala/xiangshan/backend/vector/VecIssueQueue.scala:24` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issueQueues` | 骨架；待实现 |
| `iq_vialu_vidiv_vfmac_vfdiv` | `IssueQueueVialuVidivVfmacVfdiv` | `src/main/scala/xiangshan/backend/vector/VecIssueQueue.scala:24` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issueQueues_1` | 骨架；待实现 |
| `iq_vialu` | `IssueQueueVialu` | `src/main/scala/xiangshan/backend/vector/VecIssueQueue.scala:24` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issueQueues_2` | 骨架；待实现 |
| `iq_vialu_1` | `IssueQueueVialu_1` | `src/main/scala/xiangshan/backend/vector/VecIssueQueue.scala:24` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issueQueues_3` | 骨架；待实现 |
| `iq_vstd` | `IssueQueueVstd` | `src/main/scala/xiangshan/backend/vector/VecIssueQueue.scala:24` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issueQueues_4` | 骨架；待实现 |
| `pipe_vialu_vimac_vmove_vfcvt_vfmac` | `IssuePipeVialuVimacVmoveVfcvtVfmac` | `src/main/scala/xiangshan/backend/vector/IssuePipe.scala:21` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issuePipes` | 骨架；待实现 |
| `pipe_vialu_vidiv_vfmac_vfdiv` | `IssuePipeVialuVidivVfmacVfdiv` | `src/main/scala/xiangshan/backend/vector/IssuePipe.scala:21` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issuePipes_1` | 骨架；待实现 |
| `pipe_vialu` | `IssuePipeVialu` | `src/main/scala/xiangshan/backend/vector/IssuePipe.scala:21` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issuePipes_2` | 骨架；待实现 |
| `pipe_vialu_1` | `IssuePipeVialu_1` | `src/main/scala/xiangshan/backend/vector/IssuePipe.scala:21` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issuePipes_3` | 骨架；待实现 |
| `pipe_vstd` | `IssuePipeVstd` | `src/main/scala/xiangshan/backend/vector/IssuePipe.scala:21` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issuePipes_4` | 骨架；待实现 |
| `pipe_vstd_1` | `IssuePipeVstd_1` | `src/main/scala/xiangshan/backend/vector/IssuePipe.scala:21` | `XSTop.core_with_l2.core.backend.inner_vecRegion.issuePipes_5` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
