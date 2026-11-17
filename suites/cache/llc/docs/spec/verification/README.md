# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `open_llc` / `OpenLLC` | 骨架；合同与环境待实现 | [范围、工作与完成条件](open_llc.md) | [实现、用例与命令](../../../testbenches/open_llc/README.md) |
| `chi_logger` / `CHILogger` | 骨架；合同与环境待实现 | [范围、工作与完成条件](chi_logger.md) | [实现、用例与命令](../../../testbenches/chi_logger/README.md) |
| `rn_xbar` / `RNXbar` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rn_xbar.md) | [实现、用例与命令](../../../testbenches/rn_xbar/README.md) |
| `mem_unit` / `MemUnit` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mem_unit.md) | [实现、用例与命令](../../../testbenches/mem_unit/README.md) |
| `mmio_diverger` / `MMIODiverger` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mmio_diverger.md) | [实现、用例与命令](../../../testbenches/mmio_diverger/README.md) |
| `response_unit` / `ResponseUnit` | 骨架；合同与环境待实现 | [范围、工作与完成条件](response_unit.md) | [实现、用例与命令](../../../testbenches/response_unit/README.md) |
| `mmio_merger` / `MMIOMerger` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mmio_merger.md) | [实现、用例与命令](../../../testbenches/mmio_merger/README.md) |
| `sn_xbar` / `SNXbar` | 骨架；合同与环境待实现 | [范围、工作与完成条件](sn_xbar.md) | [实现、用例与命令](../../../testbenches/sn_xbar/README.md) |
| `transmitter_link_monitor` / `TransmitterLinkMonitor` | 骨架；合同与环境待实现 | [范围、工作与完成条件](transmitter_link_monitor.md) | [实现、用例与命令](../../../testbenches/transmitter_link_monitor/README.md) |
| `receiver_link_monitor` / `ReceiverLinkMonitor` | 骨架；合同与环境待实现 | [范围、工作与完成条件](receiver_link_monitor.md) | [实现、用例与命令](../../../testbenches/receiver_link_monitor/README.md) |
| `refill_unit` / `RefillUnit` | 骨架；合同与环境待实现 | [范围、工作与完成条件](refill_unit.md) | [实现、用例与命令](../../../testbenches/refill_unit/README.md) |
| `rn_link_monitor` / `RNLinkMonitor` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rn_link_monitor.md) | [实现、用例与命令](../../../testbenches/rn_link_monitor/README.md) |
| `snoop_unit` / `SnoopUnit` | 骨架；合同与环境待实现 | [范围、工作与完成条件](snoop_unit.md) | [实现、用例与命令](../../../testbenches/snoop_unit/README.md) |
| `sn_link_monitor` / `SNLinkMonitor` | 骨架；合同与环境待实现 | [范围、工作与完成条件](sn_link_monitor.md) | [实现、用例与命令](../../../testbenches/sn_link_monitor/README.md) |
| `rxreq` / `RXREQ` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rxreq.md) | [实现、用例与命令](../../../testbenches/rxreq/README.md) |
| `txsnp` / `TXSNP` | 骨架；合同与环境待实现 | [范围、工作与完成条件](txsnp.md) | [实现、用例与命令](../../../testbenches/txsnp/README.md) |
| `slice` / `Slice_4` | 骨架；合同与环境待实现 | [范围、工作与完成条件](slice.md) | [实现、用例与命令](../../../testbenches/slice/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`open_llc`](open_llc.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

OpenLLC、LLC slice、互联与 CHI 链路；顶层链路监视和日志组件单列实际放置位置。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
