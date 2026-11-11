# `StoreUnitS3`：head-only 输出与写回延迟管线

## 1. 职责

S3 有两条互不相同的路径：

1. **head-only 流水寄存器** `pipeOut`：只有非对齐 head beat 才置 valid，供 S4 做
   head/tail 合并；
2. **一拍写回延迟管线**：把混合载荷延迟一拍后送 `stout`（ROB 写回）与
   `exceptionInfo`（异常信息）。

## 2. 语义

```
headHasException = unalignConcat.valid && unalignConcat.hasException
kill             = RobPtr.needFlush(pipeIn.robIdx)          // 无 valid 门控
delayIn.valid    = pipeIn.valid && !kill
                   && ((!mmio && !isCbo) || hasException)
                   && !unalignHead && !instrType[2] && !needRSReplay
delayIn.bits     = headHasException ? concat 的异常/trigger/fullva/gpaddr 等字段
                                    : pipeIn 的同名字段
                   // robIdx / nc / mmio / memBackTypeMM / instrType 恒取 pipeIn
pipeOut.valid    = pipeIn.valid && !kill && unalignHead
pipeOut.bits     = pipeIn 的 13 个异常/trigger/fullva/gpaddr 字段
```

写回（延迟管输出）：

```
stout.toRob.valid = delayOut.valid && !instrType[1]     // 向量 store 不写 ROB
exceptionInfo.valid = 同上
stout.bits = robIdx + 6 个异常位 + trigger
           + debugInfo.isMMIO = mmio
           + debugInfo.isNCIO = nc && !memBackTypeMM
exceptionInfo.bits = robIdx + 6 个异常位 + vaddr = fullva
                   + vaNeedExt/isHyper/isForVSnonLeafPTE + gpaddr[49:0]
```

## 3. 要点

- **MMIO / CBO 只有带异常时才写回**：正常完成的 MMIO store 由 SQ/Sbuffer 路径处理，
  不走 ROB 写回；带异常的才需要 ROB 记录。
- **`needRSReplay` 抑制写回**：需要重放时不产生 ROB 写回。
- **`exceptionInfo.vaddr` 是 store 自己的 fullva**（`src+imm`），不是 TLB 响应里的
  fullva；后者只进非对齐尾段地址。
- 延迟管 `out.ready` 恒为 true，所以进入后一拍即可见；输入侧 redirect 过滤一次，
  已消费的 beat 不会被后续 redirect 撤回。

## 4. 依据

- `NewStoreUnit.scala:740-830`（S3 逻辑与延迟管实例化）
- `soc-split/rtl/StoreUnitS3.sv`（本 DUT）
