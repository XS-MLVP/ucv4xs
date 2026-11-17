# int_region

整数 Region 的调度、读寄存器、旁路与执行协作；Ldu/Sta 发射队列属于这里，实际访存流水属于 LSU。

[设计边界与模块映射](docs/spec/design/README.md) · [验证合同](docs/spec/verification/README.md) · [问题](docs/bugs/README.md)

从仓库根执行 `./scripts/ucv info int_region` 或 `./scripts/ucv check int_region`。有效基线从配置继承；构建和运行按 DUT 显式选择。

当前绑定与结构接入不等于 DUT 验收。骨架的 smoke 保持显式失败；已有用例沿用原基线结论，新基线接口兼容、合法激励和独立预期仍需分别核验。
