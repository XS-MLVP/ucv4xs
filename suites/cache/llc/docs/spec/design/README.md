# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`open_llc`](open_llc.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

OpenLLC、LLC slice、互联与 CHI 链路；顶层链路监视和日志组件单列实际放置位置。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `open_llc` | `OpenLLC` | `XSCache/src/main/scala/openLLC/OpenLLC.scala:26` | `XSTop.chi_openllc_opt` | 骨架；待实现 |
| `chi_logger` | `CHILogger` | `XSCache/src/main/scala/xscache/chi/CHILogger.scala:27` | `XSTop.mmioLogger` | 骨架；待实现 |
| `rn_xbar` | `RNXbar` | `XSCache/src/main/scala/openLLC/utils/CHIXbar.scala:26` | `XSTop.chi_openllc_opt.rnXbar` | 骨架；待实现 |
| `mem_unit` | `MemUnit` | `XSCache/src/main/scala/openLLC/MemUnit.scala:60` | `XSTop.chi_openllc_opt.slices_0.memUnit` | 骨架；待实现 |
| `mmio_diverger` | `MMIODiverger` | `XSCache/src/main/scala/openLLC/utils/MMIOBridge.scala:26` | `XSTop.chi_openllc_opt.mmioDiverger` | 骨架；待实现 |
| `response_unit` | `ResponseUnit` | `XSCache/src/main/scala/openLLC/ResponseUnit.scala:57` | `XSTop.chi_openllc_opt.slices_0.responseUnit` | 骨架；待实现 |
| `mmio_merger` | `MMIOMerger` | `XSCache/src/main/scala/openLLC/utils/MMIOBridge.scala:114` | `XSTop.chi_openllc_opt.mmioMerger` | 骨架；待实现 |
| `sn_xbar` | `SNXbar` | `XSCache/src/main/scala/openLLC/utils/CHIXbar.scala:117` | `XSTop.chi_openllc_opt.snXbar` | 骨架；待实现 |
| `transmitter_link_monitor` | `TransmitterLinkMonitor` | `XSCache/src/main/scala/openLLC/chi/LinkLayer.scala:190` | `XSTop.linkMonitor_1` | 骨架；待实现 |
| `receiver_link_monitor` | `ReceiverLinkMonitor` | `XSCache/src/main/scala/openLLC/DummyLLC.scala:372` | `XSTop.linkMonitor` | 骨架；待实现 |
| `refill_unit` | `RefillUnit` | `XSCache/src/main/scala/openLLC/RefillUnit.scala:52` | `XSTop.chi_openllc_opt.slices_0.refillUnit` | 骨架；待实现 |
| `rn_link_monitor` | `RNLinkMonitor` | `XSCache/src/main/scala/openLLC/chi/LinkLayer.scala:58` | `XSTop.chi_openllc_opt.rnLinkMonitor` | 骨架；待实现 |
| `snoop_unit` | `SnoopUnit` | `XSCache/src/main/scala/openLLC/SnoopUnit.scala:31` | `XSTop.chi_openllc_opt.slices_0.snpUnit` | 骨架；待实现 |
| `sn_link_monitor` | `SNLinkMonitor` | `XSCache/src/main/scala/openLLC/chi/LinkLayer.scala:142` | `XSTop.chi_openllc_opt.snLinkMonitor` | 骨架；待实现 |
| `rxreq` | `RXREQ` | `XSCache/src/main/scala/openLLC/chi/RXREQ.scala:26` | `XSTop.chi_openllc_opt.slices_0.rxreqUp` | 骨架；待实现 |
| `txsnp` | `TXSNP` | `XSCache/src/main/scala/openLLC/chi/TXSNP.scala:26` | `XSTop.chi_openllc_opt.slices_0.txsnpUp` | 骨架；待实现 |
| `slice` | `Slice_4` | `XSCache/src/main/scala/openLLC/Slice.scala:27` | `XSTop.chi_openllc_opt.slices_0` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
