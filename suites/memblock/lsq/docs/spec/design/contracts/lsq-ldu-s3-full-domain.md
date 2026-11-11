# 全类型LDU的S3写回与S4合并（新代理/重跑前合同）

沿用893e1580b与真实LsqWrapper全部下级。旧18例15/3、原8种子2/6、S3拒绝及全部原件
保留；不改目标RTL/参考/比较mask，不用新的名字追溯给旧流正常域准入。

## 可读微架构关系

1. **首次非缓存访问不是完成。** 首次NC/MMIO/IO通过TLB/PMP得知isUncache，需先入
   原Uncache/LRQ等待；无异常、无matchInvalid时不应S3写回更新地址，即便RAR/RAW已查。
2. **再执行的属性来源不同。** 原总线响应被原bypass消费后，S1 `noQuery`取原PA，
   `TlbAccessResult.noQuery`不是TLB hit，S2不会再次识别原PBMT/PMP为isUncache。
   NC replay仍进行RAR/RAW并可能因依赖重试；MMIO replay走always-writeback且不查。
   不能只用最终lqWrite.nc/mmio标签反推该拍S2 isUncache。
3. **普通Replay与完成分开。** 无异常/VA-PA mismatch/prefetch的请求仅在无Replay且
   非首次isUncache时writeback。异常或matchInvalid即使其他Replay原因同时存在也可能
   要writeback；所以不能把所有域的更新都简化成`!needReplay`。
4. **S4 head与tail分别保留。** head有异常或matchInvalid时，headAlwaysWriteback为真，
   最终写回不被tail的Replay压掉；否则只有head本可正常writeback且tail也可writeback
   时最终更新。head自己的Replay/异常已撤销自己的查询，tail同lane和older revoke仍按
   原合同；不伪造对齐Load作为S4。
5. **S3字段按最终源赋值。** alignedType为当前tail/非split请求size，last_beat来自
   最终PA bit6（S4选择head PA），updateAddrValid来自上述实际writeback；ROBLQ/原slot、
   例外位与Cause优先级保持。异常优先选择head，不应不加选择地把两代元信息混在一起。

## 固定源码依据

`NewLoadUnit.scala:608-610,713-719`的noQuery/PBMT/PA；`927-929`仅TLB hit识别
isNC/isMMIO；`1059-1061`的alwaysWriteback与troubleMaker；`1145-1146`预计算wakeup/
writeback；`1398-1422,1431-1457`选择head PA、异常及writeback；`1516,1544,1596,1607,1613`
输出字段；`1716-1717`保存headAlwaysWriteback/writebackDependOnTail。

## 实施与验收门禁

新增独立代理只修生产者S3元数据，不增随机调用，不删原0x7100..0x7107/八类型权重、
sticky CBO、600随机/fair、别名/split、立即SID复用、Cache/Bus错误和恢复。独立重跑
同18个RAR/原96满池定向，保持原行为与普通FAIL，不删除前拍release。

独立审计只用公开S0/S1/S2/S3与实际grants/响应重建，不能读actor声明作为答案，也不能
沿用旧“updateAddrValid总为1”的错误门禁。compare/knownness/PA安全检查不放宽。若新
字段纠正改变后续公开输出/随机交错，逐项定位，不能默认相等；未到达的错误/S4组合仍
明确未证明。随后逐原DA审计与补例重跑，不能以本26例代替联合容量/CBO或完整目标。
