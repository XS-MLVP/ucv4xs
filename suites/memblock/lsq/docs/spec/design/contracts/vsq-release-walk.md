# VSQ 恢复 release→walk：退休前缀、公开恢复尾和正常复用

本合同先于新增测试。固定开源 RTL/Chisel 不改；验证层次为真实 VSQ 叶子、
StoreQueue（保留 VSQ/PSQ）与 LsqWrapper（保留 Load/Store 两支）。

## 功能点与合法轨迹

| 功能点 | 微架构语义和检查义务 |
|---|---|
| `VSQ-WALK.prefix_windows` | ROB 越过的 Store 前缀可以先从虚拟队列释放，但未退休的幸存项不能被取消。redirect 必须返回最后幸存项的 **exclusive physical end**，不是 ROB 数或虚拟项数；恢复窗口不能接新 dispatch。叶子只能证明公开退休/恢复，不冒充实际内存消费。|
| `VSQ-REDIRECT.deep_suffix` | 正常 dispatch 十个连续 Store 后，以公开 redirect 保留前两个、一次取消至少八个年轻 UID；恢复尾必须是保留前缀的 exclusive SQ end，所有取消 UID 都不能退休。恢复窗口结束后用新 UID 复用同一虚拟区间并正常退休；该情形专门覆盖合法 `cancelCount` 高位，不用内部计数器写入。|
| `VSQ-RETIRE.batch_width` | 八个连续 uop 各有4个 physical flow，ROB正常越过后一次退休批次的 physical reqNum 总和达到32；公开退休尾精确前进32，所有8个原UID正常完成。该情形覆盖退休请求计数的合法高位，而不是改变寄存器或伪造ROB反馈。|
| `SQ-RECOVER.prefix_windows` | 已执行 Store 先受 Sbuffer 背压，ROB 退休前缀与真实恢复流水交错。只取消 cutoff 之后的三个年轻 UID；既有前缀和两条幸存 Store 的字节不能丢，三个同 SQ 位置的新 UID 最后正常消费和出队。|
| Wrapper 复合情形 | 与 Store 同时派发一个幸存 Load 和一个被取消 Load。幸存原 Load 从其原 Store 取字节，用相同 uop 完成 S3；旧 Store 在恢复后仍须实际消费。新 Load 复用被取消的 LQ 槽并读取新 Store 后完成。真实两分支恢复尾、Store 字节、Sbuffer fire 和出队都检查，沿用 `LSQ-RECOVER.partial/retired_store/reuse`，不扩写既有功能分母。|

- 每个测试依次运行四窗：起始物理 SQ 绝对位置 **0、62、126、190**；
  退休前缀长度 **1、8、9、59**。每窗另外两条幸存 Store、三个取消 Store，
  最大 64 个在途 Store（Wrapper 加两条 Load），不超实际容量/ROB 半环。
- 窗间由普通 Store 真实完成推进位置。最终每个父级用例正常完成 **254 个
  Store**，另取消 12 个旧 Store；无窗间 reset，无取消替代正常资源回收。
- 三个参数分别在设置公开 ROB head 后 **0、1、2** 个额外空拍发 redirect，
  覆盖退休流水不同相位；不保证每个参数都进入 release，direct-walk 是必要
  负对照。以 raw branch 计数报告实际走过的路径，不把相位名当覆盖证据。
- 深后缀用一条独立叶子轨迹：连续10个 `flows=1` Store，redirect 保留 ROB10/11
  的前缀并取消 ROB12..19 共8个真实 uop UID；公开恢复尾为SQ2，随后派发
  **1个新uop UID、3个physical flow**并正常退休。复用第一个取消虚拟槽和
  三个物理flow位置，不声称八个虚拟槽全被重新派发。新测试不覆盖父级内存消费，父级恢复仍由上方真实 actor合同
  检查；叶子只负责VSQ计数宽度和公开尾身份。
- 退休批宽用一条独立叶子轨迹：八个连续 `flows=4` Store（总32 physical flow），
  设置公开 `rob_head=18` 后等待真实退休/空队列，检查公开 retiredPtr 为32，
  8个UID均在独立模型完成集合中；再派发1个单flow uop，真实退休使公开尾到33，
  计数高位逆向回落由正常业务产生而非reset。不读 `retireReqNumReg` 内部值。
- ROB head 先单调推进到第一条未退休幸存 Store；redirect 后可再单调推进到
  cutoff（第二条幸存 Store），不回退 ROB head，不越过未完成的幸存 Load。
  被取消 Store 从未消费，不人为发假的 physical deq 来制造内部状态。
- Wrapper 的幸存 Load 在第一条未退休 Store 之后、cutoff Store 之前；它在
  redirect 前实际查询、执行原 S3 并完成后，才允许 ROB head 推进至 cutoff。
  被取消 Load 未执行；新 UID 用原 LQ 槽、实际新 Store 字节查询和原 S3 完成。
  不重复发送已完成原 Load 的 S3，不把未派发查询冒充真实 Load。

## 两个未命中 branch 必须分开处理

`VirtualStoreQueue.sv:15853 else` 的控制谓词为
`state != 0 && state != 1 && state != 2`。必须逐份固定源核实：state 为2位、
复位写0、所有时钟赋值只写0/1/2；枚举布尔条件做归纳闭包后，才可给出
**post-reset 编码3不可达**的精确边界。初始化随机态、故障注入、未复位仿真
不在这个证明域，不能说所有配置/上电状态都不可达。源点和分母仍保留。

`:15850 else` 表示 release 中继续看到 retired head。没有命中不等于不可达；
本轮先用合法长前缀/退休相位轨迹检查。若仍未命中，继续保留为可达性尚未
证明的条件缺口，不能套用编码3的归纳证明、参考模型搜索或叶子通过来豁免。

## 运行与审计

各层先 fresh baseline/after，保持同 build、源 aggregate、三类点全集、旧节点
及检查流；保存 compact 的公开恢复尾/stall/UID/消费 witness，不生成逐拍 JSON、
波形或完整源副本。正常消费者和参考模型保持，不改共享 actor/checker。

之后以完整贡献范围重跑：上一五-build 的1119节点，加 VSQ 原42节点、一个
上一范围漏掉但本轮前已存在的 release 贡献节点，以及本轮9个新节点；实际
节点数必须由 collect/manifest 复核（本轮实际为1171）。必须先用真实 collect/manifest 复核参数和贡献者数；
不能按目录名遗漏 Wrapper 主目录外41个既有贡献者。保持原171个范围内失败
（169个既有五-build失败＋2个VSQ失败）及统一regression15全部227FAIL。
完整与定向增益分开，不以旧dat OR代替一次执行，不回填统一分母。
