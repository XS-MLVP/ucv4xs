# ncb

LLC 与 MMIO 两种 CHI/AXI 桥配置及 NCB200 内部事务管理。两种桥分别绑定，不以一个变体替代另一个。

[设计边界与模块映射](docs/spec/design/README.md) · [验证合同](docs/spec/verification/README.md) · [问题](docs/bugs/README.md)

从仓库根执行 `./scripts/ucv info ncb` 或 `./scripts/ucv check ncb`。有效基线从配置继承；构建和运行按 DUT 显式选择。

当前绑定与结构接入不等于 DUT 验收。骨架的 smoke 保持显式失败；已有用例沿用原基线结论，新基线接口兼容、合法激励和独立预期仍需分别核验。
