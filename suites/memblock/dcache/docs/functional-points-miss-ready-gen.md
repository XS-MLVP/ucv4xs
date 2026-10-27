# MissReadyGen 功能点

DUT：`MissReadyGen`（`soc-split/rtl/MissReadyGen.sv`），层次：DCache miss 请求入口叶块。
它把 `LoadPipe ×3` 以及 MainPipe 的 4 路 miss 请求原样送到 `MissQueue` 的 4 个查询端口，
并把 MissQueue 的 ready 原样送回各路。无时钟、无复位、无内部状态。

端口分组：

- 通道 0（store/atomic/预取来源较全）：source、pf_source、cmd、addr、vaddr、vaddrAlias、
  vaddrSet、full_overwrite、word_idx、amo_data、amo_mask、amo_cmp、req_coh_state、id、
  isBtoT、occupy_way、cancel、store_data(512)、store_mask(64)。
- 通道 1..3（load/spec miss）：source、cmd、addr、vaddr、vaddrAlias、vaddrSet、
  req_coh_state、id、isBtoT、occupy_way、cancel、isSpecMiss。

## MRG-FP-001 四路请求直通

4 个输入通道的 `valid` 和全部 payload 字段在同一个组合路径上送到对应 `io_queryMQ_i`；
`io_queryMQ_i_req_valid == io_in_i_valid`，所有 bits 逐位相等。

## MRG-FP-002 ready 反向直通

每路 `io_in_i_ready == io_queryMQ_i_ready`：MissQueue 的背压只影响对应通道，不跨路传播。

## MRG-FP-003 通道间独立

任一路的 valid/payload/ready 变化不影响其它三路的输出；同拍 4 路可以各自有效或无效。

## MRG-FP-004 位域保真（含宽载荷）

每个 payload 字段（包括通道 0 的 512-bit store_data、64-bit store_mask、128-bit
amo_data/amo_cmp）都逐位透传；全零、全一、单 bit walking、随机值都成立。

## MRG-FP-005 零状态组合语义

DUT 没有时钟/复位：输出只由当前输入决定。把同一组输入保持多个求值周期，输出不变；
改变输入后立即（同一求值周期）反映到输出。

## 覆盖组

- `mrg.channel`：4 个通道 × valid、ready、payload 形态。
- `mrg.field`：通道 0 的宽字段类别；通道 1..3 的字段类别。
- `mrg.independence`：单路有效、多路有效、ready 位图。
- cross：通道 × valid；通道 × ready。
