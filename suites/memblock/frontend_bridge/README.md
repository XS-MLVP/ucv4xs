# FrontendBridge

MemBlock 内 FrontendBridge 及 ICacheBuffer、ICacheCtrlBuffer、InstrUncacheBuffer；当前为待实现骨架。

[DUT 工作索引与验证合同](docs/spec/verification/README.md) · [设计与硬件绑定](docs/spec/design/README.md) · [问题](docs/bugs/README.md)

从仓库根运行 `./scripts/ucv info frontend_bridge`；用 `--dut <key>` 选择验证对象。
`./scripts/ucv docs frontend_bridge` 预览工作索引，`./scripts/ucv check frontend_bridge` 检查入口。

工作按 DUT＋合同认领，负责人、下一步、阻塞及证据维护在验证规格正文或关联任务中。
各 DUT 使用独立绑定和结果，shared 只承载本包实际复用的机制。

当前公开基线由根配置继承；历史基线结果保持原义。目录/收集检查不代表新基线功能验收，
原 native/RTL 工作空间已归档，当前资源由配方重新准备和构建。
