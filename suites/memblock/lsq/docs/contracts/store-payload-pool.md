# Store 全宽载荷与正常同槽复用契约

本补例在开发测试前定义，针对 regression15 中 Forward、PhysicalStoreQueue、
StoreQueue 的 VA 高位、PA 页号和各槽数据 toggle 缺口。固定原样 RTL、Picker
native build、三类覆盖分母及既有失败均保留；本合同不是整条 Store 路径签核。

## 语义功能点

| 功能点 | 微架构行为与实际检查 |
| --- | --- |
| `FWD-PAYLOAD.pool` | 全部 64 个公开 Store bank 槽依次保存高地址全一、低地址槽号/字节图样、高地址互补图样、低地址全零的四代数据；每槽在三条查询入口都返回自己的完整 16B，而不是旧地址、旧代、相邻槽或被截断的数据。独立逐字节来源检查和每拍参考模型始终开启。 |
| `PSQ-PAYLOAD.pool` | 两路真实 STA/STD 写入全部 64 槽，在未授予退休许可且 Sbuffer 背压时不得提前完成；三路转发检查全部有效字节后，再授予退休许可，实际 Sbuffer fire 的 VA/PA、全 mask、128 位数据必须与外部 UID 台账一致。真实出队后用同一物理槽写入新代，不用 reset 冒充复用。 |
| `SQ-PAYLOAD.pool` | 经过真实 dispatch→VSQ→PSQ 的每代 64 个 flow 完成相同的写入、查询和 Sbuffer 消费；真实 ROB 前进产生许可，PSQ 出队反馈最终释放虚拟所有权并报告 empty。四代必须仍为同一组物理槽但完整 SQ 身份不同。 |

## 合法域、时序与边界

- 每代 64 个互不重叠、16B 对齐、size=4 的完整写。STD 使用既有真实
  producer 的 Q 编码 `fuOp=0x208`，数据 128 位；mask 由真实 PSQ 生成，
  不输入任意孔洞、不注入内部寄存器。
- 第 0 代 VA 为 `(2^50 - 2^20) + slot*16`，PA 为
  `(2^48 - 2^20) + slot*16`，数据为 `2^128-1`；第 1 代 VA 为
  `0x200000 + slot*16`，PA 为 `0x1000000 + slot*16`，数据为下面的槽号图样。
  VA 的高地址为保留 50 位的符号扩展地址；PA 在保留 48 位接口内。
  第 2 代重复第 0 代的地址但数据为第 1 代逐位互补，第 3 代重复第 1
  代地址而数据为全零。第 1 代数据按 little-endian 字节
  `(slot*19 + byte*31) % 256` 生成，区分不同槽与不同字节；这避免只用
  所有槽相同的高/低值而无法观察同代串槽。初始两代 probe 只使用全一、
  全零；正式补例增加图样和互补图样，probe 不代替正式结果。
  同一个翻译 VA/PA 的 12 位页内偏移必须一致。地址翻译、PMP、cache
  存储容量不在这些 LSQ DUT 内；本用例只声明其公开接口的生产者合法域。
- 所有地址和数据在对应 UID 的 STA/STD 事件前由外部台账确定。三路查询
  使用独占的 load SQ 上界 `head+64`，四代分别为 64、128、192、256，不使用
  越过物理窗口的查询冒充合法转发。
  测试仅定制尚未发行的外部 producer record，并记录 `payload_before_issue`；
  不改通用 actor/参考模型的实现及历史失败栈位置。初次 probe/正式 -01
  使用过等价的 actor 可选载荷参数，其结果仍保留；最终 -02 使用此隔离方式，
  各自的 source aggregate 不混用。
- 父级先阻止退休/预提交，Sbuffer ready 全为 0，写入和查询期间不允许
  出队；查询时 bank 稳定。查询 S0 后下一拍提供相同页偏移的 S1 PA，
  仅在有效 S2 检查数据、mask 和 replay/dependency 标志。
- 公平排空阶段打开两条 Sbuffer lane；每个 UID 必须且只能被消费一次，
  原有 actor 的地址、mask、数据、出队时序检查保持生效。每一代开始前
  前代全部实际完成；不使用取消、reset、空闲拍或模型内部槽表代替完成。
- ForwardModule 无 reset 引脚，沿用无效查询排空；父级 fixture 正常 reset
  后开始。无效响应的数据为 don't-care，不为增加 toggle 去比较或认可它。

## 覆盖与证据

1. 三层分别使用 fresh baseline/after；每对使用相同 source aggregate、
   相同 native build、相同点全集，baseline 节点在 after 全部保留。
2. 保存三类非 wrapper 原始点和 LCOV 原始源码行的前后差集，不混为同一
   line 指标，也不跨父级/叶子相加。与 regression15 的缺口交集仅作集合
   对照，不回填其统一回归分子。
3. 父级目标位为真实 `dataEntries_<slot>_data[0..127]` 的两个方向，
   共 `64*128*2=16384` 点。Forward 叶子没有这些持久寄存器，只核验
   对应公开 Store bank 全宽 data 输入点，不把它称为内部存储覆盖。
4. compact witness 保留每代完整槽集合、地址/数据、768 个三路有效响应
   的摘要、256 个父级真实完成 UID 和消费摘要；不生成逐拍 JSON、波形
   或完整源码副本。真实失败保留，不 skip/xfail，不改 RTL。

本补例不覆盖别名、跨 word/page、CBO、NC/IO、异常、取消中的新情形，
不能关闭它们的既有 FAIL，也不能代表完整 Wrapper 混合 Store/Load 已通过。
