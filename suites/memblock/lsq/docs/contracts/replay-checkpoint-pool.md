# Replay checkpoint：全池生命周期与真实父级复用补例

状态：**先定义功能点与检查义务，再实现和运行；不是整体 LSQ 验收。**

## 1. 缺口来源和范围

基准为 `lsq-progress-regression-15`，保持各 native build 原有分母与原样 RTL。
`load_queue_replay` 的未命中点包含各 `uop_N_perfDebugInfo_runahead_checkpoint_id`
高位的两个方向；父级 `load_queue` 的真实 `LoadQueueReplay` 子实例也保留这些缺口。
这些属于既有 `LRQ-PAYLOAD`、`LRQ-RECYCLE`、`LQ-REPLAY.metadata`、
`LQ-CAPACITY.replay_pool` 功能中缺少的全池 payload 生命周期情况。

此前 `test_full_width_replay_metadata_and_pointer_identity_reuses_slot` 只分配一项、
完成反馈后再分配一项，没有检查两次公开槽号相同。空闲 FIFO 中还有其他槽，
因此这只能证明两条请求的边界 payload，**不能独立证明同一槽位复用**。
历史目录与计数保留；本次不追溯修改其结果，只纠正该项能力描述并补充真实证明。

## 2. 用例前定义的语义功能点

| 情况 ID | 人类可读行为 | 必需检查 |
|---|---|---|
| LRQ-PAYLOAD.pool_checkpoint | 占满 120 项的每个 load 在实际重放时保持 64 位恢复 checkpoint，输出握手不是释放 | 第一生命周期 checkpoint 全 1；每个公开 `replayQueueIdx` 都实际 ready/valid 握手一次；UID/LQ/ROB/payload 由独立参考逐拍比较；握手后、反馈前仍满且 `replayAllocate` 有效 |
| LRQ-RECYCLE.public_slots | 反馈释放整池后，每个真实槽位保存新身份和相反 checkpoint，而不是只分配到新的空槽 | 第一生命周期反馈全部完成、容量回收稳定；第二生命周期 checkpoint 为 0；公开槽号两轮均恰好是 0..119；两个生命周期没有未完成义务或重复握手 |
| LQ-REPLAY.checkpoint_pool | 上述新旧身份在真实 LoadQueue 的 dispatch、共享 S3、真实 Replay/FreeList/Age 和 VLQ 释放链路中保持 | 不替换下级；外部 LoadActor 分配 120 个 UID，真实 replay 输出及原 UID 反馈、VLQ 有序释放；两轮公开反馈槽号完整，新旧 checkpoint 与完整 payload 检查均通过 |
| LSQ-REPLAY.capacity 的 checkpoint 全池情形 | 上述新旧身份穿过完整 LsqWrapper 的真实 LoadQueue 子树，两轮完整恢复字段不串单 | 外部 MemoryOwners 从公开 dispatch/S3 发出 240 个全局 ROB 有序 UID；两轮公开 grant 槽号均为 0..119，正常反馈并获得真实 LQ 释放；Store 分支仍真实连接但本例为空，不能据此声称混合 Store 义务通过 |

## 3. 合法输入、负义务与边界

- 使用单 hot `BANK_CONFLICT` 原因、普通 load `fuOpType=6`，不使用保留 cause12，
  不以修改 strict 属性或异常语义绕过真实失败。
- 入口最多三路、池容量 120、ROB160/LQ120 的合法编码；只有实际 replay 握手后的
  live owner 才能反馈，反馈槽号来自公开输出而不是 DUT 内部状态。
- 必须真实反馈全部请求并等待回收，再进行下一生命周期；不用 reset 冒充正常释放。
- 模型继续逐个 DriveStable/RisingEdge 检查，不因更高覆盖率屏蔽旧 FAIL。
- compact witness 只保存每生命周期计数、公开槽号集合及 payload 摘要，不保存逐拍 JSON/波形。

## 4. 覆盖率实验和验收门禁

每个 DUT 单独运行 fresh baseline 与 baseline+补例，保存命令、pytest、native
`coverage.dat`、三类点集哈希与 compact witness。要求同 build、三类点集分母
完全相同、旧命中不丢失、功能检查通过。叶子的分母与命中不并入父级或 regression15。
明确区别 Verilator 原始 line **点**与 LCOV 展开的原始源码 **行**，两者不互相冒充。
余下常量/非法指针/初始化分支必须另据静态或配置证据分类，本补例不声称关闭这些点。
