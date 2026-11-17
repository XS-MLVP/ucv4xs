# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`ncb_transaction_queue`](ncb_transaction_queue.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

LLC 与 MMIO 两种 CHI/AXI 桥配置及 NCB200 内部事务管理。两种桥分别绑定，不以一个变体替代另一个。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `ncb_transaction_queue` | `NCBTransactionQueue` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBTransactionQueue.scala:30` | `XSTop.chi_llcBridge_opt.uNCB200.uTransactionQueue` | 骨架；待实现 |
| `ncb_transaction_payload` | `NCBTransactionPayload` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBTransactionPayload.scala:30` | `XSTop.chi_llcBridge_opt.uNCB200.uTransactionPayload` | 骨架；待实现 |
| `ncb_upstream_txdat` | `NCBUpstreamTXDAT` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBUpstreamTXDAT.scala:60` | `XSTop.chi_llcBridge_opt.uNCB200.uTXDAT` | 骨架；待实现 |
| `ncb_upstream_rxreq` | `NCBUpstreamRXREQ` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBUpstreamRXREQ.scala:127` | `XSTop.chi_llcBridge_opt.uNCB200.uRXREQ` | 骨架；待实现 |
| `ncb_transaction_age_matrix` | `NCBTransactionAgeMatrix` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBTransactionAgeMatrix.scala:20` | `XSTop.chi_llcBridge_opt.uNCB200.uTransactionAgeMatrix` | 骨架；待实现 |
| `ncb_upstream_txrsp` | `NCBUpstreamTXRSP` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBUpstreamTXRSP.scala:55` | `XSTop.chi_llcBridge_opt.uNCB200.uTXRSP` | 骨架；待实现 |
| `ncb_downstream_w` | `NCBDownstreamW` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBDownstreamW.scala:49` | `XSTop.chi_llcBridge_opt.uNCB200.uW` | 骨架；待实现 |
| `ncb_downstream_aw` | `NCBDownstreamAW` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBDownstreamAW.scala:44` | `XSTop.chi_llcBridge_opt.uNCB200.uAW` | 骨架；待实现 |
| `ncb_downstream_ar` | `NCBDownstreamAR` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBDownstreamAR.scala:44` | `XSTop.chi_llcBridge_opt.uNCB200.uAR` | 骨架；待实现 |
| `ncb_upstream_rxdat` | `NCBUpstreamRXDAT` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBUpstreamRXDAT.scala:56` | `XSTop.chi_llcBridge_opt.uNCB200.uRXDAT` | 骨架；待实现 |
| `ncb_downstream_r` | `NCBDownstreamR` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBDownstreamR.scala:52` | `XSTop.chi_llcBridge_opt.uNCB200.uR` | 骨架；待实现 |
| `ncb_order_address_cam` | `NCBOrderAddressCAM` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBOrderAddressCAM.scala:29` | `XSTop.chi_llcBridge_opt.uNCB200.uOrderAddressCAM` | 骨架；待实现 |
| `ncb_transaction_free_list` | `NCBTransactionFreeList` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBTransactionFreeList.scala:23` | `XSTop.chi_llcBridge_opt.uNCB200.uTransactionFreeList` | 骨架；待实现 |
| `ncb_downstream_b` | `NCBDownstreamB` | `XSCache/OpenNCB/src/main/scala/openncb/logical/NCBDownstreamB.scala:47` | `XSTop.chi_llcBridge_opt.uNCB200.uB` | 骨架；待实现 |
| `chi_link_active_manager_rx` | `CHILinkActiveManagerRX` | `XSCache/OpenNCB/src/main/scala/openncb/logical/chi/CHILinkActiveManagerRX.scala:10` | `XSTop.chi_llcBridge_opt.uNCB200.uLinkActiveRX` | 骨架；待实现 |
| `chi_link_active_manager_tx` | `CHILinkActiveManagerTX` | `XSCache/OpenNCB/src/main/scala/openncb/logical/chi/CHILinkActiveManagerTX.scala:10` | `XSTop.chi_llcBridge_opt.uNCB200.uLinkActiveTX` | 骨架；待实现 |
| `llc_bridge` | `OpenNCB` | `XSCache/src/main/scala/openLLC/utils/OpenNCB.scala:46` | `XSTop.chi_llcBridge_opt` | 骨架；待实现 |
| `mmio_bridge` | `OpenNCB_1` | `XSCache/src/main/scala/openLLC/utils/OpenNCB.scala:46` | `XSTop.chi_mmioBridge_opt` | 骨架；待实现 |
| `llc_core` | `NCB200` | `XSCache/OpenNCB/src/main/scala/openncb/NCB200.scala:18` | `XSTop.chi_llcBridge_opt.uNCB200` | 骨架；待实现 |
| `mmio_core` | `NCB200_1` | `XSCache/OpenNCB/src/main/scala/openncb/NCB200.scala:18` | `XSTop.chi_mmioBridge_opt.uNCB200` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
