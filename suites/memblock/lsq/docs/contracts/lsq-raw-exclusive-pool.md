# RAW容量等待在真实120项Replay池内的保存与排空（补例前定义）

`lsq-raw-exclusive-05`首轮端点自身Replay仍缺16243条本体DA，其中大量是尚未访问的
slot/入口的原exclusive blockSqIdx保存及bank选择；这是既有容量Replay功能的缺少情形，
不是把每条寄存器行虚构成新微架构功能。新增12个**独立Replay DUT**补例：

- 外部合法RAW满池条件下，以Load exclusive SQ比address-ready领先128保存120个
  不同ROB/LQ/checkpoint的原Load。三个S3入口分别覆盖，起点0/255覆盖完整SQ flags。
  全部原Load必须一直等待，不能由物理低6位相同、LQ头或SQ空假唤醒。
- 分别由外部真实RAW信用解除（rawFull降0）或地址前缀到达exclusive tail解除；原
  请求只进一次，grant按真实valid/ready记账、原slot/ROB/LQ元信息不串用。冷却/背压
  只影响选取/握手时间，不允许丢失某个owner或重复grant。
- 120个原owner都实际grant后逐原slot反馈释放；所有原UID完成后full/allocate/valid
  清除。不能仅填池再reset/取消，也不直接写slot、私有ready或参考状态。

这12例是独立Replay输入合同：rawFull/address-ready在此由外部环境提供，**不是**
Wrapper中同时填满所有父池的证明。真实Wrapper的128 Store/56 RAW/第57 Load六例
已另有完整原效应；正常全池联合/CBO分阶段和八类型随机仍必需。
