# `MemTrigger`（load 变体）：load 地址触发器匹配

## 1. 职责

`NewLoadUnit` 在 S1 用 load 版 `MemTrigger` 把 4 路 debug trigger 与本次 load 的
`vaddr/mask` 比较，输出 `TriggerAction` 进入异常/断点路径。

## 2. 与 store 变体的三处差别

1. 每路类型位是 `load`（不是 `store`）；
2. **没有 CBO 分支**：`DcacheLineBitsEq()` 对 load 返回 `false`，因此 `matchType`
   永远决定标量比较；
3. `isPrf` 抑制**仅标量路径**——向量 unit-stride 路径完全不看 `isPrf`。

## 3. 语义

```
标量路径： !select && !debugMode && !isPrf && tEnable && load
           && (matchType==3 → vaddr < tdata2[49:0]
               matchType==2 → vaddr >= tdata2[49:0]
               matchType==0 → vaddr == tdata2[49:0]
               其它(NAPOT=1) → 不匹配)
向量路径： !select && !debugMode && tEnable && load
           && vaddr[49:4] == tdata2[63:4]
           && (mask & (1 << tdata2[3:0])) != 0
chain：   canFire[i] = (前一路 chain 则前一路命中且 timing 相同) && hit[i] && !chain[i]
动作：    any(DebugMode) → 4'h1
          any(Breakpoint && triggerCanRaiseBpExp) → 4'h0
          否则 → 4'hF
```

`matchType` 在本接口是 2 bit，所以可达编码只有 EQ(0)/NAPOT(1)/GE(2)/LT(3)。

## 4. 依据

- `XiangShan/src/main/scala/xiangshan/backend/fu/NewCSR/Debug.scala:301-343`（load 变体）
- `Debug.scala:246-297`（模式选择、chain、动作优先级）
- `XiangShan/src/main/scala/xiangshan/backend/fu/util/Trigger.scala:157-249`
- `soc-split/rtl/MemTrigger.sv`（本 DUT）
