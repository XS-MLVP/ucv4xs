# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `tl_debug_module` / `TLDebugModule` | 骨架；合同与环境待实现 | [范围、工作与完成条件](tl_debug_module.md) | [实现、用例与命令](../../../testbenches/tl_debug_module/README.md) |
| `debug_transport_module_jtag` / `DebugTransportModuleJTAG` | 骨架；合同与环境待实现 | [范围、工作与完成条件](debug_transport_module_jtag.md) | [实现、用例与命令](../../../testbenches/debug_transport_module_jtag/README.md) |
| `debug_module` / `DebugModule` | 骨架；合同与环境待实现 | [范围、工作与完成条件](debug_module.md) | [实现、用例与命令](../../../testbenches/debug_module/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`tl_debug_module`](tl_debug_module.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

调试模块、JTAG transport 和核心调试接口合同。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
