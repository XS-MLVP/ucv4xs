# Frontend — Design spec

状态：草稿，待设计确认。基线：由工程 ucv.json 继承。

## 职责与上下游

`Frontend` 为 XSCore 实例化的真实顶层闭包。内部连接 BPU、FTQ、ICache、IFU、IBuffer、
InstrUncache 与取指地址翻译/权限检查；向后端提供指令及控制反馈，接收 redirect、WFI、
CSR/fence 控制。FrontendBridge 在 MemBlock 内，不能假定在本 DUT 闭包中。

## 接口、配置与合法输入

当前配置与真实端口以工程 binding、完整生成 RTL 和后续 Picker 导出为准。后端控制、
TL/PTW 响应和 CSR 更新的合法域及时间关系待设计确认；不得默认每个输入位任意组合合法。

## 行为要求、时序与并发

集成责任草案见 [FE-INT-01..04](../verification/frontend.md)。单元行为仍由各包合同维护；
本层需确认跨接口接受/终结、背压、取消/迟响应、WFI 和控制事件传播。

## 依据与待确认问题

源码接线观察：`Frontend.scala:220–268`，含 WFI 双通道汇合、IFU/FTQ/ICache/IBuffer
连接及非缓存 flush 常量绑定。设计 owner、接口时序签核、独立预期和可观察性仍待确认。
这些观察描述实现事实，不代替行为规格或新基线验收。
## 切分与硬件绑定（2026-11-16）

逻辑身份：`frontend_top/frontend`；生成 top：`Frontend`。

源码位置：`src/main/scala/xiangshan/frontend/Frontend.scala:106`。

实例样本：`XSTop.core_with_l2.core.frontend`。

绑定样本为 `public-e716c7658 / DefaultConfig / 单核 / CHI E.b / OpenLLC`，含 `--fpga-platform --reset-gen`。父实例和源码位置登记在 workspace.json。

当前只确认设计身份、来源与切点；上面的接口、合法域和独立行为合同仍待评审。同名类型、参数复用或父级包含关系均不构成覆盖证据。
