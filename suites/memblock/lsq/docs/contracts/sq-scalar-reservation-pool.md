# 128标量预留池：模块容量接口域与完整核可达性分开

本合同先于新增用例。固定开源RTL/Chisel、Picker、X Reactor与共享参考/actor保持。
承接1180-node完整运行，不重做已完成的64flow退休或4..128叶子取消。

## 功能点与域标签

| 功能点 | 微架构行为和必须实际检查的义务 |
|---|---|
| `SQ-INTERFACE.scalar_pool` | LSQ容量接口上预留128个独立标量Store uop（各1flow），真实VSQ达到满池。仅当前64物理位置允许STA/STD；更老的非访存分支redirect flushAfter取消全部128项，恢复到原exclusive尾，旧UID没有Sbuffer副作用。128个逻辑位置分别由不同新UID复用，所有新原始字节实际消费、正常出队。 |
| Wrapper整池恢复 | 同样的128标量Store接口容量情形保留真实LoadQueue/StoreQueue全部下级；另有一个年轻Load未执行即取消，恢复后同LQ槽新Load在新Store取原PA有效字节并完成原S3。Store所有128逻辑位置精确复用，不只按64物理低位证明。 |

域标签固定为 **`UNIT_INTERFACE_LSQ_CAPACITY`**。LSQ侧分配数量、尾快照、恢复、
ROB年龄、STA/STD窗口均合法，但**不宣称固定完整核有可实现的全套上游流水历史**。
固定Rename的numLsElem=1与LSQ比较器可证明本例的标量payload和LSQ准入规则；
固定Parameters的STA0/STA1各16-entry IQ只共32项，完整核能否同时保留64条
未执行STA还需要额外资源/流水证明。因此本补例不得给“正常完整核128项可达”
验收背书，也不把缺乏证明反过来当作全局不可达豁免。其他配置仍在总目标范围内。

## 两轮公开输入与独立账本

- 物理/虚拟逻辑起点0、128两轮，每轮128个旧标量uop全部分配、只执行前64项。
  ROB头保持在所有Store之前的一个非访存分支；redirect在该更老分支flushAfter，
  不是取消已获preCommit许可的Store。dispatch与redirect互斥，stall内不派发。
- SQ用共享StoreActor，uop lane0/1交替使每拍最多两个Store dispatch；只用外部
  UID/ROB/位置和真实端口作决策。没有参考/内部内存读写来直接构造cancelCount。
- 每轮旧128 UID无消费、无正常完成；恢复尾必须等于该轮base%256。每个新UID
  的绝对逻辑位置等于对应旧位置，UID不同且更大，新原PA/mask/字节实际fire、
  延迟出队。新128Store可逐步滑动64发行窗，不能越过未释放槽覆盖旧代。
- Wrapper每次dispatch至多两个Store；旧Load占年轻ROB、同一全局顺序，旧Load
  没有S3发送。新128Store分两64窗口真实完成，每次ROB前进至多8个Store项，
  不一次跳过64/128个活跃项；第二窗口准备好后，新Load在末Store查字节并走S3。
- 两轮无reset，正常256个新Store、取消256个旧Store；Wrapper另正常2个新Load、
  取消2个旧Load。ROB活动跨度不达到160-entry半环；取消ROB槽可复用，但UID新建。
- `sqFull`不是已优化删除的VSQ canAccept/full。真实NewStoreQueue:1549/2076/
  2150及导出PSQ:16123规定它是寄存预留flow数>128，恰好128时仍为0。首探测
  错把它当虚拟满池而产生两个checker FAIL，原probe-01保留；正式检查其精确0值，
  不删除参考/字节/恢复比较，也不非法派发第129项来刷full信号覆盖。

## 覆盖、保留与完成边界

目标是SQ cancelCount[7]双方向及满池/恢复控制；Wrapper已命中的相同计数不预设
增益。每层fresh baseline/after同source aggregate、同build和三类点全集，旧节点、
主检查摘要和旧命中保持。指标仅称模块容量接口域动态覆盖，不回填统一regression15。

原1180节点加SQ/Wrapper各一节点，完整六build预计1182，实际collect/manifest
核验；保留全部172FAIL全文，包括头许可flushSelf旧UID315失败，及Wrapper主目录
外41贡献者。不得用成功的更老分支取消替代原Store自身取消失败。

仅保存compact UID/分组/旧执行64与未执行64/实际恢复和新完成摘要、失败与原生
覆盖，不保存逐拍JSON、波形或完整新源码副本。整体仍须继续正常核producer域、
128flow退休bit7、release-wait、异常/总线/跨页Load及最终扩大回归和全范围审计。
