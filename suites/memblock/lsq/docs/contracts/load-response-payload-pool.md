# Load响应池：原UID数据、独立错误与源正确S3

先定义本合同，再新增用例。固定开源893e1580b、Picker/X Reactor、目标RTL/Chisel、
共享参考和既有actor保持；不重复已完成的1182节点或叶子已满的数据方向。

## 语义功能点与实际缺口

| 层次/功能点 | 行为与必须检查的生命周期 |
|---|---|
| LQU `LQU-BYPASS.payload_pool` | 每个真实mid依次保存0/全64位1/0/全1响应，两种NC/MMIO与error/nderr四组合独立；原请求身份、ack绑定、wake、bypass s1原PA/异常及s2复制128位数据全部比较后才完成。 |
| LQ `LQ-UNCACHE.payload_pool` | 首次Uncache的S3不能完成VLQ；实际总线响应唤醒Replay后，经真实slot grant和bypass取原数据，再以源正确S3反馈，最后真实LQ前缀释放。全部16mid实际数据方向分别核验。 |
| Wrapper既有BUS/EXCEPTION功能点 | 保留真实LoadQueue/StoreQueue连接，不伪造内部SQ反馈；在空Store分支的正常对齐Load情形执行同样的S0/S1/S2/S3、总线/Replay/bypass及错误链。它不是完整混合LSQ验收，原混合/SID失败必须在完整运行中保留。 |

最新dat中LQU与Wrapper的UncacheEntry数据方向已命中，但LQ仍有591个uncacheData
方向缺口，且entry输出数据各有同等未命中；本轮不得把LQU/Wrapper已有命中当作
完整新增点。每层各自native build、完整点全集与前后缺口集合独立保留。

## 外部生产者与时序

- 一次只保留一个原Load/总线事务，两种类型各4轮×16个真实mid，合计128个新
  Load。四轮数据0/all1/0/all1，error/nderr为00/10/01/11。实际mid来自公开bus
  handshake，不读取参考或内部FreeList选择刺激；每轮必须实际覆盖16个mid。
- 地址使用对齐、低位canonical VA/PA，GPA为0且Hyper关闭，不用无效高VA或源
  异常刷payload。只有总线响应可以引入error/nderr，source异常不能在首次入队
  时非零（真实Uncache会过滤）。SID回收在实际response后，原数据消费也完成；
  这是正例，不代替已回包未消费时同SID新回包的原必保留失败。
- LQ/Wrapper首次S0/S1保持同lane，首次S2可查询RAR/RAW但dataValid=0，S3为
  C_UNCACHE、updateAddrValid=0且revokeLast。真正返回后取得原slot，replay的
  bypass s1为原PA与错误信息、s2为原64位复制两份，不做凭空移位或符号扩展。
- NC replay仍走RAR/RAW，MMIO replay不查；S3 size/lastBeat来自原size/PA，
  错误映射为loadAccessFault(bit5)/hardwareError(bit19)，进入uop及Load exceptions。
  有错误或正常完成均按源关系updateAddrValid，不能沿用旧“首次uncache也更新”
  或“最终S3丢掉响应异常”的驱动。
- 错误Load在LSQ本地写回/释放后，ROB头保持其身份，外部输入一个相应flushSelf
  异常redirect，待真实恢复/stall结束才分配下一UID；不宣称Backend trap实现已验收，
  不把异常写回当架构提交。被取消的ROB槽可由新UID复用，无活动事务跨半环。
- 无reset，三lane轮换。LQU本体不含VLQ/Replay，仅声称其公开消费；LQ/Wrapper
  必须实际slot反馈、S3和公开LQ释放，不能把leaf完成回填父级。

## 运行和保留

各层fresh baseline/after同source aggregate/build/三类点全集；原节点/主检查流和
旧命中保持。随后将LQU、LQ完整目录纳入原六build全部贡献范围，先完整fresh
基线，再加3新节点完整fresh运行。所有原172失败及LQU/LQ原失败须保留，实际
collect/manifest核验；不OR旧dat、不删分母、不skip/xfail。

只有compact原UID/mid/sid/数据/错误/slot/S3/实际释放与异常恢复摘要、失败和覆盖。
既有SID失败、跨页/S4、禁用反馈、128容量完整核producer、release-wait与最终38-DUT
扩大统一回归继续开放；本补例不是用较容易的串行正例替代这些完整域。
