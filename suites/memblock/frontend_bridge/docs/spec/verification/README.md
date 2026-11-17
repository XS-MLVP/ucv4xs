# FrontendBridge 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `icache_ctrl_buffer` / `ICacheCtrlBuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](icache_ctrl_buffer.md) | [实现、用例与命令](../../../testbenches/icache_ctrl_buffer/README.md) |
| `icache_buffer` / `ICacheBuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](icache_buffer.md) | [实现、用例与命令](../../../testbenches/icache_buffer/README.md) |
| `instr_uncache_buffer` / `InstrUncacheBuffer` | 骨架；合同与环境待实现 | [范围、工作与完成条件](instr_uncache_buffer.md) | [实现、用例与命令](../../../testbenches/instr_uncache_buffer/README.md) |
| `frontend_bridge` / `FrontendBridge` | 骨架；合同与环境待实现 | [范围、工作与完成条件](frontend_bridge.md) | [实现、用例与命令](../../../testbenches/frontend_bridge/README.md) |

<!-- ucv:work-index:end -->

负责人：四个 DUT 各自待认领；当前均为显式失败骨架。当前工作是先确认 A/D 通道的
接受事件、保序/字段保持、reset 边界与 InstrUncache 常量字段合法域，再建立环境和检查器。
未执行当前基线硬件验收。

- [FrontendBridge](frontend_bridge.md)：真实三组缓冲的组合与通道隔离。
- [ICacheBuffer](icache_buffer.md)、[ICacheCtrlBuffer](icache_ctrl_buffer.md)：各自缓冲行为。
- [InstrUncacheBuffer](instr_uncache_buffer.md)：非缓存 Get 合法域与固定字段、响应缓冲。

MemBlock 实例化该桥；它不属于 Frontend 的 RTL 闭包。Frontend 对内连接与取消/WFI
集成性质由 [frontend_top](../../../../../frontend/frontend_top/docs/spec/verification/README.md) 负责。
