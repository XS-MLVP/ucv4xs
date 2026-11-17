# 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `region` / `FltRegionModule` | 骨架；合同与环境待实现 | [范围、工作与完成条件](region.md) | [实现、用例与命令](../../../testbenches/region/README.md) |
| `fp_reg_file` / `FpRegFile` | 骨架；合同与环境待实现 | [范围、工作与完成条件](fp_reg_file.md) | [实现、用例与命令](../../../testbenches/fp_reg_file/README.md) |
| `dummy_dpic_wrapper` / `DummyDPICWrapper_PhyFpRegState` | 骨架；合同与环境待实现 | [范围、工作与完成条件](dummy_dpic_wrapper.md) | [实现、用例与命令](../../../testbenches/dummy_dpic_wrapper/README.md) |
| `iq_falu_fmul_fcvt_fcmp` / `IssueQueueFaluFmulFcvtFcmp` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_falu_fmul_fcvt_fcmp.md) | [实现、用例与命令](../../../testbenches/iq_falu_fmul_fcvt_fcmp/README.md) |
| `pipe_falu_fmul_fcvt_fcmp` / `IssuePipeFaluFmulFcvtFcmp` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_falu_fmul_fcvt_fcmp.md) | [实现、用例与命令](../../../testbenches/pipe_falu_fmul_fcvt_fcmp/README.md) |
| `flt_wb_data_path` / `FltWbDataPath` | 骨架；合同与环境待实现 | [范围、工作与完成条件](flt_wb_data_path.md) | [实现、用例与命令](../../../testbenches/flt_wb_data_path/README.md) |
| `fp_rf_read_arbiter` / `FpRFReadArbiter` | 骨架；合同与环境待实现 | [范围、工作与完成条件](fp_rf_read_arbiter.md) | [实现、用例与命令](../../../testbenches/fp_rf_read_arbiter/README.md) |
| `iq_falu_fmul_fdiv` / `IssueQueueFaluFmulFdiv` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_falu_fmul_fdiv.md) | [实现、用例与命令](../../../testbenches/iq_falu_fmul_fdiv/README.md) |
| `iq_falu_fmul_fdiv_1` / `IssueQueueFaluFmulFdiv_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_falu_fmul_fdiv_1.md) | [实现、用例与命令](../../../testbenches/iq_falu_fmul_fdiv_1/README.md) |
| `iq_falu_fmul` / `IssueQueueFaluFmul` | 骨架；合同与环境待实现 | [范围、工作与完成条件](iq_falu_fmul.md) | [实现、用例与命令](../../../testbenches/iq_falu_fmul/README.md) |
| `pipe_falu_fmul_fdiv` / `IssuePipeFaluFmulFdiv` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_falu_fmul_fdiv.md) | [实现、用例与命令](../../../testbenches/pipe_falu_fmul_fdiv/README.md) |
| `pipe_falu_fmul_fdiv_1` / `IssuePipeFaluFmulFdiv_1` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_falu_fmul_fdiv_1.md) | [实现、用例与命令](../../../testbenches/pipe_falu_fmul_fdiv_1/README.md) |
| `pipe_falu_fmul` / `IssuePipeFaluFmul` | 骨架；合同与环境待实现 | [范围、工作与完成条件](pipe_falu_fmul.md) | [实现、用例与命令](../../../testbenches/pipe_falu_fmul/README.md) |

<!-- ucv:work-index:end -->

## 当前工作与认领

各 DUT 待认领，当前均为接入骨架；本基线尚无硬件验收证据。队列/IssuePipe 变体、
FpRegFile、FpRFReadArbiter、FltWbDataPath 与 Region 顶层各自认领。
下一步先确认发射身份、读口仲裁、写回与 flush 的合同，核对变体差异后决定环境复用。
包内关联不表示已有联合环境，也不能将某个仲裁器实例的结果外推到整数 DataPath 的实例；
阻塞、下一项要求与证据维护在具体 DUT 规格。

按模块维护场景、独立预期、检查、覆盖与完成条件。

初始模块：[`region`](region.md)。新增模块由 `ucv info` 发现。
## 验证切点与集成责任

浮点 Region、浮点发射队列/流水、寄存器文件与写回协作。FpRFReadArbiter 还被整数 DataPath 使用，复用类型不代表另一实例已验证。

父级检查接口组合、仲裁、背压、redirect/reset/异常传播与端到端事务守恒；子级检查独立行为合同。父级实例化子模块不自动记作该子模块功能覆盖。

既有规格继续负责要求、合法域、独立预期和未证明范围。新增骨架逐项补合同与实现，未执行项保持未验证；复用 testbench 前先核对参数与接口。
