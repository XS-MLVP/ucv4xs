# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`region`](region.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

整数 Region 的调度、读寄存器、旁路与执行协作；Ldu/Sta 发射队列属于这里，实际访存流水属于 LSU。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `region` | `Region` | `src/main/scala/xiangshan/backend/Region.scala:40` | `XSTop.core_with_l2.core.backend.inner_intRegion` | 骨架；待实现 |
| `data_path` | `DataPath` | `src/main/scala/xiangshan/backend/datapath/DataPath.scala:26` | `XSTop.core_with_l2.core.backend.inner_intRegion.intDataPath` | 骨架；待实现 |
| `exu_block` | `ExuBlock` | `src/main/scala/xiangshan/backend/exu/ExuBlock.scala:18` | `XSTop.core_with_l2.core.backend.inner_intRegion.intExuBlock` | 骨架；待实现 |
| `iq_alu_i2f_brh_njmp` | `IssueQueueAluI2fBrhNjmp` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueALU2BJU2_AluI2fBrhNjmp` | 骨架；待实现 |
| `iq_alu_csr_fence_link_brh_njmp` | `IssueQueueAluCsrFenceLinkBrhNjmp` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueALU0BJU0_AluCsrFenceLinkBrhNjmp` | 骨架；待实现 |
| `iq_alu_div_brh_njmp` | `IssueQueueAluDivBrhNjmp` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueALU1BJU1_AluDivBrhNjmp` | 骨架；待实现 |
| `iq_alu_bku_vset` | `IssueQueueAluBkuVset` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueALU3_AluBkuVset` | 骨架；待实现 |
| `iq_alu_mul` | `IssueQueueAluMul` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueALU4_AluMul` | 骨架；待实现 |
| `iq_ldu` | `IssueQueueLdu` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueLDU0_Ldu` | 骨架；待实现 |
| `iq_sta_mou` | `IssueQueueStaMou` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueSTA0_StaMou` | 骨架；待实现 |
| `iq_sta_mou_1` | `IssueQueueStaMou_1` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueSTA1_StaMou` | 骨架；待实现 |
| `iq_std_moud` | `IssueQueueStdMoud` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueSTD0_StdMoud` | 骨架；待实现 |
| `iq_std_moud_1` | `IssueQueueStdMoud_1` | `src/main/scala/xiangshan/backend/issue/IssueQueue.scala:70` | `XSTop.core_with_l2.core.backend.inner_intRegion.issueQueueSTD1_StdMoud` | 骨架；待实现 |
| `connect_variant` | `NewPipelineConnectPipe` | `src/main/scala/xiangshan/backend/datapath/NewPipelineConnect.scala:22` | `XSTop.core_with_l2.core.backend.inner_intRegion.pipeToALU0` | 骨架；待实现 |
| `connect_variant_1` | `NewPipelineConnectPipe_1` | `src/main/scala/xiangshan/backend/datapath/NewPipelineConnect.scala:22` | `XSTop.core_with_l2.core.backend.inner_intRegion.pipeToBJU0` | 骨架；待实现 |
| `connect_variant_2` | `NewPipelineConnectPipe_2` | `src/main/scala/xiangshan/backend/datapath/NewPipelineConnect.scala:22` | `XSTop.core_with_l2.core.backend.inner_intRegion.pipeToALU1` | 骨架；待实现 |
| `connect_variant_4` | `NewPipelineConnectPipe_4` | `src/main/scala/xiangshan/backend/datapath/NewPipelineConnect.scala:22` | `XSTop.core_with_l2.core.backend.inner_intRegion.pipeToALU2` | 骨架；待实现 |
| `connect_variant_6` | `NewPipelineConnectPipe_6` | `src/main/scala/xiangshan/backend/datapath/NewPipelineConnect.scala:22` | `XSTop.core_with_l2.core.backend.inner_intRegion.pipeToALU3` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
