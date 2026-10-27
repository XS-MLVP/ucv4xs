# MissTrack 功能点

DUT：`MissTrack`（`soc-split/rtl/MissTrack.sv`，源码
`xiangshan/cache/dcache/loadpipe/MissTrack.scala`），层次：DCache load/miss 中层。
它是 16 项、8-bit index、5-bit hash、4-way 的推测 miss 历史表。

对外可观察接口只有每 lane 的 `io_spec_*_valid` 与 `io_spec_*_candidate`；
`resident`/`pending`/`mshr_id` 是内部分类信号，用于产生 candidate，未引到 DCache 顶层。
内部语义仍按源码功能点验证，外部只断言 valid/candidate 的可观察结果。

关键地址函数（modeId=1，生成配置）：

- index = `{ XOR(vaddr[47:12] 的 2-bit 对), vaddr[11:6] }`（8 bit）
- hash = XORFold(`vaddr[49:14]`, 5)
- block(paddr) = `paddr[47:6]`

## MT-FP-001 安装生成 resident 记录

`io_install_valid` 且 `way` 为单 bit 时，把 `{vaddr,paddr,way}` 写成 resident 项
（pending=0，age=0）。多 bit way 的安装被忽略。若同拍有同 line 的 alloc/training，
安装优先。

## MT-FP-002 分配生成 pending 记录

`io_alloc_i_valid` 写入 pending 项，携带 `mshr_id`。该记录在 owner 仍有效
（`io_owners[mshr_id]` 的 vaddr index 与 paddr block 匹配）时保留；owner 失效后
在下一个时钟沿退休。

## MT-FP-003 s2 命中训练

`s2.valid & s2.hit & way 为单 bit` 时把该行训练成 resident 项。s2 miss、way 多 bit
不训练；与 clear/invalidate 同拍时不复活被清除/失效的行。

## MT-FP-004 S0→S1 查询语义

S0 在 t 拍发出，S1 在 t+1 拍得到结果（寄存器化的 index/hash 与表快照）：

- 表中有唯一匹配项且 paddr block 相同 → resident/pending 命中，外部 `candidate=0`；
- 唯一匹配项但 paddr block 不同，或表中无该项 → UNKNOWN，外部 `candidate=1`；
- 查询有效但无历史 → `valid=1, candidate=1`；
- 无 S1 load → `valid=0`。

## MT-FP-005 多命中抑制

两项共享同一 `{idx,hash}`（hash 碰撞）时，查询得到 multi，`valid=0`（既不命中也不
放行候选）。只有一项匹配且无碰撞项时才 unique。

## MT-FP-006 失效与清除

`invalidate` 按 `idx` 与 4-bit way 掩码清除 **resident** 项（`inv.way & entry.way`）；
pending 项不受影响。`clear` 在时钟沿清空全表，且同拍 `spec.valid=0`。

## MT-FP-007 事件合并与单端口仲裁

同拍 8 个事件（1 install + 4 alloc + 3 training）先按同 line（idx+block）合并：
同 line 的多个事件只产生一次更新，字段优先级 install > alloc0..3 > training0..2。

不同 line 的事件竞争**单个插入端口**，由 RRArbiter 按轮转授权：一拍只插入一个事件，
其余**直接丢弃**（不会排队到下一拍）。因此不同 line 的事件之间**没有固定优先级**——
轮转指针从上次授权之后开始，alloc 可能先于 install 获得插入机会；验证时按
“本拍只有被授权的那一个事件写入”判定，而不是假定 install 必赢。

## MT-FP-008 表项生命周期与替换

- age 每拍 +1，7 饱和；命中/更新时 age 归零。
- 有空槽时优先最低索引空槽；否则替换 age 最大的项，age 相同取最低索引。
- 表满（16 项）后继续插入会淘汰最老项。

## MT-FP-009 流水气泡的 retained 结果

S0 无效时 S1 使用上一次有效查询的 retained 结果（`retained`/`retainedMulti` 是不带
复位的寄存器）；真实 load 流水只在 S0 有效后的下一拍present S1，因此验证按该时序驱动。
