# FrontendBridge — Design spec

状态：草稿，待设计确认。基线：由工程 ucv.json 继承。

## 职责与上下游

MemBlock 内的前端总线桥，组合 ICacheBuffer、ICacheCtrlBuffer、InstrUncacheBuffer 三路。
源码位于 `MemBlock.scala:318–325`，实例由 `MemBlockInlined` 创建。

## 接口、配置与合法输入

各缓冲双向处理 A/D 通道。当前源码中非缓存请求强制为 Get，并固定 data/mask/size/source；
合法输入域、每路可同时在途数量、reset 前提与响应身份需结合 TL 协议及真实导出端口确认。

## 行为要求、时序与并发

待评审责任见 [FBR-INT-01..04](../verification/frontend_bridge.md)：三路独立保序、背压稳定、
请求/响应守恒、非缓存固定字段合法性及 reset 边界。此处不是 Frontend 取指取消合同。

## 依据与待确认问题

设计 owner 和协议/时序 review 尚未确认。源码表示真实接线与字段生成方式，不是独立
正确性依据。三类缓冲是否可复用完整 testbench 须在核对字段合法域后决定。
## 切分与硬件绑定（2026-11-16）

逻辑身份：`frontend_bridge/frontend_bridge`；生成 top：`FrontendBridge`。

源码位置：`src/main/scala/xiangshan/mem/MemBlock.scala:323`。

实例样本：`XSTop.core_with_l2.core.memBlock.inner_frontendBridge`。

绑定样本为 `public-e716c7658 / DefaultConfig / 单核 / CHI E.b / OpenLLC`，含 `--fpga-platform --reset-gen`。父实例和源码位置登记在 workspace.json。

当前只确认设计身份、来源与切点；上面的接口、合法域和独立行为合同仍待评审。同名类型、参数复用或父级包含关系均不构成覆盖证据。
