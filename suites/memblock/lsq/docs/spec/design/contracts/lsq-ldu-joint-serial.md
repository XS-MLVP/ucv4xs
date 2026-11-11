# 联合容量后的串行总线缺口（补例前定义）

`lsq-ldu-joint-phases-03`的真实自身DA是50902/59602，本体111/114。逐行发现
顶层1505、1507、1508仅未激活`uncacheOutstanding=false`的串行pendingstate选择与
响应归空路径，属于既有LSQ-BUS.serial/ack_route/resp_route的缺少情形，不是本次
新整体功能。Deq缺少NC/IO、UncacheEntry缺MMIO/IO属性也应通过正常源一起补，而
非只翻转开关打覆盖。

补例采用固定单一ROB时间线，NC/MMIO/IO Load与NC/IO Store共五类型×三LDU/Store
lane轮转。每例只有一个原外部owner，真实accept→方向ack→原sid响应；Load必须沿
S0/S1/S2/S3首次Uncache、原Replay grant、S0 bypass再执行及原slot反馈真正完成；
Store则检查真实STA/STD/S2、ROB许可、NC ack后执行或IO实际WB，再SQ释放。随后
同一ROB时间线派年轻cached Load并完成，确认不是只得总线包而队列留有义务。

源字段、已知性和严格458输出不改。串行模式由DUT自己阻止多外部请求，不是把SID
使用延长到Load消费；立即复用故障仍在原period1六例及完整随机中普通保留。本15例
仅补实际缺口，不能替代完整八类型随机/CBO/backpressure或把三个STRESS勾成通过。
重跑要保留已有12节点的公开历史/六SID失败，再按本次DA证明新增和旧命中丢失数。
