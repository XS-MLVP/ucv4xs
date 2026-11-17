# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `ctrl_block` / `CtrlBlock` | 骨架；合同与环境待实现 | [范围、工作与完成条件](ctrl_block.md) | [实现、用例与命令](../../../testbenches/ctrl_block/README.md) |
| `dispatch` / `Dispatch` | 骨架；合同与环境待实现 | [范围、工作与完成条件](dispatch.md) | [实现、用例与命令](../../../testbenches/dispatch/README.md) |
| `rename` / `Rename` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rename.md) | [实现、用例与命令](../../../testbenches/rename/README.md) |
| `pipe_group_connect` / `PipeGroupConnect` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_group_connect.md) | [实现、用例与命令](../../../testbenches/pipe_group_connect/README.md) |
| `rob` / `Rob` | 骨架；合同与环境待实现 | [范围、工作与完成条件](rob.md) | [实现、用例与命令](../../../testbenches/rob/README.md) |
| `decode_stage` / `DecodeStage` | 骨架；合同与环境待实现 | [范围、工作与完成条件](decode_stage.md) | [实现、用例与命令](../../../testbenches/decode_stage/README.md) |
| `lsq_enq_ctrl` / `LsqEnqCtrl` | 骨架；合同与环境待实现 | [范围、工作与完成条件](lsq_enq_ctrl.md) | [实现、用例与命令](../../../testbenches/lsq_enq_ctrl/README.md) |
| `mem_ctrl` / `MemCtrl` | 骨架；合同与环境待实现 | [范围、工作与完成条件](mem_ctrl.md) | [实现、用例与命令](../../../testbenches/mem_ctrl/README.md) |
| `fusion_decoder` / `FusionDecoder` | 骨架；合同与环境待实现 | [范围、工作与完成条件](fusion_decoder.md) | [实现、用例与命令](../../../testbenches/fusion_decoder/README.md) |
| `pipeline_connect_pipe` / `PipelineConnectPipe` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipeline_connect_pipe.md) | [实现、用例与命令](../../../testbenches/pipeline_connect_pipe/README.md) |
| `redirect_generator` / `RedirectGenerator` | 骨架；合同与环境待实现 | [范围、工作与完成条件](redirect_generator.md) | [实现、用例与命令](../../../testbenches/redirect_generator/README.md) |
| `trace` / `Trace` | 骨架；合同与环境待实现 | [范围、工作与完成条件](trace.md) | [实现、用例与命令](../../../testbenches/trace/README.md) |
| `sync_data_module_template_backend_pc_64_entry` / `SyncDataModuleTemplate_BackendPC_64entry` | 骨架；合同与环境待实现 | [范围、工作与完成条件](sync_data_module_template_backend_pc_64_entry.md) | [实现、用例与命令](../../../testbenches/sync_data_module_template_backend_pc_64_entry/README.md) |
| `gpa_mem` / `GPAMem` | 骨架；合同与环境待实现 | [范围、工作与完成条件](gpa_mem.md) | [实现、用例与命令](../../../testbenches/gpa_mem/README.md) |
| `h_perf_counter` / `HPerfCounter` | 骨架；合同与环境待实现 | [范围、工作与完成条件](h_perf_counter.md) | [实现、用例与命令](../../../testbenches/h_perf_counter/README.md) |
| `perf_events_module` / `perfEventsModule` | 骨架；合同与环境待实现 | [范围、工作与完成条件](perf_events_module.md) | [实现、用例与命令](../../../testbenches/perf_events_module/README.md) |
| `top_down_gen` / `TopDownGen` | 骨架；合同与环境待实现 | [范围、工作与完成条件](top_down_gen.md) | [实现、用例与命令](../../../testbenches/top_down_gen/README.md) |
| `backend` / `Backend` | 骨架；合同与环境待实现 | [范围、工作与完成条件](backend.md) | [实现、用例与命令](../../../testbenches/backend/README.md) |

<!-- ucv:work-index:end -->

## 当前工作与认领

各 DUT 待认领，当前均为接入骨架；本基线尚无硬件验收证据。按 rename、dispatch、ROB、
redirect 等对象的独立合同分工，CtrlBlock 与 Backend 顶层分别承担经评审的组合性质。
下一步确定每个 DUT 的合法输入、独立预期、观察点和完成条件，再实现环境；同包不等于
已有联合环境或统一验收。负责人、下一项要求、阻塞与证据维护在对应 DUT 规格。

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`ctrl_block`](ctrl_block.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

Decode/Rename/Dispatch/ROB、重定向与后端控制；CtrlBlock 为局部集成，Backend 为跨 Region 集成。TopDown/性能组件是后端及跨块服务，按实际实例定位。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
