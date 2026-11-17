# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `mem_misc` / `MemMisc` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mem_misc.md) | [实现、用例与命令](../../../testbenches/mem_misc/README.md) |
| `axi4_deinterleaver` / `AXI4Deinterleaver` | 骨架；合同与环境待实现 | [范围、工作与完成条件](axi4_deinterleaver.md) | [实现、用例与命令](../../../testbenches/axi4_deinterleaver/README.md) |
| `axi4_id_indexer` / `AXI4IdIndexer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](axi4_id_indexer.md) | [实现、用例与命令](../../../testbenches/axi4_id_indexer/README.md) |
| `tlfifo_fixer` / `TLFIFOFixer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](tlfifo_fixer.md) | [实现、用例与命令](../../../testbenches/tlfifo_fixer/README.md) |
| `tl_fragmenter` / `TLFragmenter` | 骨架；合同与环境待实现 | [范围、工作与完成条件](tl_fragmenter.md) | [实现、用例与命令](../../../testbenches/tl_fragmenter/README.md) |
| `queue` / `Queue2_TLBundleA` | 骨架；合同与环境待实现 | [范围、工作与完成条件](queue.md) | [实现、用例与命令](../../../testbenches/queue/README.md) |
| `repeater` / `Repeater` | 骨架；合同与环境待实现 | [范围、工作与完成条件](repeater.md) | [实现、用例与命令](../../../testbenches/repeater/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`mem_misc`](mem_misc.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

MemMisc 的 TileLink/AXI 路由、位宽/ID/顺序适配及外设挂接集成；AIA、PLIC、Debug、Timer 的内部功能分别归对应 suite。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
