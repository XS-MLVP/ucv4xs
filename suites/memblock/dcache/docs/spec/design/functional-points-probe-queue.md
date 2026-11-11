# ProbeQueue 功能点

DUT：`ProbeQueue`（`soc-split/rtl/ProbeQueue.sv`，源码 `mainpipe/Probe.scala`），层次：
DCache 上层 probe 队列。生成配置：8 个 probe 条目，B 通道只有
`param/address/data`（source/opcode 由父块补齐），`data[0]` 表示 needData，
`data[2:1]` 提供别名索引位。

## PQ-FP-001 B 通道受理与 MainPipe 请求

空闲条目存在时 `io_mem_probe_ready=1`；受理后下一拍在 `io_pipe_req` 上产生
`probe=True` 的 MainPipe 请求，携带 `probe_param`、`probe_need_data`（= B.data[0]）、
`addr`、`vaddr`（由 address 与别名位构造）和条目 id。

## PQ-FP-002 权限目标编码

B.param 的 TtoB/TtoN/TtoT 原样进入 `probe_param`；三种权限都产生同构请求，只是
MainPipe 决定是否回数据。

## PQ-FP-003 LR/SC 保留块阻塞

probe 地址与 `io_lrsc_locked_block` 同块（addr[47:6]）时，MainPipe 请求被抑制；
保留释放后同一请求可继续。`io_update_resv_set` 也会在下一拍阻塞所有 probe。

## PQ-FP-004 条目占用

`pipe_req` 被 MainPipe 接收后条目进入等待响应状态；在本独立 DUT 中
`pipe_resp` 由父块 perf 事件驱动，因此单条目响应完成语义在 DCache 顶层
`test_probe_ack` 中验证（B → C ProbeAck）。

## 覆盖组

- `pq.probe`：param、need_data、lrsc 阻塞/放行。
