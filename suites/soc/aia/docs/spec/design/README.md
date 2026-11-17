# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`axi4_aplic`](axi4_aplic.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

APLIC、IMSIC 总线侧和核心 CSR 侧的独立合同；实际跨 MemMisc、XSTop 与 CSR 放置。端到端中断投递仍需系统集成证据。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `axi4_aplic` | `AXI4APLIC` | `ChiselAIA/src/main/scala/APLIC.scala:411` | `XSTop.nocMisc.aplic` | 骨架；待实现 |
| `aplic` | `APLIC` | `ChiselAIA/src/main/scala/APLIC.scala:104` | `XSTop.nocMisc.aplic.aplic` | 骨架；待实现 |
| `axi_reg_imsic` | `AXIRegIMSIC` | `ChiselAIA/src/main/scala/IMSIC.scala:832` | `XSTop.imsic_bus_tops.axi_reg_imsic.axireg` | 骨架；待实现 |
| `axi4_map` | `AXI4Map` | `ChiselAIA/src/main/scala/common.scala:280` | `XSTop.map` | 骨架；待实现 |
| `imsic_bus` | `imsic_bus_top` | `src/main/scala/device/imsic_axi_top.scala:80` | `XSTop.imsic_bus_tops` | 骨架；待实现 |
| `axi_reg_imsic_wrap` | `AXIRegIMSIC_WRAP` | `ChiselAIA/src/main/scala/IMSIC.scala:720` | `XSTop.imsic_bus_tops.axi_reg_imsic` | 骨架；待实现 |
| `imsic_wrap` | `IMSIC_WRAP` | `ChiselAIA/src/main/scala/IMSIC.scala:461` | `XSTop.core_with_l2.core.backend.inner_intRegion.intExuBlock.exuALU0_AluCsrFenceLink.csr.imsic` | 骨架；待实现 |
| `imsic` | `IMSIC` | `ChiselAIA/src/main/scala/IMSIC.scala:163` | `XSTop.core_with_l2.core.backend.inner_intRegion.intExuBlock.exuALU0_AluCsrFenceLink.csr.imsic.imsic` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
