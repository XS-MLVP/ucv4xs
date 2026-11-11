# 后续正常CBO生产者合同：先纠正真实StoreUnit元信息，再重跑

这是在新用例/代理修正之前补充的合同，**不是通过声明**。原Wrapper合同的82项
可读行为和全部FAIL保持；这里补的是既有CBO/Forward/RAW/公平业务的生产者情形，
不是删减目标或排除合法失败域。当前统一回归08已启动，须先捕获其结束源，不能
在运行期间改变它的启动文件；下列修正随后使用全新目录运行。

## 已核对的真实公开生产者

固定开源`893e1580b705d81f113c30c7a05734e09a08050e`：

- `NewStoreUnit.scala:98-102`：CBO的mask固定`Fill(VLEN/8,1)`，本配置为0xffff，
  不沿用普通8字节mask255。
- `NewStoreUnit.scala:433-438`：CBO PA/VA对齐到16B，`size=MemorySize.QB`、
  `wlineflag=isCbo`；`MemCommon.scala:169`的QB编码为4。
- `LSQWrapper.scala:206,252`：同一真实STA包分别直接进入StoreQueue及LoadQueue
  的RAW探测，不能只把PSQ字段改成正常却给RAW留下wline=false。
- `NewStoreQueue.scala:1966`：STD的CBO.zero数据写入强制0，外部STD data即使
  DontCare也不能改变有效零数据；非zero CBO仍不得伪造可用转发数据。

## 必需修正及行为检查

1. 新混合/联合正常生产者的CBO0..3均使用实际QB/全mask/wline/对齐，保留同一
   UID、完整ROB/SQ代及真实STA→S2属性。普通Store的原size、split、别名与背压
   域不能为了CBO修正而删除或变保守。
2. 老普通Store、年轻CBO、再年轻真实Load必须保留实际PA字节来源及重放安全。
   CBO.zero可提供该line有效零数据；其他CBO若是有效最年轻候选必须要求重放，
   不能回退老非零字节。正常QB正条件与size3等独立接口边界分别记账；后者不能
   作为正常StoreUnit/Backend可达缺陷证明。
3. CBO的RAW探测同样用真实全mask/wline/ROB/FTQ。不能只修转发避免触发RAW；
   正rollback必须原字段正确、真实shared redirect及取消后同槽新UID完成。
4. zero自己的实际16字节零片段、Cache0..2请求/响应、原WB/异常及随后SQ连续
   完成保持必需。老Sbuffer背压时年轻ROB头的合法preCommit仍允许，不加read==head
   或严格早于ROB头限制来换通过。
5. 保留原8全域固定种子和6联合情形的历史结果。新正常元信息须独立检查后重跑，
   不能把旧接口绿色结果“提升”为正常证明，也不能把接口范围现象登记成正常
   CBO架构缺陷。其他已合法观察的SID/串行所有权/zero后果，分别核对其自身
   生产者前提；不得靠本次新条件一概抹去普通FAIL。

## 补例前的正常全槽完成要求

新`test_normal_cbo_paths.py`在两个真实STA lane分别完成全部64物理槽×4个CBO
子操作，共512个正常QB CBO及各自的原Load。逐个实际Cache req/resp或16B zero
消费，再原WB fire、SQ/LQ释放，覆盖完整SQ四代和ROB回绕；保留旧size3接口例。
该全槽补例针对既有CBO行为的缺失正常生产者情形，不是新增STRESS验收标准。

## 当前证据的限制

`results/lsq-expanded-16/cbo-producer-audit-v1.json`将仅从真实源码和原始公开包
核对元信息；前轮独立生命周期/峰值审计不能代替这个生产者门禁。正常域修正、
新用例实际运行/逐行分析及完整回归之前，三个STRESS仍未checked，目标继续active。
