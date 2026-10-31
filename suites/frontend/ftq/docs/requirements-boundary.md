# FTQ 责任边界与合法输入域

## 范围与身份

- 基线：`public-893e1580b`（`893e1580b705d81f113c30c7a05734e09a08050e`），DefaultConfig，单核。
- DUT：`ResolveQueue`、`CommitQueue`、`Ftq`（`Ftq` 真实实例化前两者）。
- 不在本工程内：`EntryQueue`、`CfiQueue`、`MetaQueue`、`SpeculationQueue` 当前未被 `Ftq`
  实例化，不纳入 DUT 闭包。
- 单位/地址：50 位虚拟地址；32B cache line；64B fetch block；FTQ 64 项；ResolveQueue 16 项、
  保留 4；CommitQueue 64 项、保留 8；PrefetchDepth 32；BpTrainStallLimit 8；
  `ResolveEntryBranchNumber=8`；DefaultConfig 的 `NumBtbResultEntries=10`。

## 责任矩阵

| 行为 ID / 语义 | 来源版本/条款 | 本层责任与输入前提 | 观察点/禁止副作用 | 上层承接 | 状态与证据 |
|---|---|---|---|---|---|
| RQ-001 身份与准入 | `ResolveQueue.scala`；CircularQueuePtr 语义 | 相同 `{flag,value}` 合并，不同 flag 分离；输入是后端/IFU 针对某 FTQ entry 的解析 | `bpuTrain` 队首、`startPc`、分支槽 | BPU 训练消费 | 已执行，`FTQ-RQ-001` |
| RQ-002 最多 8 条分支归并 | `ResolveEntryBranchNumber=8` | 同拍/多拍来源按 b0→b1→b2→IFU 顺序占空槽；超出容量应丢弃 | 8 个 `branches` 槽的 valid/position/target | BPU 训练 | 已执行；超容量见 RQ-011 |
| RQ-003 后续解析附着 | `hit/hitPrevious` 合同 | 已驻留 entry 的后续解析追加分支，不重复占槽 | 队首索引不变、分支增加 | BPU 训练 | 已执行 |
| RQ-004 IFU 独立来源 | `ifuFilteredResolve` | IFU 解析不受后端 direct/return 过滤 | `bpuTrain` 分支和 `debug_source` | BPU 训练 | 已执行 |
| RQ-005 后端过滤 | `backendFilteredResolve` | 正确 direct 和 return 不训练；误预测条件/非返回间接训练 | 是否产生训练事务 | BPU 训练 | 已执行 |
| RQ-006 单条背压出队 | `DecoupledIO` 合同 | `ready=0` 保持；`ready=1` 恰好消费一条；空队列不被 ready 伪造 | `bpuTrain.valid/bits` | BPU 训练 | 已执行 |
| RQ-007 重定向冲刷 | `backendRedirect` 合同 | 只冲刷比新指针更年轻的 entry | 训练序列中不再出现被冲刷条目 | BPU 训练 | 已执行 |
| RQ-008 BPU 新入队冲突 | `bpuEnqueue` 合同 | 同 `value` 的旧推测失效，可重新建立 | 训练序列与重新入队 | BPU 训练 | 已执行 |
| RQ-009 保留区 | `ResolveQueueSize-4` | 12 条后可排空，新条目丢弃且不污染已接纳序列 | 队列训练序列 | BPU 训练 | 已执行 |
| RQ-010 复位 | 同步复位合同 | 丢弃所有未完成所有权 | `bpuTrain.valid=0`，之后可重新接纳 | BPU 训练 | 已执行 |
| RQ-011 超容量丢弃 | 本表 RQ-002 + 10 位置 BPU meta | 第 9 条/同拍超量不得改写已记录分支 | 8 个槽的既有 payload | BPU 训练 | **真实 RTL 缺陷，strict XFAIL**，见 `bugs/resolve-queue-branch-overflow.md` |
| CQ-001 只接纳 RAS 动作 | `BranchAttribute.RasAction` | `None` 不占槽，Pop/Push/PopAndPush 进入 | `bpuTrain.valid` | BPU commit 训练 | 已执行 |
| CQ-002 多 lane 保序 | CommitWidth=8 | 同拍有效 lane 按程序顺序入队，队首 FIFO 输出 | `bpuTrain.bits` | BPU commit 训练 | 已执行 |
| CQ-003 同拍入/出队 | FIFO 合同 | 新条目排队尾，队首不被旁路/覆盖 | 队首序列 | BPU commit 训练 | 已执行 |
| CQ-004 保留区 | `CommitQueueSize-8` | 到门限后整组拒绝，排空后恢复 | 无覆盖、FIFO 不丢 | BPU commit 训练 | 已执行 |
| CQ-005 复位 | 同步复位合同 | 清空所有排队动作 | `bpuTrain.valid=0` | BPU commit 训练 | 已执行 |
| TOP-001 复位空闲 | `Ftq.scala` | 五个所有权指针归零，所有输出空闲 | `bpu/pf/fetch/commit/pnr`，输出 valid | ICache/IFU/BPU/后端 | 已执行 |
| TOP-002 预测准入 | BPU prediction 合同 | `ready` 时接纳一个 entry，写回后端 PC | `toBackend.wen/startPc`，entryQueue | ICache/后端 | 已执行 |
| TOP-003 三类背压 | FTQ 满、PrefetchDepth、训练 stall | 三个条件独立关闭 `prediction.ready`，释放后恢复 | `prediction.ready`，topdown reasons | BPU | 已执行 |
| TOP-004 预取请求 | ICache prefetch 合同 | 描述 `pfPtr` entry，fire 推进 1/2 | `toPrefetch`，`pfPtr` | ICache | 已执行 |
| TOP-005 2-prefetch | PNR/同页/异常门限 | 五种 `TwoPrefetchCase`；只有非 Conflict 推进 2 | `twoPrefetchCase.value`，`pfPtr` | ICache | 已执行（5 种 case） |
| TOP-006 2-fetch | PNR/大小/同页/realTwoFetch | 第二个请求只在这些条件下有效；`realTwoFetchValid` 决定推进 1/2 | `toMainPipe.req_1`，`fetchPtr` | ICache | 已执行 |
| TOP-007 s2 override | BPU s2 合同 | 重写 s2 entry，回卷 pf/fetch | flush、entry、指针 | BPU/IFU/ICache | 已执行 |
| TOP-008 s3 override | BPU s3 合同 | 优先于 s2，推进 PNR，回卷已前进的 pf/fetch | flush、entry、`pnrPtr` | BPU/IFU/ICache | 已执行 |
| TOP-009 PNR 边界 | `passedPnr` 合同 | 未过 PNR 的第二块绝不合并 | 2-prefetch/2-fetch | ICache | 已执行 |
| TOP-010 后端重定向 | CtrlToFtqIO 合同 | 优先于 IFU，回卷所有所有权，转发 meta；ahead 命中取消延迟 | 指针、`toBpu.redirect`、flush | BPU/IFU/ICache/后端 | 已执行 |
| TOP-011 IFU 重定向 | IfuToFtqIO 合同 | 下一拍生效；返回目标取 meta top；canTrain 门限 | `toBpu.redirect`、训练 | BPU | 已执行 |
| TOP-012 异常/satp 标记 | ExceptionType 合同 | IPF/GPF/AF 映射；只污染窗口内首个 fetch block；三个 block 后清除 | prefetch/fetch 标记 | ICache/IFU | 已执行 |
| TOP-013 退休指针 | commit 合同 | 同一指针只推进一次；可追赶到重复指针；一 lap 后停止 | `commitPtr` | 后端 | 已执行 |
| TOP-014 call/return 提交 | CommitQueue + commitMeta | 保序送 BPU，meta 对应索引 | `toBpu.commit` | BPU | 已执行 |
| TOP-015 解析训练 | ResolveQueue + first-mispredict mask | 训练事务带 meta/首误预测掩码；队首更新时延迟出队 | `toBpu.train` | BPU | 已执行 |
| TOP-016 训练缓存 | trainCache 合同 | 保持到 ready；更老重定向冲刷；同索引重定向保留 | `toBpu.train.valid` | BPU | 已执行 |
| TOP-017 meta 队列 | MetaQueue 读写合同 | 64 个物理索引可写读；全 bit 双向 toggle | `metaQueue*` | BPU/后端 | 已执行 |
| TOP-018 topdown | TopDownCounters | FTQ 满/更新气泡暴露给 IFU | `toIfu.topdownInfo` | IFU/性能分析 | 已执行 |

## 合法输入域与生产者约束

- BPU prediction：只在 `prediction.ready=1` 时由生产者提交；`startPc` 50 位、`endPosition` 0..31、
  override 指针与 `s2FtqPtr/s3FtqPtr` 同源。测试中的 `allocate()` 按该握手逐条接纳，并在
  需要 32 条以上时打开 ICache 消费者以保持 PrefetchDepth。
- BPU meta：只对已接纳 entry 写；`pnr ≤ bpu` 由外部不变量监视器每拍检查。测试不再对未预测的
  索引单独写 meta。
- 后端 resolve：`branchType` 0..3、`rasAction` 0..3、offset 0..31；正确 direct/return 被消费
  方过滤。FTQ 顶层测试先用 `allocate()` 建立 entry，再送对应索引的 resolve。
- 重定向：`level` 0/1，`offset` 0..31，`ftqIdx` 0..63；异常最多一个（IPF/GPF/AF 互斥）。
- commit：退休指针单调；测试覆盖重复指针追赶和跨 lap。
- 越域压力不冒充功能反例：构建器在写入原生 pin 前拒绝非法编码；对未定义 payload（无效分支槽）
  不比较数据，只比较 valid 和有效槽字段。

## 观察点与边界缺口

- 主要观察点是公开端口（`toBpu`、`toICache`、`toIfu`、`toBackend`、`metaQueue*`）。
- 指针身份/所有权使用内部 `*_ptrs_*`；这是设计声明的所有权，不是从 RTL 行为倒推答案。
- 生成 RTL 中 `XSError` 的 `$fatal` 已被优化掉（三个闭包均为 0 个 `$fatal`）。因此增加
  被动不变量监视器，按 RTL 相同的 CircularQueuePtr `>`、`isFull` 语义每拍检查
  `fetch/pf ≤ bpu`、`pnr ≤ bpu`、`commit` 落后不超过一 lap。
- 未保留的断言还包括 EnumUInt 合法性、ExceptionType one-hot 等；本工程只对合法域输入负责，
  越域输入由构建器拒绝或显式标为压力。
- 第二块的 `backendFlagPtr` 检查在当前 `pnr ≤ bpu` 合同下未构造出可达序列：重定向把
  `fetchPtr` 设为 flag 指针本身，若再回卷到 flag-1 则 `bpu=flag`，而 `pnr>flag` 会违反不变量。
  该分支保留为“疑似冗余/不可达”，未用非法激励强行覆盖。
- 上层消费（ICache 对 prefetch/fetch 的实际使用、BPU 对 train/commit 的更新、后端退休序列）
  不在本层验证范围；见 `residuals.md`。
