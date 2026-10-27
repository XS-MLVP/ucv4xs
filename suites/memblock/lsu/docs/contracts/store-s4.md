# `StoreUnitS4`：head/tail 合并结果直通

## 1. 职责

生成的 `StoreUnitS4` 没有任何状态：它把 S3 的 head 输出原样转发为
`unalignConcat`，供 S3 在 `headHasException` 时选择 head 的异常载荷。

## 2. 语义

`valid` 与 13 个字段（6 个异常位、trigger、fullva、vaNeedExt、isHyper、
isForVSnonLeafPTE、gpaddr、hasException）全部恒等。

这一级的正确性价值在于**证明它确实没有副作用**：任何在 S4 被改写或延迟的字段都会
破坏 head/tail 合并语义，所以 UT 逐位比较而不是"看起来一样"。

## 3. 依据

- `NewStoreUnit.scala:830-850`（S4 连接）
- `soc-split/rtl/StoreUnitS4.sv`（本 DUT，纯 `assign`）
