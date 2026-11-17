# IFU

Ifu 顶层、指令边界、RVC 展开、预测检查、非缓存单元、触发器与性能分析。

[DUT 工作索引与验证合同](docs/spec/verification/README.md) · [设计与硬件绑定](docs/spec/design/README.md) · [问题](docs/bugs/README.md)

从仓库根运行 `./scripts/ucv info ifu`；用 `--dut <key>` 选择验证对象。
`./scripts/ucv docs ifu` 预览工作索引，`./scripts/ucv check ifu` 检查入口。

工作按 DUT＋合同认领，负责人、下一步、阻塞及证据维护在验证规格正文或关联任务中。
各 DUT 使用独立绑定和结果，shared 只承载本包实际复用的机制。

当前公开基线由根配置继承；历史基线结果保持原义。目录/收集检查不代表新基线功能验收，
原 native/RTL 工作空间已归档，当前资源由配方重新准备和构建。

[原工程说明与历史结论](docs/spec/verification/suite-overview.md)。
