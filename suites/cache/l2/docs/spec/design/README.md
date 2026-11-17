# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`request_arb`](request_arb.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

CoupledL2、四个 L2 slice、请求/一致性/填充与内部预取；L2Top 补充 L1-L2 fabric 和错误上报集成。L2Cache/L2Slice 是 MBIST 生成名。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `request_arb` | `RequestArb` | `XSCache/src/main/scala/coupledL2/RequestArb.scala:29` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.reqArb` | 骨架；待实现 |
| `mshr_ctl` | `MSHRCtl` | `XSCache/src/main/scala/coupledL2/MSHRCtl.scala:32` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.mshrCtl` | 骨架；待实现 |
| `directory` | `Directory` | `XSCache/src/main/scala/coupledL2/Directory.scala:133` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.directory` | 骨架；待实现 |
| `rxsnp` | `RXSNP` | `XSCache/src/main/scala/coupledL2/RXSNP.scala:29` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.rxsnp` | 骨架；待实现 |
| `request_buffer` | `RequestBuffer` | `XSCache/src/main/scala/coupledL2/RequestBuffer.scala:72` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.reqBuf` | 骨架；待实现 |
| `arbiter` | `Arbiter16_CHIDAT` | 依赖库 `src/main/scala/chisel3/util/Arbiter.scala`；实例化位置见 workspace | `XSTop.core_with_l2.l2top.inner_l2cache.mmioBridge.mmio_txdat_arb` | 骨架；待实现 |
| `sink_c` | `SinkC` | `XSCache/src/main/scala/coupledL2/SinkC.scala:36` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.sinkC` | 骨架；待实现 |
| `grant_buffer` | `GrantBuffer` | `XSCache/src/main/scala/coupledL2/GrantBuffer.scala:59` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.grantBuf` | 骨架；待实现 |
| `p_best_offset_prefetch` | `PBestOffsetPrefetch` | `XSCache/src/main/scala/coupledL2/prefetch/BestOffsetPrefetch.scala:1209` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.pbop` | 骨架；待实现 |
| `txdat` | `TXDAT` | `XSCache/src/main/scala/coupledL2/TXDAT.scala:34` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.txdat` | 骨架；待实现 |
| `cdp_prefetcher` | `CDPPrefetcher` | `XSCache/src/main/scala/coupledL2/prefetch/CDP.scala:1319` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.cdp` | 骨架；待实现 |
| `v_best_offset_prefetch` | `VBestOffsetPrefetch` | `XSCache/src/main/scala/coupledL2/prefetch/BestOffsetPrefetch.scala:1101` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.vbop` | 骨架；待实现 |
| `data_storage` | `DataStorage` | `XSCache/src/main/scala/coupledL2/DataStorage.scala:50` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.dataStorage` | 骨架；待实现 |
| `txreq` | `TXREQ` | `XSCache/src/main/scala/coupledL2/TXREQ.scala:33` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.txreq` | 骨架；待实现 |
| `mmio_bridge_entry` | `MMIOBridgeEntry` | `XSCache/src/main/scala/coupledL2/MMIOBridge.scala:69` | `XSTop.core_with_l2.l2top.inner_l2cache.mmioBridge.entries_0` | 骨架；待实现 |
| `txrsp` | `TXRSP` | `XSCache/src/main/scala/coupledL2/TXRSP.scala:33` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.txrsp` | 骨架；待实现 |
| `spec_miss_a_buffer` | `SpecMissABuffer` | `src/main/scala/xiangshan/SpecMissABuffer.scala:14` | `XSTop.core_with_l2.l2top.inner_l1_l2_fabric.buffer` | 骨架；待实现 |
| `decoupled2_l_credit` | `Decoupled2LCredit` | `XSCache/src/main/scala/xscache/chi/LinkLayer.scala:256` | `XSTop.linkMonitor_1.Decoupled2LCredit_txreq` | 骨架；待实现 |
| `sink_a` | `SinkA` | `XSCache/src/main/scala/coupledL2/SinkA.scala:30` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.sinkA` | 骨架；待实现 |
| `bus_error_unit` | `BusErrorUnit` | `rocket-chip/src/main/scala/tile/BusErrorUnit.scala:49` | `XSTop.core_with_l2.l2top.inner_beu` | 骨架；待实现 |
| `rxdat` | `RXDAT` | `XSCache/src/main/scala/coupledL2/RXDAT.scala:27` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.rxdat` | 骨架；待实现 |
| `stash_prefetcher` | `StashPrefetcher` | `XSCache/src/main/scala/coupledL2/prefetch/StashPrefetcher.scala:98` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.stashPrefetcher` | 骨架；待实现 |
| `queue` | `Queue4_PrefetchTrain` | 依赖库 `src/main/scala/chisel3/util/Queue.scala`；实例化位置见 workspace | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.vbop_train_buf` | 骨架；待实现 |
| `l_credit2_decoupled` | `LCredit2Decoupled` | `XSCache/src/main/scala/xscache/chi/LinkLayer.scala:131` | `XSTop.core_with_l2.l2top.inner_l2cache.linkMonitor.LCredit2Decoupled_rxsnp` | 骨架；待实现 |
| `rxrsp` | `RXRSP` | `XSCache/src/main/scala/coupledL2/RXRSP.scala:27` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.rxrsp` | 骨架；待实现 |
| `prefetch_controller` | `PrefetchController` | `XSCache/src/main/scala/coupledL2/prefetch/PrefetchController.scala:55` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.prefetchController` | 骨架；待实现 |
| `mshr_buffer` | `MSHRBuffer` | `XSCache/src/main/scala/coupledL2/MSHRBuffer.scala:40` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0.refillBuf` | 骨架；待实现 |
| `prefetch_receiver` | `PrefetchReceiver` | `XSCache/src/main/scala/coupledL2/prefetch/PrefetchReceiver.scala:36` | `XSTop.core_with_l2.l2top.inner_l2cache.prefetcher.pfRcv` | 骨架；待实现 |
| `coupled_l2` | `CoupledL2` | `XSCache/src/main/scala/coupledL2/CoupledL2.scala:425` | `XSTop.core_with_l2.l2top.inner_l2cache` | 骨架；待实现 |
| `l2top` | `L2Top` | `src/main/scala/xiangshan/L2Top.scala:416` | `XSTop.core_with_l2.l2top` | 骨架；待实现 |
| `slice0` | `Slice` | `XSCache/src/main/scala/coupledL2/Slice.scala:31` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_0` | 骨架；待实现 |
| `slice1` | `Slice_1` | `XSCache/src/main/scala/coupledL2/Slice.scala:31` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_1` | 骨架；待实现 |
| `slice2` | `Slice_2` | `XSCache/src/main/scala/coupledL2/Slice.scala:31` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_2` | 骨架；待实现 |
| `slice3` | `Slice_3` | `XSCache/src/main/scala/coupledL2/Slice.scala:31` | `XSTop.core_with_l2.l2top.inner_l2cache.slices_3` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
