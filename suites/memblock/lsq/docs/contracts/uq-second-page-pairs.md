# 两槽 UQ 第二页：高/低 PA、真实跨页 Store 与原 UID 完成

本合同先于新增测试实现。目标是当前 PSQ/SQ/Wrapper 中 UQ 第二页 PA 高位、
两路请求与真实存储/消费方向缺口，不以空闲 payload 翻转代替功能检查。
固定开源 RTL/Chisel、Picker native build、X Reactor 与独立参考模型保持。

## 语义功能点

| 情形 | 人类可读的语义与实际检查 |
|---|---|
| `UQ-PAGE.paired_lifetimes` | 两个按 SQ 程序顺序接受的第二页同时占有两槽，背压期间 head/forward 的完整 SQ 与页号保持；满池对下一有效请求不偷接，之后真正消费并复用槽，返回新页而非旧页。|
| `PSQ-PAGE.paired_lifetimes` | 两个普通 8B Store 从页末 offset4092 跨到各自非连续第二页；真实 STA/STD、第二页 ready/valid 和尾 STA 到达后，未获退休许可不能提前写出。消费时先后两个 4B 片段的 VA、PA、mask 和原字节必须正确，只完成一个 Store UID。|
| `SQ-PAGE.paired_lifetimes` | VSQ 实际派发产生 SQ 身份与许可，PSQ/UQ 保留真实连接。允许 ROB 前进后两段真实消费和出队完成，跨四组 SQ flags 正常复用，不以 reset/取消回收资源。|
| Wrapper 复合情形 | 每个跨页 Store 后真实派发一个读其第一页最后 4B 的 Load；UQ 的第二页已真实接受、尾 STA 已完成后，查询第一页仍须得到该 Store 的原低 4B。原 Load 用相同 SQ/LQ/ROB/uop 执行 S3，最后 Store 两段和原 Load 均正常完成。使用原 `LSQ-FORWARD.page/sqid/wrap` 功能，不改变原 82 项分母。|

## 具体合法生产者轨迹

- 八组主对的起始 SQ 绝对位置为 0、62、64、126、128、190、192、254。
  每组两个跨页 Store，其他位置用普通已完成 Store 真实推进；最终恰好完成
  256 个 Store，其中 16 个跨页、240 个普通填充。无内存直写/指针改写。
- profile 为偶数时第二页 page 分别为 `2^36-1`、`2^36-2`；奇数时为 0、1，
  都转换为 48 位、4KiB 对齐 PA。零页与高页属于本 LSQ 保留接口合法域，
  不代表集成 PMP/页表/存储总线已验收；输入低12位始终为0，不人为翻转非法位。
- 第一页 VA/PA 页内 offset 均为4092，普通 8B Store 分成第一 word 的
  byte12..15 和第二页 word 的 byte0..3，第二段必须使用真正握手的页 PA。
  每组两个 producer 地址不同、数据不同，不能只用同值掩盖串槽。
- 公共两路第二页入口由该对第0/1个 owner 各自使用，完整 SQ 必须与真实
  连续地址就绪前缀相同；valid 持续到 ready/fire 后才撤销。先第一 STA/STD，
  再第二页真实握手和尾 STA，最后才允许退休/消费。
- PSQ/SQ 每组第二页未发行前可定制外部 producer record，发行后不改地址、
  数据或身份。只在真实 fire 后更新外部 page-sent 台账，参考模型仍逐拍检查。
- Wrapper 三条测试分别用 Load lane0/1/2。Load 只读第一页4B，未声称 UQ
  第二页可直接安全转发；第二页功能通过真实 Sbuffer 第二片段检查。
- Leaf UQ 另保留满池等待的第三个有效请求，直到消费腾出槽后真实接受并消费；
  不以撤销未握手请求或 invalid payload 翻转冒充完成。叶子只证明第二页队列，
  不冒充父级 Store/Load 生命周期。

## 边界和证据门禁

fixture 仅开头 reset；所有主对之间正常消费、出队，不 reset/取消。本补例
不替代恢复、异常、MMIO/NC/CBO、跨页 Load、禁用反馈或完整总线域，历史 FAIL
和全部原节点保留。无效数据位不比较，不把输入 PA 低12位的常零当动态增益。

每层 fresh baseline/after 同源摘要、同 build、line/toggle/branch 点全集，
记录目标 UQ 页位和源位置、差集/LCOV、compact 公开握手及原 UID 消费 witness。
随后完整贡献范围实际重跑：原四 build 的1072节点，加原 leaf UQ全部41节点，
再加新6节点，总1119；五 build 均保留自己的分母与历史失败，不能 OR 冒充运行。
结果不回填 regression15。只保留摘要、失败、compact witness 和覆盖，不生成
逐拍 JSON、波形、完整源码副本，不改共享 actor/参考模型或 RTL。
