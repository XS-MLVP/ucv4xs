# WritebackQueue 功能点

DUT：`WritebackQueue`（`soc-split/rtl/WritebackQueue.sv`），层次：DCache 上层写回队列。
生成配置：2 个 L2 通道，18 个 release 条目（DUT 只实例化可见条目），C 通道 256-bit
数据 beat。

## WQ-FP-001 请求受理

`io_req_ready=1` 时接收 `{param, voluntary, hasData, corrupt, addr, data}`，并按地址
第 6 位选择通道；地址/载荷在条目内保持，直到 C 响应完成且 D ack 返回。

## WQ-FP-002 C 通道响应类型

C 响应 opcode 由 `{1'b1, voluntary, hasData}` 决定，**与 `param` 无关**：

| hasData | voluntary | opcode | 语义 |
|---:|---:|---:|---|
| 1 | 1 | 7 | `ReleaseData`（主动让出脏行，2 个 256-bit beat 组成 64B） |
| 1 | 0 | 5 | `ProbeAckData`（probe 合并且要求数据） |
| 0 | 1 | 6 | `Release`（干净行主动让出） |
| 0 | 0 | 4 | `ProbeAck`（probe 合并，不带数据） |

`param` 是独立的 shrink/report 权限字段：在 Release 中作为 shrinkPermissions、
在 ProbeAck 中作为 reportPermissions 原样出现，可以是任意合法值（不要求 0）。
地址、corrupt 同样原样透传；size 固定为 6（64B）。

## WQ-FP-003 通道选择

C 响应出现在 `addr[6]` 选择的通道（0 或 1）；另一通道不产生响应。

## WQ-FP-004 条目生命周期

C 的所有 beat 完成后，等待 D 通道 `ReleaseAck`（source 必须匹配释放事务）；ack 后
条目释放，`io_req_ready` 恢复，可接收下一次写回。

## WQ-FP-005 miss 请求阻塞

条目占用期间，`io_miss_req_conflict_check_i` 与条目同块（addr[47:6]）时
`io_block_miss_req_i=1`；不同块不阻塞。C 完成并 ack 后阻塞解除。

## 覆盖组

- `wbq.release`：响应类型、通道、voluntary。
- `wbq.ack`：释放完成 / 未完成。
- `wbq.block`：同块阻塞 / 其他块放行。
