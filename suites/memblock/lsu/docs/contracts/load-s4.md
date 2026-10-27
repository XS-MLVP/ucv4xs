# `LoadUnitS4`：load head/tail 合并结果直通

## 1. 职责

生成的 `LoadUnitS4` 没有任何状态：把 S3 的 head 输出原样转发为
`unalignConcat`，供 S3 在 `headHasException` 时选择 head 的异常/地址载荷。

## 2. 语义

`valid` 与 41 个字段（11 个 cause 位、6 个异常位、entrance、vaddr/fullva/mask/
paddr、mshrId、tlbId/tlbFull、specialModeRequest、handledByMSHR、causeOrR、
matchInvalid、shouldWakeup、hasException、headAlwaysWriteback、
writebackDependOnTail、shouldRarViolation）全部恒等。

UT 的价值是证明**没有字段被延迟、改名或门控**：head/tail 合并依赖 head 的
`cause*`、`paddr`、`shouldWakeup`、`shouldRarViolation` 等位与 tail 精确对齐。

## 3. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala`（S4 连接）
- `soc-split/rtl/LoadUnitS4.sv`（本 DUT，纯 `assign`）
