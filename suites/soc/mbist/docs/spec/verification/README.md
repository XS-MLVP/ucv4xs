# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `mbist_pipe_frontend` / `MbistPipeFrontend` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_pipe_frontend.md) | [实现、用例与命令](../../../testbenches/mbist_pipe_frontend/README.md) |
| `mbist_pipe_mem_blk` / `MbistPipeMemBlk` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_pipe_mem_blk.md) | [实现、用例与命令](../../../testbenches/mbist_pipe_mem_blk/README.md) |
| `mbist_intf_frontend` / `MbistIntfFrontend` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_intf_frontend.md) | [实现、用例与命令](../../../testbenches/mbist_intf_frontend/README.md) |
| `mbist_intf_l2` / `MbistIntfL2` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_intf_l2.md) | [实现、用例与命令](../../../testbenches/mbist_intf_l2/README.md) |
| `mbist_intf_mem_blk` / `MbistIntfMemBlk` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_intf_mem_blk.md) | [实现、用例与命令](../../../testbenches/mbist_intf_mem_blk/README.md) |
| `mbist_pipe_l2_prefetcher` / `MbistPipeL2Prefetcher` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_pipe_l2_prefetcher.md) | [实现、用例与命令](../../../testbenches/mbist_pipe_l2_prefetcher/README.md) |
| `l2_cache_pipeline` / `L2Cache` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l2_cache_pipeline.md) | [实现、用例与命令](../../../testbenches/l2_cache_pipeline/README.md) |
| `l2_slice0_pipeline` / `L2Slice` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l2_slice0_pipeline.md) | [实现、用例与命令](../../../testbenches/l2_slice0_pipeline/README.md) |
| `mbist_pipe_sms` / `MbistPipeSms` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mbist_pipe_sms.md) | [实现、用例与命令](../../../testbenches/mbist_pipe_sms/README.md) |
| `l2_slice1_pipeline` / `L2Slice_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l2_slice1_pipeline.md) | [实现、用例与命令](../../../testbenches/l2_slice1_pipeline/README.md) |
| `l2_slice2_pipeline` / `L2Slice_2` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l2_slice2_pipeline.md) | [实现、用例与命令](../../../testbenches/l2_slice2_pipeline/README.md) |
| `l2_slice3_pipeline` / `L2Slice_3` | 骨架；合同与环境待实现 | [范围、工作与完成条件](l2_slice3_pipeline.md) | [实现、用例与命令](../../../testbenches/l2_slice3_pipeline/README.md) |

<!-- ucv:work-index:end -->

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`mbist_pipe_frontend`](mbist_pipe_frontend.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

MBIST 接口及参数化控制流水；Frontend/MemBlock/L2 保留内存选择与接入集成责任。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
