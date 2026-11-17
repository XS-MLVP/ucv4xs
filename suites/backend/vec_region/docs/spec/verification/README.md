# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `region` / `VecRegionModule` | 骨架；合同与环境待实现 | [范围、工作与完成条件](region.md) | [实现、用例与命令](../../../testbenches/region/README.md) |
| `vf_reg_file` / `VfRegFile` | 骨架；合同与环境待实现 | [范围、工作与完成条件](vf_reg_file.md) | [实现、用例与命令](../../../testbenches/vf_reg_file/README.md) |
| `wb_data_path` / `WbDataPath` | 骨架；合同与环境待实现 | [范围、工作与完成条件](wb_data_path.md) | [实现、用例与命令](../../../testbenches/wb_data_path/README.md) |
| `vl_reg_file` / `VlRegFile` | 骨架；合同与环境待实现 | [范围、工作与完成条件](vl_reg_file.md) | [实现、用例与命令](../../../testbenches/vl_reg_file/README.md) |
| `wb_fu_busy_table` / `WbFuBusyTable` | 骨架；合同与环境待实现 | [范围、工作与完成条件](wb_fu_busy_table.md) | [实现、用例与命令](../../../testbenches/wb_fu_busy_table/README.md) |
| `nf_mapped_elem_idx` / `NfMappedElemIdx` | 骨架；合同与环境待实现 | [范围、工作与完成条件](nf_mapped_elem_idx.md) | [实现、用例与命令](../../../testbenches/nf_mapped_elem_idx/README.md) |
| `get_e8_offset_in_vreg` / `GetE8OffsetInVreg` | 骨架；合同与环境待实现 | [范围、工作与完成条件](get_e8_offset_in_vreg.md) | [实现、用例与命令](../../../testbenches/get_e8_offset_in_vreg/README.md) |
| `exception_merge` / `VecExcpDataMergeModule` | 骨架；合同与环境待实现 | [范围、工作与完成条件](exception_merge.md) | [实现、用例与命令](../../../testbenches/exception_merge/README.md) |
| `iq_vialu_vimac_vmove_vfcvt_vfmac` / `IssueQueueVialuVimacVmoveVfcvtVfmac` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_vialu_vimac_vmove_vfcvt_vfmac.md) | [实现、用例与命令](../../../testbenches/iq_vialu_vimac_vmove_vfcvt_vfmac/README.md) |
| `iq_vialu_vidiv_vfmac_vfdiv` / `IssueQueueVialuVidivVfmacVfdiv` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_vialu_vidiv_vfmac_vfdiv.md) | [实现、用例与命令](../../../testbenches/iq_vialu_vidiv_vfmac_vfdiv/README.md) |
| `iq_vialu` / `IssueQueueVialu` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_vialu.md) | [实现、用例与命令](../../../testbenches/iq_vialu/README.md) |
| `iq_vialu_1` / `IssueQueueVialu_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_vialu_1.md) | [实现、用例与命令](../../../testbenches/iq_vialu_1/README.md) |
| `iq_vstd` / `IssueQueueVstd` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_vstd.md) | [实现、用例与命令](../../../testbenches/iq_vstd/README.md) |
| `pipe_vialu_vimac_vmove_vfcvt_vfmac` / `IssuePipeVialuVimacVmoveVfcvtVfmac` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_vialu_vimac_vmove_vfcvt_vfmac.md) | [实现、用例与命令](../../../testbenches/pipe_vialu_vimac_vmove_vfcvt_vfmac/README.md) |
| `pipe_vialu_vidiv_vfmac_vfdiv` / `IssuePipeVialuVidivVfmacVfdiv` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_vialu_vidiv_vfmac_vfdiv.md) | [实现、用例与命令](../../../testbenches/pipe_vialu_vidiv_vfmac_vfdiv/README.md) |
| `pipe_vialu` / `IssuePipeVialu` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_vialu.md) | [实现、用例与命令](../../../testbenches/pipe_vialu/README.md) |
| `pipe_vialu_1` / `IssuePipeVialu_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_vialu_1.md) | [实现、用例与命令](../../../testbenches/pipe_vialu_1/README.md) |
| `pipe_vstd` / `IssuePipeVstd` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_vstd.md) | [实现、用例与命令](../../../testbenches/pipe_vstd/README.md) |
| `pipe_vstd_1` / `IssuePipeVstd_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_vstd_1.md) | [实现、用例与命令](../../../testbenches/pipe_vstd_1/README.md) |

<!-- ucv:work-index:end -->

## 当前工作与认领

各 DUT 待认领，当前均为接入骨架；本基线尚无硬件验收证据。队列/IssuePipe 变体、
寄存器/写回、异常合并与 Region 顶层分别认领和验收。
下一步先确认向量事务的 uop/element 身份、合法参数与异常终结合同，再建立环境和独立预期。
异常合并组件的实际父实例为 Backend，须单独定义边界；internal VAGQ 不提供公开同名
模块的覆盖证明。当前没有已实现的整包共用环境，阻塞和证据归具体 DUT 规格。

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`region`](region.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

向量 Region 的发射、执行、寄存器与写回；异常合并组件实际由 Backend 直接实例化。internal VAGQ 保持独立工程与基线。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
