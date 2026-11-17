# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `ncb_transaction_queue` / `NCBTransactionQueue` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_transaction_queue.md) | [实现、用例与命令](../../../testbenches/ncb_transaction_queue/README.md) |
| `ncb_transaction_payload` / `NCBTransactionPayload` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_transaction_payload.md) | [实现、用例与命令](../../../testbenches/ncb_transaction_payload/README.md) |
| `ncb_upstream_txdat` / `NCBUpstreamTXDAT` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_upstream_txdat.md) | [实现、用例与命令](../../../testbenches/ncb_upstream_txdat/README.md) |
| `ncb_upstream_rxreq` / `NCBUpstreamRXREQ` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_upstream_rxreq.md) | [实现、用例与命令](../../../testbenches/ncb_upstream_rxreq/README.md) |
| `ncb_transaction_age_matrix` / `NCBTransactionAgeMatrix` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_transaction_age_matrix.md) | [实现、用例与命令](../../../testbenches/ncb_transaction_age_matrix/README.md) |
| `ncb_upstream_txrsp` / `NCBUpstreamTXRSP` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_upstream_txrsp.md) | [实现、用例与命令](../../../testbenches/ncb_upstream_txrsp/README.md) |
| `ncb_downstream_w` / `NCBDownstreamW` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_downstream_w.md) | [实现、用例与命令](../../../testbenches/ncb_downstream_w/README.md) |
| `ncb_downstream_aw` / `NCBDownstreamAW` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_downstream_aw.md) | [实现、用例与命令](../../../testbenches/ncb_downstream_aw/README.md) |
| `ncb_downstream_ar` / `NCBDownstreamAR` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_downstream_ar.md) | [实现、用例与命令](../../../testbenches/ncb_downstream_ar/README.md) |
| `ncb_upstream_rxdat` / `NCBUpstreamRXDAT` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_upstream_rxdat.md) | [实现、用例与命令](../../../testbenches/ncb_upstream_rxdat/README.md) |
| `ncb_downstream_r` / `NCBDownstreamR` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_downstream_r.md) | [实现、用例与命令](../../../testbenches/ncb_downstream_r/README.md) |
| `ncb_order_address_cam` / `NCBOrderAddressCAM` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_order_address_cam.md) | [实现、用例与命令](../../../testbenches/ncb_order_address_cam/README.md) |
| `ncb_transaction_free_list` / `NCBTransactionFreeList` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_transaction_free_list.md) | [实现、用例与命令](../../../testbenches/ncb_transaction_free_list/README.md) |
| `ncb_downstream_b` / `NCBDownstreamB` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ncb_downstream_b.md) | [实现、用例与命令](../../../testbenches/ncb_downstream_b/README.md) |
| `chi_link_active_manager_rx` / `CHILinkActiveManagerRX` | 骨架；合同与环境待实现 | [范围、工作与完成条件](chi_link_active_manager_rx.md) | [实现、用例与命令](../../../testbenches/chi_link_active_manager_rx/README.md) |
| `chi_link_active_manager_tx` / `CHILinkActiveManagerTX` | 骨架；合同与环境待实现 | [范围、工作与完成条件](chi_link_active_manager_tx.md) | [实现、用例与命令](../../../testbenches/chi_link_active_manager_tx/README.md) |
| `llc_bridge` / `OpenNCB` | 骨架；合同与环境待实现 | [范围、工作与完成条件](llc_bridge.md) | [实现、用例与命令](../../../testbenches/llc_bridge/README.md) |
| `mmio_bridge` / `OpenNCB_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mmio_bridge.md) | [实现、用例与命令](../../../testbenches/mmio_bridge/README.md) |
| `llc_core` / `NCB200` | 骨架；合同与环境待实现 | [范围、工作与完成条件](llc_core.md) | [实现、用例与命令](../../../testbenches/llc_core/README.md) |
| `mmio_core` / `NCB200_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mmio_core.md) | [实现、用例与命令](../../../testbenches/mmio_core/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`ncb_transaction_queue`](ncb_transaction_queue.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

LLC 与 MMIO 两种 CHI/AXI 桥配置及 NCB200 内部事务管理。两种桥分别绑定，不以一个变体替代另一个。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
