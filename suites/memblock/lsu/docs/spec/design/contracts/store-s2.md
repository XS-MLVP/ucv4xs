# `StoreUnitS2`：存储类型与访问异常

## 1. 职责

S2 用 TLB 的 PBMT 与 PMP 结果判定这条 store 是 cacheable / NC / MMIO，并形成最终的
访问异常（access fault）与错位异常（misalign）。输出分两类：组合的 `toSqAddrRe`
（给 SQ 的存储类型侧带）和寄存器化的 `pipeOut`。

## 2. 语义

```
tlbHit          = pipeIn.valid && pipeIn.tlbHit          // 重新与 valid 相与
kill            = RobPtr.needFlush(pipeIn.robIdx)         // 无 valid 门控
fire            = pipeIn.valid && !kill
pmpInaccessible = tlbHit && (pmp.st || (pmp.ld && isCboNoZero))
tlbInaccessible = exc[7] || exc[15] || exc[23]
isNC            = tlbHit && !tlbInaccessible && pbmt == 1
isMMIO          = tlbHit && !tlbInaccessible && (pbmt == 2 || (pbmt == 0 && pmp.mmio))
isUncache       = isNC || isMMIO
memBackTypeMM   = !(pmp.mmio && !tlbInaccessible)
af              = exc[7] || pmpInaccessible || (vector && isUncache)
                  || (isCbo && isUncache) || (isMMIO && !align)
am              = !align && scalar && isNC && !pmpInaccessible
hasException    = pipeIn.hasException || af || am
```

寄存器输出：`exc[7] = af`、`exc[6] = am`，其余异常位与 trigger 直通；
`nc/mmio/memBackTypeMM` 为上述判定。

组合输出：`toSqAddrRe.{nc,mmio,memBackTypeMM}` 直通判定，
`hasException = fire && hasException`，`isLastRequest = !unalignHead`；
`unalignHeadTlbHit = fire && unalignHead && tlbHit`（回送 S1，用于非对齐尾段的双响应）。

## 3. 要点

- **向量与 CBO 访问 uncache 空间会报 access fault**：这是本级的显式语义，不是误判。
- **MMIO 错位报 access fault，NC 错位报 misalign(6)**；若 NC 同时被 PMP 拒绝，
  `af` 置位而 `am` 被抑制。
- `pmp.ld` 只对 CBO 非零类操作生效（clean/flush/inval 只需读权限）。
- PBMT=3 与 PBMT=0+PMP 非 MMIO 都是正常 cacheable。

## 4. 输入合法域与 don't-care

- `pipeIn`：S1 输出；`tlbHit/align/unalignHead` 已由 S1 派生。
- `tlbResp`：S1 的同一份响应（S2 通过 pipeIn.pbmt/excp 位消费，不直接读响应；
  本 DUT 只接收 `pmp` 与 pipeIn）。
- `valid=0` 时 `pipeOut.bits` 保持旧值，不比较。

## 5. 依据

- `NewStoreUnit.scala:470-560`（S2 全部逻辑）
- `soc-split/rtl/StoreUnitS2.sv`（本 DUT）
