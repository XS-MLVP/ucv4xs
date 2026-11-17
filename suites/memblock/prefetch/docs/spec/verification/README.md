# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `prefetcher` / `PrefetcherWrapper` | 骨架；合同与环境待实现 | [范围、工作与完成条件](prefetcher.md) | [实现、用例与命令](../../../testbenches/prefetcher/README.md) |
| `l1_prefetcher` / `L1Prefetcher` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l1_prefetcher.md) | [实现、用例与命令](../../../testbenches/l1_prefetcher/README.md) |
| `sms_prefetcher` / `SMSPrefetcher` | 骨架；合同与环境待实现 | [范围、工作与完成条件](sms_prefetcher.md) | [实现、用例与命令](../../../testbenches/sms_prefetcher/README.md) |
| `berti_prefetcher` / `BertiPrefetcher` | 骨架；合同与环境待实现 | [范围、工作与完成条件](berti_prefetcher.md) | [实现、用例与命令](../../../testbenches/berti_prefetcher/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`prefetcher`](prefetcher.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

MemBlock 内 PrefetcherWrapper 及 SMS、Stream/Stride、Berti；L2 内部预取由 l2 管理。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
