# VirtualLoadQueue：连续流区间、完成前缀与重定向恢复合同

本合同先于用例实现定义，来源为开源 `VirtualLoadQueue.scala`、`RobBundles.scala` 和当前同名原始 RTL。现已通过原生DUT实测核对并完成首轮缺口/补例闭环，见 [实际结果与边界](../reports/vlq-20261018.md)；不把源码推导本身当作通过证据。

## 1. 实际 DUT 和观察边界

- top `VirtualLoadQueue`，120 个槽位（非 2 的幂），8 路 dispatch、3 路 load writeback；每拍最多释放连续 8 项。
- dispatch 每路保留 valid、ROB 的 flag/value/isFormer、LQ 的 flag/value 和 5 位 numLsElem。
- writeback 每路只保留 valid、LQ value、updateAddrValid、need_rep。ROB 标识、LQ flag、异常、mmio、地址、向量标识等字段已从这个 top 优化删除。
- 输出只有 ldWbPtr、lqEmpty、lqDeq(valid/count)、lqRedirect(valid/LQ pointer)、lqRecoverStall。
- **没有** canAccept、sqCanAccept、needAlloc、分配 resp、lqFull 或 ldin.ready；源码中的这些接口不能绑定或计作已测。容量合法性由独立 dispatch 账本约束；本 DUT 不提供可测试的 full/背压承诺。StoreQueue 可接收约束只能留给实际保留该连接的父级/分配控制器验证。
- 源配置 CommitWidth=8、RobSize=160；生成的 `RobEnqPtrWrapper.sv` 环绕减数 `0xA0` 独立佐证 ROB 深度。ROB value 是 8 位而不是 256 项 ROB，LQ value 是 7 位而不是 128 项 LQ。

## 2. 语义模型和合法输入

参考用绝对递增的 LQ 序号标记生命周期，映射成 `(flag=(serial//120)%2, value=serial%120)`。每个 dispatch 请求描述 `[start, start+numLsElem)` 连续区间；所有 valid lane 的区间按 lane 顺序紧凑相接，稀疏 lane 不留下洞。0 流在本块边界表示空区间，最大单请求16流（当前128-bit向量、最小8-bit元素；不据5位宽度假设31流合法）。

维护语义条目 `{absolute_token, ROB_slot, completed}`、已准备释放批次与按时刻排队的恢复响应，不复制 allocated/committed 位向量或 RTL 指针表达式。实际 monitor 是模型唯一输入；不读取 DUT 内部寄存器，不用 driver 日志产生答案。

- 活跃区间和已预留的 dispatch 容量不能超过120，不允许覆盖仍占用的生命周期。不能将 value 用二进制截断模拟回绕。
- enabled writeback 只能指向仍由该生命周期拥有且尚未完成的槽位；同拍三个 WB 地址不同。need_rep 或 updateAddrValid=false 可多次报告而不完成；最终合法完成只能发生一次。
- top 删除了 WB 的 ROB/LQ-flag 身份字段，不能要求它拒绝 stale/wrong-epoch WB。此类输入不作为合法随机，也不把外部约束当作已验证的硬件保护。
- 同拍 redirect 和旧条目的有效 writeback 可以发生；取消项不能因此重新成为可释放项。后续重用需重新建立未完成状态。
- dispatch 的 ROB 年龄按顺序递增或共享同 ROB entry 的 former/latter 两个 slot；在途年龄跨度保持单环半区内，避免 flag 环形关系歧义。参考使用解环后的事务顺序比较，不用普通8位整数大小判年龄。
- redirect level=0 为 flushAfter；level=1 连同同一 ROB slot 取消。`isFormer=true` 早于同一 entry 的 latter；同 flag/value 但不同 isFormer 不能当作同一 slot。
- reset 期输入 idle，保持至少6拍并留出空拍清空非复位观察流水；旧所有权、准备释放和恢复批次全部终止。

## 3. 完成、释放和可见时序

`committed` 在这里是 **load 已完成且无需 replay**，不是 ROB 架构退休。只有 `WB.valid && !need_rep && updateAddrValid` 才标记完成；源码中异常计算没有额外完成门控，在此 top 也无对应输入。

释放只看旧状态下队头起连续已完成前缀，最多8项，并排除本拍 redirect 取消的项；年轻项先完成不能越过未完成的老项。同拍刚收到的完成 WB 不能零延迟成为旧状态释放前缀。

源码推导的两阶段释放合同（以输入/决策发生的上升沿为 N）：

| 上升沿 | 行为/外部观察 |
|---|---|
| N | 根据边沿前的旧 completed 状态，选出连续释放批次并清除这些槽位的 allocated 生命周期；ldWbPtr 尚未按该新批次前移 |
| N+1 | 前一批次正式推进 ldWbPtr，lqDeq.valid/count 同步报告同一批次；不得重复释放 |

不能把这个 pipeline 简化成每次 WB 立刻移动指针，也不能假设每拍都能持续释放8项。参考要显式记录准备批次，旧头部已经被准备释放但指针尚未前移时不可重复扫描出同一批。

`lqEmpty` 是**上一拍的指针距离为空**这一事实，不是当前 allocated 字典是否为空。准备释放、取消到恢复之间可存在暂态空洞；不能用 active 条目数替代公开 empty 的精确时序。

## 4. Redirect 和容量恢复

redirect 取消所有更年轻 ROB slot；flushItself 还取消相同 slot。dispatch 与 redirect 同拍时：被取消的新请求不建立条目，但其 numLsElem 已进入预分配尾部推进，需要计入随后回退的取消数。

| 上升沿 | 单个 redirect 输入发生于 N 时的源码推导 |
|---|---|
| N | 取消命中的旧条目，统计旧条目及同拍被取消 dispatch 的流数；lqRecoverStall 拉高 |
| N+1 | 捕获该次恢复取消数；dispatch 必须停止 |
| N+2 | 回退分配尾部，且不得退到新释放头指针之前；lqRedirect.valid 给出同一实际恢复指针 |
| N+3 | 无新 redirect 时 lqRecoverStall 解除，随后可恢复正常 dispatch |

在已观察到 recover-stall 的拍不再发送新 dispatch；redirect 当拍可有已经在途的 dispatch。连续/相邻 redirect 需分别保留恢复事务，不把最后一次输入覆盖前一次证据。允许老项在恢复期间完成/释放，取消数和恢复尾部仍需与新头部一致。

所有 valid=false 的输出 payload（lqDeq_bits、lqRedirect_bits）均为 don't-care，不通过比较无效 payload 消除覆盖缺口。

## 5. 用例前的人类可读功能点

| ID | 行为要求 | 必需情形及检查义务 |
|---|---|---|
| VLQ-RESET | 复位恢复空的0号生命周期，旧完成和恢复不能泄漏 | 初始；非空/有完成/恢复期间 reset；重新填充和实际释放 |
| VLQ-INTERVAL | 按 numLsElem 分配连续流区间，稀疏 lane 仍紧凑且不重复 | 单流、多流、0流空区间、8路/稀疏路；各lane完整区间经实际WB/释放或恢复验证 |
| VLQ-COMPLETE | 只有无需重放且地址更新有效的 WB 才完成条目 | 正常、need_rep、updateAddrValid=false、两者共同抑制；后续合法WB才能解除队头阻塞 |
| VLQ-ORDER | 只能释放最老连续完成前缀，不越过老项缺口 | 乱序WB、未完成队头、部分/满8项、多个批次；实际deq计数和ldWbPtr守恒 |
| VLQ-TIMING | WB、准备释放、指针前移/计数报告具有规定延迟，不重复 | 同拍WB不提前释放；准备批次后旧头不重复扫描；empty的延迟 |
| VLQ-REUSE | 120项非2幂回绕和旧槽位复用不继承完成状态 | 跨119→0、两种flag、多圈；旧槽重新分配后需重新完成 |
| VLQ-REDIRECT | 精确取消年轻/同slot事务，保留应存活的老项 | flushAfter/flushItself；same-entry former/latter；ROB环绕；取消部分/全部/零项 |
| VLQ-RECOVER | 多拍恢复回退正确尾部，stall与恢复响应同一事务对齐 | 取消旧项及同拍dispatch；老项继续释放；尾部不落后头；相邻/连续redirect |
| VLQ-RACE | 完成、释放、取消和新分配重叠时不复活/重复使用 | WB与redirect；dispatch与redirect；释放与恢复；恢复后旧槽重用 |
| VLQ-IDLE | 没有输入时所有权/指针稳定，仅未完成的流水允许推进 | 空池、占用池、准备释放/恢复中的空拍；禁用口毒化payload不生效 |
| VLQ-CAPACITY | 在外部合法容量约束内不丢流，满池仍可正确完成/恢复 | 恰满120、仅余1/2、多流跨尾；不虚构已删除的full/canAccept输出检查 |

reached 从真实采样、独立事务账本和语义情形识别；checked 在相应真实输出比较成功后产生。区间分配/完成类义务应追踪到实际释放或合法恢复，不能仅发过 valid 就记通过。reset 取消旧证明但不完成它。

## 6. 首轮和后续闭环

先用空池、单/少量流分配与完成、基本阻塞建立原生时序实测，冻结首轮源代码/工具/运行证据。随后逐行审查未覆盖执行行：按区间写入、完成写、连续释放、环绕、ROB slot 比较及恢复流水映射到已有功能点的缺失情形或新功能点，再补例重跑。高行覆盖不抵消上述必需语义缺口。

本合同不承诺任意参数、不验证未保留的WB身份/异常/向量类型、不把 dispatch/StoreQueue 外部容量协议当作本块已检查。父级仍需验证真实 canAccept/needAlloc/resp/sqCanAccept 连接、取消反馈及所有业务子队列。

## 7. 首轮实测与缺口驱动的补例定义

`vlq-initial-01` 已实测3/3通过：单流WB在N接受、N+1准备、N+2报告/移动头，empty再滞后一拍；8路接口中的稀疏1/7端口也完成短区间。原生本体为 **1924/6329=30.40%**，仅 **11/43** 个可执行语义情形checked。首轮原始清单 `line-audit.json` 先保留needs_review；人工对照后另生成映射清单，不覆盖初始审查结果。

4405条剩余行归入已有功能点的情形缺失：

- 4275条ROB标签选择路径：需要全部8个入口覆盖完整120项，且通过flag/former不同的redirect和幸存项实际释放验证存储标签。没有读端口，仅写入/行命中不能证明ROB字段正确。
- 121条取消快照更新及2条取消计数捕获：需要部分/全池取消、同拍dispatch取消和相邻恢复，并比较恢复尾部。
- 3条连续前缀选择：首轮仅1～3项，补4～8项的不同前缀及不重复计数报告。
- 1条非2幂恢复减法分支：补物理0边界前后回退，不用非法越界指针制造命中。
- 3条恢复响应赋值：补实际有效响应、规定stall窗口以及释放与恢复重叠。

补例还必须完成已有但首轮未执行的回放/地址无效抑制、全池容量、WB/取消竞争、多圈重用、reset中断恢复、ROB former/latter和环绕等语义；不能只针对上述行号发激励。分配/正常WB的checked等待对应生命周期的真实释放；抑制完成的情形先验证至少三个观察边沿内头不前移，再要求后续正常WB释放。恢复类checked还等待实际响应、stall解除和当时幸存项的实际释放；取消或reset不完成旧证明。
