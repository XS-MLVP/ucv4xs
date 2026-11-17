# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`mem_misc`](mem_misc.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

MemMisc 的 TileLink/AXI 路由、位宽/ID/顺序适配及外设挂接集成；AIA、PLIC、Debug、Timer 的内部功能分别归对应 suite。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `mem_misc` | `MemMisc` | `src/main/scala/system/SoC.scala:507` | `XSTop.nocMisc` | 骨架；待实现 |
| `axi4_deinterleaver` | `AXI4Deinterleaver` | `rocket-chip/src/main/scala/amba/axi4/Deinterleaver.scala:44` | `XSTop.nocMisc.axi4deint` | 骨架；待实现 |
| `axi4_id_indexer` | `AXI4IdIndexer` | `rocket-chip/src/main/scala/amba/axi4/IdIndexer.scala:59` | `XSTop.nocMisc.axi4index` | 骨架；待实现 |
| `tlfifo_fixer` | `TLFIFOFixer` | `rocket-chip/src/main/scala/tilelink/FIFOFixer.scala:44` | `XSTop.nocMisc.fixer` | 骨架；待实现 |
| `tl_fragmenter` | `TLFragmenter` | `rocket-chip/src/main/scala/tilelink/Fragmenter.scala:84` | `XSTop.nocMisc.fragmenter` | 骨架；待实现 |
| `queue` | `Queue2_TLBundleA` | 依赖库 `src/main/scala/chisel3/util/Queue.scala`；实例化位置见 workspace | `XSTop.nocMisc.llc_to_peripheral_buffer_0.nodeOut_a_q` | 骨架；待实现 |
| `repeater` | `Repeater` | `rocket-chip/src/main/scala/util/Repeater.scala:10` | `XSTop.nocMisc.widget.repeated_repeater` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
