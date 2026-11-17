# aia

APLIC、IMSIC 总线侧和核心 CSR 侧的独立合同；实际跨 MemMisc、XSTop 与 CSR 放置。端到端中断投递仍需系统集成证据。

[设计边界与模块映射](docs/spec/design/README.md) · [验证合同](docs/spec/verification/README.md) · [问题](docs/bugs/README.md)

从仓库根执行 `./scripts/ucv info aia` 或 `./scripts/ucv check aia`。有效基线从配置继承；构建和运行按 DUT 显式选择。

当前绑定与结构接入不等于 DUT 验收。骨架的 smoke 保持显式失败；已有用例沿用原基线结论，新基线接口兼容、合法激励和独立预期仍需分别核验。
