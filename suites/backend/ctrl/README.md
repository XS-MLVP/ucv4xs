# ctrl

Decode/Rename/Dispatch/ROB、重定向与后端控制；CtrlBlock 为局部集成，Backend 为跨 Region 集成。TopDown/性能组件是后端及跨块服务，按实际实例定位。

[设计边界与模块映射](docs/spec/design/README.md) · [验证合同](docs/spec/verification/README.md) · [问题](docs/bugs/README.md)

从仓库根执行 `./scripts/ucv info ctrl` 或 `./scripts/ucv check ctrl`。有效基线从配置继承；构建和运行按 DUT 显式选择。

当前绑定与结构接入不等于 DUT 验收。骨架的 smoke 保持显式失败；已有用例沿用原基线结论，新基线接口兼容、合法激励和独立预期仍需分别核验。
