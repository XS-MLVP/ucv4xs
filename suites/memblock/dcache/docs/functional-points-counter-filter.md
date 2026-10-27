# CounterFilter 功能点

DUT：`CounterFilter`（`soc-split/rtl/CounterFilter.sv`，源码
`xiangshan/mem/prefetch/FDP.scala`），层次：DCache 预取反馈叶块。它是一个 15 项的
环形 FIFO，记录最近 3 条 load 流水在 s3 看到的 set/way；对每个 load 查询端口做
“这条 cache line 是否刚被访问过”的过滤，避免同一条 line 的重复预取命中计数。

参数（由 RTL 固定）：`SIZE = (4+1) × 3 = 15`，3 个 enqueue 端口，3 个 query 端口，
3 个 dequeue/cycle 上限。

## CF-FP-001 复位后为空

复位清空 15 个 entry 的 valid 与 payload，清空 enq/deq 指针和 `last3CycleAlloc`；
所有 query（无论 idx/way）在复位后都返回 0，直到有 load 入队。

**复位校准（`CF-DEQUEUE-PIPELINE-NO-RESET`）**：3 级出队计数流水
`last3CycleAlloc_REG{,_1,_2}` 不在复位域内，短复位后仍保留旧值；第一个复位后时钟沿
会按该旧值出队，把 `deqPtr` 推过 `enqPtr`，FIFO 从此永久偏移。本 UT 的 `reset()`
保持复位 5 拍（期间输入全 0）以冲干净该流水后再放流量。真实系统复位持续数百拍，
且 DCache 还要等 256 拍 SRAM 清扫，因此不影响实际功能。

## CF-FP-002 入队保存 set/way

`io_ld_in_i_valid=1` 时，端口 i 的 `idx/way` 在同拍按端口顺序写入 FIFO；多端口同拍
入队按 0→1→2 顺序占用连续槽位；无效端口不占槽位。

## CF-FP-003 查询命中语义

对任一 query 端口：`resp = req_valid && (∃ valid entry: entry.idx == req.idx &&
entry.way == req.way)`。3 个查询端口并行、相互独立；无效查询恒为 0。

## CF-FP-004 条目生命周期

条目在入队边沿后对查询可见，并保持 **4 个时钟沿**（含入队后的当前拍），第 4 个沿
之后被 dequeue 清除。dequeue 数量是 4 拍前的入队数量（4 级延迟匹配 load 流水
s0→s3 + 预取写回下一拍）。

- 情形：age 0/1/2/3 命中；age 4 之后同 line 查询变 miss。

## CF-FP-005 重复 line 与容量

同一拍多个端口可以写入相同 (idx, way)，形成多个 entry；查询只关心是否存在匹配。
FIFO 有 15 个物理槽（(4+1) × 3），但 dequeue 数要经过 3 级寄存器延迟后在入队后第 4 个
时钟沿才生效，因此**合法在途占用上限是 4 个可见周期 × 3 端口 = 12 项**；剩下 3 个槽
是流水写回阶段的余量。连续满带宽时入队与出队保持平衡，不会覆盖未出队的 entry。
指针在 15 处回绕，flag 位参与满/空判定。

- 情形：重复 line、3 端口不同 line、连续 5 拍满带宽（12 项在途）、指针回绕。

## CF-FP-006 查询与入队同拍

查询使用当前已提交的 entry 集合；同拍入队的 entry 在下一个时钟沿之后才可见。
同拍 dequeue 与 enqueue 命中同一槽位时，以新入队为准。

## 覆盖组

- `cf.query`：命中/未命中/无效查询、3 个查询端口、4 个 way、idx 区间、占用度。
- `cf.enq`：0..3 个端口、同 line 重复/不同 line、满带宽、指针回绕。
- `cf.lifetime`：age 0..3 命中与过期 miss。
- cross：查询端口 × 结果、结果 × way、占用度 × 端口数。
