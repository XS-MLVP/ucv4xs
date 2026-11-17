# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`mbist_pipe_frontend`](mbist_pipe_frontend.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

MBIST 接口及参数化控制流水；Frontend/MemBlock/L2 保留内存选择与接入集成责任。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `mbist_pipe_frontend` | `MbistPipeFrontend` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.core.frontend.inner_mbistPl` | 骨架；待实现 |
| `mbist_pipe_mem_blk` | `MbistPipeMemBlk` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.core.memBlock.inner_mbistPl` | 骨架；待实现 |
| `mbist_intf_frontend` | `MbistIntfFrontend` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:52` | `XSTop.core_with_l2.core.frontend.inner_mbistIntf` | 骨架；待实现 |
| `mbist_intf_l2` | `MbistIntfL2` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:52` | `XSTop.core_with_l2.l2top.inner_l2cache.l2MbistIntf` | 骨架；待实现 |
| `mbist_intf_mem_blk` | `MbistIntfMemBlk` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:52` | `XSTop.core_with_l2.core.memBlock.inner_mbistIntf` | 骨架；待实现 |
| `mbist_pipe_l2_prefetcher` | `MbistPipeL2Prefetcher` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.mbistPl` | 骨架；待实现 |
| `l2_cache_pipeline` | `L2Cache` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.l2top.inner_l2cache.mbistPl` | 骨架；待实现 |
| `l2_slice0_pipeline` | `L2Slice` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.mbistPl` | 骨架；待实现 |
| `mbist_pipe_sms` | `MbistPipeSms` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.core.memBlock.inner_prefetcher.mbistSmsPl` | 骨架；待实现 |
| `l2_slice1_pipeline` | `L2Slice_1` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_1.mbistPl` | 骨架；待实现 |
| `l2_slice2_pipeline` | `L2Slice_2` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_2.mbistPl` | 骨架；待实现 |
| `l2_slice3_pipeline` | `L2Slice_3` | `utility/src/main/scala/utility/mbist/MbistPipeline.scala:164` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_3.mbistPl` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
