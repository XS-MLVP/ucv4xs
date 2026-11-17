# Slice_4 — Design spec

状态：草稿，待设计确认。基线：由工程 ucv.json 继承。

## 职责与上下游

TODO

## 接口、配置与合法输入

TODO

## 行为要求、时序与并发

为每条要求分配稳定 ID；记录 reset/redirect/异常及不变量。

## 依据与待确认问题

TODO：规格来源、设计 owner 与 review 结论。
## 切分与硬件绑定（2026-11-16）

逻辑身份：`llc/slice`；生成 top：`Slice_4`。

源码位置：`XSCache/src/main/scala/openLLC/Slice.scala:27`。

实例样本：`XSTop.chi_openllc_opt.slices_0`。

绑定样本为 `public-e716c7658 / DefaultConfig / 单核 / CHI E.b / OpenLLC`，含 `--fpga-platform --reset-gen`。父实例和源码位置登记在 workspace.json。

当前只确认设计身份、来源与切点；上面的接口、合法域和独立行为合同仍待评审。同名类型、参数复用或父级包含关系均不构成覆盖证据。
