# `DelayPipeline`：S3→SX 的 1 拍写回延迟与 flush 过滤

## 1. 模块职责

`NewStoreUnit` 的 S3 在发出写回（`stout`）前需要与 RAW 违例检查对齐，因此把写回
载荷再延迟 `RAWTotalDelayCycles` 拍（`NewStoreUnit.scala:769-783`）。固定配置下
`LoadQueueRAWSize=56`、`RollbackGroupSize=8`，得到 **`RAWTotalDelayCycles = 1`**，
生成 RTL 中因此只有一级寄存器（`valids_1_r` / `datas_1_r_*`）。

模块的**可见功能只有一处**：入口过滤 —— 本拍要进入的 beat 如果已被本拍
redirect 命中，就不进寄存器。

源码里还有一处针对寄存器 beat 的 `curKill`，它是为延迟级数 >1 或 `out.ready=0`
准备的。固定实例中 `out.ready` 被父块接成 `true.B`（`NewStoreUnit.scala:782`），
在生成 RTL 中已被常量传播**完全删除（DUT 没有 ready 端口）**，因此一个 beat
只在它出现的那一拍被消费、不会驻留，`curKill` 在本边界上**不可观测**。

这一点是用差分实验确认的：对同一输入序列，把同一拍 redirect 指向寄存器里的
beat 与不指向它，输出逐字段完全相同（见第 5 节与测试
`test_registered_beat_kill_is_not_observable`）。合同因此不声称"出口压制"存在，
只把它记为**结构性不可观测**，并在覆盖中单列。

## 2. 语义

记 `kill(x) = x.robIdx.needFlush(redirect)`，其中

```
isSameEntry(a, b) = a.flag == b.flag && a.value == b.value
isSameSlot(a, b)  = isSameEntry(a, b) && a.isFormer == b.isFormer
isAfterSlot(a, b) = (a.flag ^ b.flag ^ (a.value > b.value))
                    || (isSameEntry(a, b) && !a.isFormer && b.isFormer)
needFlush(x)      = redirect.valid && ((redirect.level && isSameSlot(x, redirect.robIdx))
                                       || isAfterSlot(x, redirect.robIdx))
```

- `level=1`（`RedirectLevel.flush`）表示"flush 该 slot 及其之后"；
- `level=0`（`flushAfter`）表示"flush 严格在该 slot 之后"；
- `flag ^ ... ^ (value > ...)` 是环形指针比较：flag 不同意味着已经绕回，比较方向取反；
- 同一 ROB entry 内 `isFormer=1` 表示前半 uop，`0` 表示后半 uop；redirect 指向
  前半时后半也要被 flush。

逐拍行为：

| 条件 | 结果 |
|---|---|
| `in.valid=1` 且 `!kill(in)` | 下一拍 `out.valid=1`，`out.bits` 等于本拍 `in.bits` |
| `in.valid=1` 且 `kill(in)` | 该 beat 被丢弃，下一拍不出现 |
| 否则 | 下一拍 `out.valid=0`（beat 已在上一拍被消费） |

等价的可观察关系（本实例）：

```
out.valid(T) = in.valid(T-1) && !kill(in at T-1)
out.bits(T)  = in.bits(T-1)   // 当且仅当上一条成立时有意义
```

`out.ready` 恒为 `true.B`，所以本 DUT 没有出口反压；`in.ready` 也不在生成 RTL
端口上（`io_in_ready` 不存在），说明入口永远可接收。这两点必须按实际端口描述，
不能凭空造 ready 检查。

## 3. 输入合法域

- `in.valid` 任意；`in.bits` 在 `valid=0` 时为 don't-care，但寄存器只在
  `prevFire` 时更新，因此无效 beat 不会污染输出。
- `redirect.valid` 任意；`redirect.bits` 在 `valid=0` 时为 don't-care。
- `robIdx.value` 合法域为 `[0, 160)`（`RobSize=160`，非 2 的幂）；`flag` 在绕回时翻转。
- 19 个载荷字段全部是寄存器，必须逐字段保真，不能只查 valid。

## 4. 语义功能点

| ID | 语义 | 可观察结果 |
|---|---|---|
| **DLY-RESET** | reset 异步清零 valid，载荷不要求 | `reset` 期间与之后 `out.valid=0` |
| **DLY-DELAY1** | 一个 beat 恰好延迟 1 拍，字段全部保真 | T 拍 `in.valid=1` → T+1 拍 `out.valid=1` 且 19 字段全等；T 拍 `out.valid` 不含该 beat |
| **DLY-SINGLE** | 单个 beat 只出现一次，不重复 | 之后连续多拍 `out.valid=0` |
| **DLY-BACK2BACK** | 连续每拍输入 → 连续每拍输出，无丢失/合并 | 3 拍输入对应 3 拍输出，顺序一致、逐字段可区分 |
| **DLY-IN-KILL** | 入口 beat 被本拍 redirect 命中则不进入 | `in.valid=1` 但 `kill(in)` → 下一拍 `out.valid=0` |
| **DLY-OUT-KILL-BOUNDARY** | 寄存器 beat 的 `curKill` 在本实例不可观测 | 同一输入序列下，指向寄存器 beat 的 redirect 与不指向它，输出逐字段相同 |
| **DLY-LEVEL** | `level=1` 命中同 slot 与更老；`level=0` 只命中更老 | 两种 level 下 same-slot 的 kill 结果不同 |
| **DLY-FORMER** | 同一 ROB entry 的 `isFormer` 次序参与比较 | 输入为后者、redirect 指向前者 → 被 kill；反向不被 kill |
| **DLY-WRAP** | 环形指针绕回后比较方向正确 | 构造 flag 不同、value 大小关系相反的组合，kill 结果与模型一致 |
| **DLY-NO-REDIRECT** | `redirect.valid=0` 时任何 robIdx 都不被 kill | 随机 robIdx 全部正常延迟输出 |

## 5. 检查方式

参考模型独立实现 `isSameEntry/isSameSlot/isAfterSlot/needFlush` 的**关系定义**，
不复用 RTL 的位表达式；用两状态（`reg_valid`、`reg_bits`）逐拍推进，并与 DUT 的
`out.valid`/19 个字段逐拍比较。任何输入都不做"预期必过"的假设。

## 6. 覆盖要求

- `out.valid` 的 0/1 两态与 `in.valid` 的 0/1 两态组合；
- kill 的 2 类来源：入口 same-slot、入口 after-slot；出口路径作为不可观测边界单独
  用差分用例验证"无影响"；
- `level` 的 flush/flushAfter 两种；
- `isFormer` 的 4 种 (输入, redirect) 组合；
- 环形 flag 相同/不同两种；
- 连续 3 拍背靠背；
- 合法随机（随机 valid、随机 robIdx、随机 redirect，含 flag 翻转）。

## 7. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:769-783`（实例化与 killFn）
- `NewStoreUnit.scala:946-984`（`DelayPipeline` 的 n=numDelays+1 结构与 valid 更新）
- `XiangShan/src/main/scala/xiangshan/Parameters.scala:788-791`（`RAWTotalDelayCycles`）
- `XiangShan/src/main/scala/xiangshan/backend/rob/RobBundles.scala:300-358`（`RobPtr.isAfterSlot` / `needFlush`）
- `XiangShan/src/main/scala/xiangshan/package.scala:157-164`（`RedirectLevel.flush/flushAfter`）
- `soc-split/rtl/DelayPipeline.sv`（固定生成 RTL，本 DUT）
