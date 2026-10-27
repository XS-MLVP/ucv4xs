# 完整类型混合的LDU生产者合同（新实现前定义）

**后续纠正**：本版流水/路由合同遗漏S3的地址更新源关系，旧2/6不能作完整正常
准入。依据[完整S3合同](lsq-ldu-s3-full-domain.md)已独立重跑原8种子及18定向，新
26例17/9、762次S3源检查，旧实际输出/FAIL保持，见[S3报告](../reports/lsq-ldu-s3-20261019.md)。
不把所有域简化为`!needReplay`，异常/首次NC/再执行/S4须分别判断。

## 目标与范围

沿用开源`893e1580b`的真实`LsqWrapper`及全部下级。保留原8种子0x7100..0x7107、
八类型及权重`(30,12,3,2,36,6,4,7)`：cached/NC/MMIO/IO Load、普通/NC/IO Store、CBO。
保留Store split、VA别名、立即SID复用、数据/Cache错误、随机背压、branch/RAW/异常恢复、
600拍随机及5000边沿公平服务与取消同槽新UID完成。CBO意图sticky，不重抽，仍须真实
NoSpec/BlockBack；不增加“LSQ必须物理空”或“老Sbuffer必须先排空”的人为限制。

本合同不把旧串行混合8 FAIL追溯提升为完整正常域。新增驱动只有经过公开历史独立审计
才能给出生产者准入结论。没有原生LoadUnit/MemBlock DUT，不宣称其内部数据通路已验证。

## 可读微架构功能点

| 功能点 | 必需行为和实际检查 |
|---|---|
| LDU-MIX.pipeline | 每次Load再执行绑定原UID/ROB/LQ/SQ与同一LDU入口，依次S0 Forward、S1 PA/kill、S2 RAR/RAW、S3反馈；不能把查询提前后随机择拍/换lane反馈。无效、取消和TLB miss的Forward kill分开处理。 |
| LDU-MIX.priority | Replay原因来自真实外部事件及公开Forward/ready结果，按源优先级取单hot。C_NK只来自原STA的年龄、PA/CacheLine、mask，在S1或S2相遇；RAR nuke不生成C_NK。matchInvalid与forwardInvalid不同。 |
| LDU-MIX.revoke | S3 Replay或异常撤销上一拍同lane的查询。跨16B Load的head在S4保存、tail随后汇合；head和tail自己的查询/撤销历史分开，最终必要时撤销两拍前head，不能对齐Load假借older撤销。 |
| LDU-MIX.uncache | 首次NC/MMIO翻译仍发S2 RAR/RAW但nc标记仅代表NC replay；首次非完整转发时dataValid不常置1。真实响应后原Replay grant在S0同时发Forward与bypass；MMIO replay不发RAR/RAW且不再制造Uncache重试，NC replay仍发检查、被实际依赖阻塞时可以产生新原UID总线义务。 |
| LDU-MIX.error | 返回错误保持原SID/外部job身份，s1 PA/异常及s2 data/derr/nderr逐字段检查；真正bypass消费后S3保留原错误，不以恢复或SID新owner覆盖。错误Load不能正常ROB退休，按原UID完成/异常恢复分账。 |
| LDU-MIX.rollback | 有效RAR violation产生原ROB flushAfter，VA/PA matchInvalid产生原ROB flush；与真实RAW及branch/trap候选按绝对ROB年龄选择。老Load、年轻取消者、已退休Store副作用、在途外部job与恢复尾指针分别守恒。 |
| LDU-MIX.program | 执行与ROB退休不混同；普通Store已执行可在Sbuffer前退休，CBO许可保持；真实UID必须完成、取消或明确失败保留，fair超时须逐UID定位，不能自动定性RTL活性失败。 |

## 固定开源源码依据与配置边界

- `NewLoadUnit.scala:340-351,439-450,749-754,2123`：S0 Forward/bypass，S1 PA/kill；
  `1083-1097,1216-1219`：S2查询和dataValid、MMIO replay禁止查询。
- `NewStoreUnit.scala:384-390,505-506,922-923`和`MemBlock.scala:943,998`：同一真实S1
  STA同时进入LSQ与LoadUnit nuke检查；CBO按CacheLine，普通Store按16B且mask重叠。
- `RobBundles.scala:305-309`：完整flag/value/former年龄；新actor保持绝对ROB timeline，
  不能只按低value排序，也不能把取消前后相同ROB编码当成同代UID。
- `NewLoadUnit.scala:1111-1127,1565-1618`：UNCACHE/SMF/MA/TM/FF/DR/DM/BC/RAR/RAW/NK
  原因优先级与one-hot反馈。固定实现中`C_WF := false`、`C_MF := false`；旧抽样中的
  WAY_PREDICTION意图不重抽，显式记录其在本生产者配置无cause7输出，不伪造“正常cause7”。
  cause7接口级UT仍保留，不能因此删除整体Replay功能范围。
- `NewLoadUnit.scala:261-319,654-668,1398-1422,1481-1504`：cross-bank head/tail，
  S4保留head的VA/PA/mask/Replay，S3同lane与两拍older revoke及flush/flushAfter。
- `NewLoadUnit.scala:1009-1011,1459,1572-1579`：原bypass nderr→loadAccessFault(5)，
  derr→hardwareError(19)，异常压制一般Replay；不能只在actor记fault却给LSQ干净S3。

对齐/单word/跨16B Load都保留原随机几何，跨16B必须实际发head/tail而不是只保留低mask。
新调度可选择fastReplay仲裁不接受，使真实单hot原因进入LRQ；不能把未握手当slot释放。
本层没有DCache/Sbuffer内部返回数据端口，不伪造这些删除观察；独立SQ转发PA字节性质
与实际Sbuffer消费仍由严格参考及原事务账本检查。原有exact128保护不作无证扩大。

## 验证顺序与交付边界

先运行原8种子完整类型尝试，任何严格失配均普通FAIL；再从实际停止前缀独立重建
阶段、dataValid、MMIO禁查、revoke、原slot、共享恢复和外部job，不拿actor宣言作答案。
若驱动自身违反合同，保留该次拒绝并开新目录修复重跑；不能改旧轨迹或把它归为RTL。
成功前缀不能替代完整600/fair/同槽义务；本合同不缩小联合容量/CBO分阶段、reset、
其余exact128及最后全层次请求→实际证据审计的必需范围。
