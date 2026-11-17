# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `request_arb` / `RequestArb` | 骨架；合同与环境待实现 | [范围、工作与完成条件](request_arb.md) | [实现、用例与命令](../../../testbenches/request_arb/README.md) |
| `mshr_ctl` / `MSHRCtl` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mshr_ctl.md) | [实现、用例与命令](../../../testbenches/mshr_ctl/README.md) |
| `directory` / `Directory` | 骨架；合同与环境待实现 | [范围、工作与完成条件](directory.md) | [实现、用例与命令](../../../testbenches/directory/README.md) |
| `rxsnp` / `RXSNP` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rxsnp.md) | [实现、用例与命令](../../../testbenches/rxsnp/README.md) |
| `request_buffer` / `RequestBuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](request_buffer.md) | [实现、用例与命令](../../../testbenches/request_buffer/README.md) |
| `arbiter` / `Arbiter16_CHIDAT` | 骨架；合同与环境待实现 | [范围、工作与完成条件](arbiter.md) | [实现、用例与命令](../../../testbenches/arbiter/README.md) |
| `sink_c` / `SinkC` | 骨架；合同与环境待实现 | [范围、工作与完成条件](sink_c.md) | [实现、用例与命令](../../../testbenches/sink_c/README.md) |
| `grant_buffer` / `GrantBuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](grant_buffer.md) | [实现、用例与命令](../../../testbenches/grant_buffer/README.md) |
| `p_best_offset_prefetch` / `PBestOffsetPrefetch` | 骨架；合同与环境待实现 | [范围、工作与完成条件](p_best_offset_prefetch.md) | [实现、用例与命令](../../../testbenches/p_best_offset_prefetch/README.md) |
| `txdat` / `TXDAT` | 骨架；合同与环境待实现 | [范围、工作与完成条件](txdat.md) | [实现、用例与命令](../../../testbenches/txdat/README.md) |
| `cdp_prefetcher` / `CDPPrefetcher` | 骨架；合同与环境待实现 | [范围、工作与完成条件](cdp_prefetcher.md) | [实现、用例与命令](../../../testbenches/cdp_prefetcher/README.md) |
| `v_best_offset_prefetch` / `VBestOffsetPrefetch` | 骨架；合同与环境待实现 | [范围、工作与完成条件](v_best_offset_prefetch.md) | [实现、用例与命令](../../../testbenches/v_best_offset_prefetch/README.md) |
| `data_storage` / `DataStorage` | 骨架；合同与环境待实现 | [范围、工作与完成条件](data_storage.md) | [实现、用例与命令](../../../testbenches/data_storage/README.md) |
| `txreq` / `TXREQ` | 骨架；合同与环境待实现 | [范围、工作与完成条件](txreq.md) | [实现、用例与命令](../../../testbenches/txreq/README.md) |
| `mmio_bridge_entry` / `MMIOBridgeEntry` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mmio_bridge_entry.md) | [实现、用例与命令](../../../testbenches/mmio_bridge_entry/README.md) |
| `txrsp` / `TXRSP` | 骨架；合同与环境待实现 | [范围、工作与完成条件](txrsp.md) | [实现、用例与命令](../../../testbenches/txrsp/README.md) |
| `spec_miss_a_buffer` / `SpecMissABuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](spec_miss_a_buffer.md) | [实现、用例与命令](../../../testbenches/spec_miss_a_buffer/README.md) |
| `decoupled2_l_credit` / `Decoupled2LCredit` | 骨架；合同与环境待实现 | [范围、工作与完成条件](decoupled2_l_credit.md) | [实现、用例与命令](../../../testbenches/decoupled2_l_credit/README.md) |
| `sink_a` / `SinkA` | 骨架；合同与环境待实现 | [范围、工作与完成条件](sink_a.md) | [实现、用例与命令](../../../testbenches/sink_a/README.md) |
| `bus_error_unit` / `BusErrorUnit` | 骨架；合同与环境待实现 | [范围、工作与完成条件](bus_error_unit.md) | [实现、用例与命令](../../../testbenches/bus_error_unit/README.md) |
| `rxdat` / `RXDAT` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rxdat.md) | [实现、用例与命令](../../../testbenches/rxdat/README.md) |
| `stash_prefetcher` / `StashPrefetcher` | 骨架；合同与环境待实现 | [范围、工作与完成条件](stash_prefetcher.md) | [实现、用例与命令](../../../testbenches/stash_prefetcher/README.md) |
| `queue` / `Queue4_PrefetchTrain` | 骨架；合同与环境待实现 | [范围、工作与完成条件](queue.md) | [实现、用例与命令](../../../testbenches/queue/README.md) |
| `l_credit2_decoupled` / `LCredit2Decoupled` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l_credit2_decoupled.md) | [实现、用例与命令](../../../testbenches/l_credit2_decoupled/README.md) |
| `rxrsp` / `RXRSP` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rxrsp.md) | [实现、用例与命令](../../../testbenches/rxrsp/README.md) |
| `prefetch_controller` / `PrefetchController` | 骨架；合同与环境待实现 | [范围、工作与完成条件](prefetch_controller.md) | [实现、用例与命令](../../../testbenches/prefetch_controller/README.md) |
| `mshr_buffer` / `MSHRBuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mshr_buffer.md) | [实现、用例与命令](../../../testbenches/mshr_buffer/README.md) |
| `prefetch_receiver` / `PrefetchReceiver` | 骨架；合同与环境待实现 | [范围、工作与完成条件](prefetch_receiver.md) | [实现、用例与命令](../../../testbenches/prefetch_receiver/README.md) |
| `coupled_l2` / `CoupledL2` | 骨架；合同与环境待实现 | [范围、工作与完成条件](coupled_l2.md) | [实现、用例与命令](../../../testbenches/coupled_l2/README.md) |
| `l2top` / `L2Top` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l2top.md) | [实现、用例与命令](../../../testbenches/l2top/README.md) |
| `slice0` / `Slice` | 骨架；合同与环境待实现 | [范围、工作与完成条件](slice0.md) | [实现、用例与命令](../../../testbenches/slice0/README.md) |
| `slice1` / `Slice_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](slice1.md) | [实现、用例与命令](../../../testbenches/slice1/README.md) |
| `slice2` / `Slice_2` | 骨架；合同与环境待实现 | [范围、工作与完成条件](slice2.md) | [实现、用例与命令](../../../testbenches/slice2/README.md) |
| `slice3` / `Slice_3` | 骨架；合同与环境待实现 | [范围、工作与完成条件](slice3.md) | [实现、用例与命令](../../../testbenches/slice3/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`request_arb`](request_arb.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

CoupledL2、四个 L2 slice、请求/一致性/填充与内部预取；L2Top 补充 L1-L2 fabric 和错误上报集成。L2Cache/L2Slice 是 MBIST 生成名。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
