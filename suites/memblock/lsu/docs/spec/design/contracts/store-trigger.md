# `MemTrigger_3`：store 地址触发器匹配

## 1. 模块职责

`NewStoreUnit` S1 在地址计算完成后调用 store 版 `MemTrigger`（`NewStoreUnit.scala:353-370`），
把 4 个 RISC-V debug trigger 的 `tdata2/action/chain/timing` 与本次 store 的
`vaddr/mask/isCbo/isVectorUnitStride` 比较，输出一个 `TriggerAction` 给 S1 的
`uop.trigger`，后续进入异常/断点路径。

`MemTrigger_3` 是 store 参数化实例（`MemType.STORE`），比 load 版多一个 `isCbo`
输入，少了 `isPrf`。

## 2. 三种地址匹配模式（按优先级）

`BaseTrigger` 先算 `(isCacheLine, cacheLineEq)`，再 `Mux(isCacheLine, cacheLineEq,
Mux(isVectorStride, hitVecVectorStride, triggerHitVec))`。store 版的
`DcacheLineBitsEq()` 返回 `(io.isCbo, ...)`，因此：

| 模式 | 触发条件 | 比较内容 |
|---|---|---|
| **CBO**（`isCbo=1`） | cache line 匹配 | `vaddr[49:6] == tdata2[63:6]`，忽略地址低 6 位 |
| **向量 unit-stride**（`isVectorUnitStride=1`） | 高 46 位相等且 mask 覆盖起始字节 | `vaddr[49:4] == tdata2[63:4]` 且 `(mask & (1 << tdata2[3:0])) != 0` |
| **标量/普通**（默认） | 按 `matchType` 比较 50 位地址 | `matchType=0`→相等；`=2`→`vaddr >= tdata2[49:0]`；`=3`→`vaddr < tdata2[49:0]`；其他（含 1=NAPOT）→ 不匹配 |

所有模式共同的前置条件（每一路 trigger 独立）：

```
!select && !debugMode && tEnableVec[i] && tdataVec[i].store
```

## 3. chain / timing 语义

`TriggerCheckCanFire` 逐路递推：

```
canFire[0] = hit[0] & !chain[0]
canFire[i] = (chain[i-1] & hit[i-1] | !chain[i-1])
             & (chain[i-1] & !chain[i] & timing[i-1] == timing[i] | !chain[i-1])
             & hit[i] & !chain[i]
```

含义：只有当前一路命中且它不是链的起点；若前一路开启了 chain，则前一路必须命中且
timing 相同，否则整条链不成立。

## 4. 输出语义

```
anyDebugMode      = any(canFire[i] && action[i] == 1)
anyBreakpointExp  = any(canFire[i] && action[i] == 0)
triggerAction     = anyDebugMode                              ? 4'h1
                  : (anyBreakpointExp && triggerCanRaiseBpExp) ? 4'h0
                  : 4'hF   // None
```

`action` 其他编码（2=TraceOn、3=TraceOff、4=TraceNotify）不产生任何 action，
输出仍为 `4'hF`。DebugMode 优先于 BreakpointExp，且 DebugMode **不受**
`triggerCanRaiseBpExp` 约束；BreakpointExp 必须被它放行。

## 5. 输入合法域

- `tdataVec[i].store` 必须为 1 才能命中（store 版只看 store 位，不看 load 位）。
- `tdataVec[i].select` 为 1 表示该 trigger 当前被 CSR 选中用于调试，不参与匹配。
- `debugMode=1` 时任何 trigger 都不命中。
- `tEnableVec[i]` 是 CSR 使能。
- `matchType` 的 RISC-V 合法值是 0/1/2/3（另有 MASK_LO 等扩展）；本 DUT 只实现
  EQ/GE/LT，NAPOT(1) 与 MASK_* 一律不匹配。这个"部分实现"是固定源码的实际行为
  （`Trigger.scala:171-188` 的 `isLegal` 只接受 EQ/GE/LT）。
- 纯组合模块：无时钟、无 reset。

## 6. 语义功能点

| ID | 语义 | 可观察结果 |
|---|---|---|
| **MT-STORE-ONLY** | 只有 `store=1` 的 trigger 能命中 store | `store=0` 且地址完全相等 → `4'hF` |
| **MT-EQ / MT-GE / MT-LT** | 标量三种 matchType 的 50 位比较 | 每条边界（相等、相邻值）方向正确 |
| **MT-MATCHTYPE-UNSUPPORTED** | NAPOT(1) 与 4..15 不匹配 | 地址完全相等也输出 `4'hF` |
| **MT-PRECOND** | `select`/`debugMode`/`tEnable` 三者任一为真时该路不命中 | 逐项翻转为 1 后匹配消失 |
| **MT-CBO-LINE** | `isCbo=1` 时按 cache line（忽略 [5:0]）比较 | line 内任意偏移都命中；line 外不命中 |
| **MT-CBO-PRIORITY** | `isCbo=1` 时不再使用 matchType 与 mask | 构造 CBO line 命中但 matchType 不匹配的数据仍命中 |
| **MT-VEC-MASK** | `isVectorUnitStride=1` 时按高 46 位 + mask 位比较 | 起始字节被 mask 覆盖才命中；未覆盖不命中 |
| **MT-CHAIN** | chain 起点的 trigger 自身不能 fire；chain 后继需要前一路命中且 timing 相同 | 4 组 `(chain[i-1], hit[i-1], timing)` 组合 |
| **MT-TIMING** | chain 有效但 timing 不同 → 后继不 fire | 同地址下切 timing 改变结果 |
| **MT-ACTION-DEBUG** | `action=1` 且 fire → `4'h1` | 与 `triggerCanRaiseBpExp=0` 无关 |
| **MT-ACTION-BP** | `action=0` 且 fire 且 `triggerCanRaiseBpExp=1` → `4'h0`；为 0 时 → `4'hF` | 两方向都检查 |
| **MT-ACTION-PRIORITY** | 同拍 DebugMode 与 BreakpointExp 都成立 → `4'h1` | 高编号 Breakpoint + 低编号 Debug 组合 |
| **MT-ACTION-OTHER** | `action` 为 2/3/4 或 15 时不产生 action | 命中但输出 `4'hF` |
| **MT-MULTI-TRIGGER** | 4 路独立：任意一路单独命中即可产生 action | 逐路单独测试，且互不干扰 |

## 7. 覆盖要求

- 4 路 × 3 种模式 × 3 种 matchType；
- 4 路 × 4 种 action 编码 × 2 种 `triggerCanRaiseBpExp`；
- 4 路 × `(select, debugMode, tEnable, store)` 的门控翻转；
- chain 的 16 种 `(chain0..3)` 组合中语义可达的部分 + timing 相同/不同；
- CBO line 内 64 个偏移抽样与 line 外相邻；
- 向量 mask 的 16 个起始字节 × 覆盖/不覆盖；
- 合法随机（4 路随机配置 + 随机地址）。

## 8. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:353-370`（store 版调用）
- `XiangShan/src/main/scala/xiangshan/backend/fu/NewCSR/Debug.scala:301-343`（`MemTrigger` / `DcacheLineBitsEq`）
- `Debug.scala:246-297`（`BaseTrigger`：模式选择、chain、action 优先级）
- `XiangShan/src/main/scala/xiangshan/backend/fu/util/Trigger.scala:157-249`（`TrigMatchEnum`、`TriggerCmp`、`TriggerCheckCanFire`）
- `XiangShan/src/main/scala/xiangshan/Bundle.scala:762-774`（`TriggerAction`）
- `soc-split/rtl/MemTrigger_3.sv`（固定生成 RTL，本 DUT）
