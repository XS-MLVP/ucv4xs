# l2

CoupledL2、四个 L2 slice、请求/一致性/填充与内部预取；L2Top 补充 L1-L2 fabric 和错误上报集成。L2Cache/L2Slice 是 MBIST 生成名。

[设计边界与模块映射](docs/spec/design/README.md) · [验证合同](docs/spec/verification/README.md) · [问题](docs/bugs/README.md)

从仓库根执行 `./scripts/ucv info l2` 或 `./scripts/ucv check l2`。有效基线从配置继承；构建和运行按 DUT 显式选择。

当前绑定与结构接入不等于 DUT 验收。骨架的 smoke 保持显式失败；已有用例沿用原基线结论，新基线接口兼容、合法激励和独立预期仍需分别核验。
