# peripheral

MemMisc 的 TileLink/AXI 路由、位宽/ID/顺序适配及外设挂接集成；AIA、PLIC、Debug、Timer 的内部功能分别归对应 suite。

[设计边界与模块映射](docs/spec/design/README.md) · [验证合同](docs/spec/verification/README.md) · [问题](docs/bugs/README.md)

从仓库根执行 `./scripts/ucv info peripheral` 或 `./scripts/ucv check peripheral`。有效基线从配置继承；构建和运行按 DUT 显式选择。

当前绑定与结构接入不等于 DUT 验收。骨架的 smoke 保持显式失败；已有用例沿用原基线结论，新基线接口兼容、合法激励和独立预期仍需分别核验。
