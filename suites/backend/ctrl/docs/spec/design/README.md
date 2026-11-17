# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`ctrl_block`](ctrl_block.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

Decode/Rename/Dispatch/ROB、重定向与后端控制；CtrlBlock 为局部集成，Backend 为跨 Region 集成。TopDown/性能组件是后端及跨块服务，按实际实例定位。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `ctrl_block` | `CtrlBlock` | `src/main/scala/xiangshan/backend/CtrlBlock.scala:82` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock` | 骨架；待实现 |
| `dispatch` | `Dispatch` | `src/main/scala/xiangshan/backend/dispatch/Dispatch.scala:53` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.dispatch` | 骨架；待实现 |
| `rename` | `Rename` | `src/main/scala/xiangshan/backend/rename/Rename.scala:44` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.rename` | 骨架；待实现 |
| `pipe_group_connect` | `PipeGroupConnect` | `src/main/scala/xiangshan/backend/PipeGroupConnect.scala:110` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.renamePipeDispatch` | 骨架；待实现 |
| `rob` | `Rob` | `src/main/scala/xiangshan/backend/rob/Rob.scala:61` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.rob` | 骨架；待实现 |
| `decode_stage` | `DecodeStage` | `src/main/scala/xiangshan/backend/vector/Decoder/DecodeStage.scala:27` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.decode` | 骨架；待实现 |
| `lsq_enq_ctrl` | `LsqEnqCtrl` | `src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala:352` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.lsqEnqCtrl` | 骨架；待实现 |
| `mem_ctrl` | `MemCtrl` | `src/main/scala/xiangshan/backend/ctrlblock/MemCtrl.scala:12` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.memCtrl` | 骨架；待实现 |
| `fusion_decoder` | `FusionDecoder` | `src/main/scala/xiangshan/backend/decode/FusionDecoder.scala:511` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.fusionDecoder` | 骨架；待实现 |
| `pipeline_connect_pipe` | `PipelineConnectPipe` | `utility/src/main/scala/utility/PipelineConnect.scala:22` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.decodePipeRenameModule` | 骨架；待实现 |
| `redirect_generator` | `RedirectGenerator` | `src/main/scala/xiangshan/backend/ctrlblock/RedirectGenerator.scala:10` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.redirectGen` | 骨架；待实现 |
| `trace` | `Trace` | `src/main/scala/xiangshan/backend/trace/Trace.scala:28` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.trace` | 骨架；待实现 |
| `sync_data_module_template_backend_pc_64_entry` | `SyncDataModuleTemplate_BackendPC_64entry` | `utility/src/main/scala/utility/DataModuleTemplate.scala:89` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.pcMem` | 骨架；待实现 |
| `gpa_mem` | `GPAMem` | `src/main/scala/xiangshan/backend/GPAMem.scala:19` | `XSTop.core_with_l2.core.backend.inner_ctrlBlock.gpaMem` | 骨架；待实现 |
| `h_perf_counter` | `HPerfCounter` | `utility/src/main/scala/utility/HardwarePerfMonitor.scala:46` | `XSTop.core_with_l2.core.frontend.inner_perfEvents_hpm.perfEvents_hpc` | 骨架；待实现 |
| `perf_events_module` | `perfEventsModule` | `src/main/scala/xiangshan/backend/fu/NewCSR/CSRModule.scala:10` | `XSTop.core_with_l2.core.frontend.inner_pfevent.perfEvents_0` | 骨架；待实现 |
| `top_down_gen` | `TopDownGen` | `src/main/scala/xiangshan/backend/TopDownGen.scala:9` | `XSTop.core_with_l2.core.backend.inner_topDownMod` | 骨架；待实现 |
| `backend` | `Backend` | `src/main/scala/xiangshan/backend/Backend.scala:62` | `XSTop.core_with_l2.core.backend` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
