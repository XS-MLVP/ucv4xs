# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `region` / `Region` | 骨架；合同与环境待实现 | [范围、工作与完成条件](region.md) | [实现、用例与命令](../../../testbenches/region/README.md) |
| `data_path` / `DataPath` | 骨架；合同与环境待实现 | [范围、工作与完成条件](data_path.md) | [实现、用例与命令](../../../testbenches/data_path/README.md) |
| `exu_block` / `ExuBlock` | 骨架；合同与环境待实现 | [范围、工作与完成条件](exu_block.md) | [实现、用例与命令](../../../testbenches/exu_block/README.md) |
| `iq_alu_i2f_brh_njmp` / `IssueQueueAluI2fBrhNjmp` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_alu_i2f_brh_njmp.md) | [实现、用例与命令](../../../testbenches/iq_alu_i2f_brh_njmp/README.md) |
| `iq_alu_csr_fence_link_brh_njmp` / `IssueQueueAluCsrFenceLinkBrhNjmp` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_alu_csr_fence_link_brh_njmp.md) | [实现、用例与命令](../../../testbenches/iq_alu_csr_fence_link_brh_njmp/README.md) |
| `iq_alu_div_brh_njmp` / `IssueQueueAluDivBrhNjmp` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_alu_div_brh_njmp.md) | [实现、用例与命令](../../../testbenches/iq_alu_div_brh_njmp/README.md) |
| `iq_alu_bku_vset` / `IssueQueueAluBkuVset` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_alu_bku_vset.md) | [实现、用例与命令](../../../testbenches/iq_alu_bku_vset/README.md) |
| `iq_alu_mul` / `IssueQueueAluMul` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_alu_mul.md) | [实现、用例与命令](../../../testbenches/iq_alu_mul/README.md) |
| `iq_ldu` / `IssueQueueLdu` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_ldu.md) | [实现、用例与命令](../../../testbenches/iq_ldu/README.md) |
| `iq_sta_mou` / `IssueQueueStaMou` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_sta_mou.md) | [实现、用例与命令](../../../testbenches/iq_sta_mou/README.md) |
| `iq_sta_mou_1` / `IssueQueueStaMou_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_sta_mou_1.md) | [实现、用例与命令](../../../testbenches/iq_sta_mou_1/README.md) |
| `iq_std_moud` / `IssueQueueStdMoud` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_std_moud.md) | [实现、用例与命令](../../../testbenches/iq_std_moud/README.md) |
| `iq_std_moud_1` / `IssueQueueStdMoud_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_std_moud_1.md) | [实现、用例与命令](../../../testbenches/iq_std_moud_1/README.md) |
| `connect_variant` / `NewPipelineConnectPipe` | 骨架；合同与环境待实现 | [范围、工作与完成条件](connect_variant.md) | [实现、用例与命令](../../../testbenches/connect_variant/README.md) |
| `connect_variant_1` / `NewPipelineConnectPipe_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](connect_variant_1.md) | [实现、用例与命令](../../../testbenches/connect_variant_1/README.md) |
| `connect_variant_2` / `NewPipelineConnectPipe_2` | 骨架；合同与环境待实现 | [范围、工作与完成条件](connect_variant_2.md) | [实现、用例与命令](../../../testbenches/connect_variant_2/README.md) |
| `connect_variant_4` / `NewPipelineConnectPipe_4` | 骨架；合同与环境待实现 | [范围、工作与完成条件](connect_variant_4.md) | [实现、用例与命令](../../../testbenches/connect_variant_4/README.md) |
| `connect_variant_6` / `NewPipelineConnectPipe_6` | 骨架；合同与环境待实现 | [范围、工作与完成条件](connect_variant_6.md) | [实现、用例与命令](../../../testbenches/connect_variant_6/README.md) |

<!-- ucv:work-index:end -->

## 当前工作与认领

各 DUT 待认领，当前均为接入骨架；本基线尚无硬件验收证据。发射队列及参数变体、
连接变体、DataPath、ExuBlock、Region 顶层按各自合同分别认领与验收。
下一步先确认 dispatch/wakeup/issue、读寄存器与旁路事务的身份和合法域，建立独立检查。
Region 顶层只承接明确的组合性质；实际访存流水属于 LSU。当前包边界用于维护关联合同，
尚未证明或实现全包共用环境；阻塞和证据写回具体 DUT 规格。

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`region`](region.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

整数 Region 的调度、读寄存器、旁路与执行协作；Ldu/Sta 发射队列属于这里，实际访存流水属于 LSU。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
