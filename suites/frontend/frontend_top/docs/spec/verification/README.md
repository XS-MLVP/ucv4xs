# Frontend 集成验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `frontend` / `Frontend` | 骨架；合同与环境待实现 | [范围、工作与完成条件](frontend.md) | [实现、用例与命令](../../../testbenches/frontend/README.md) |

<!-- ucv:work-index:end -->

唯一验收对象为真实 `Frontend` 顶层 DUT，工作范围与待确认条件见
[frontend 合同](frontend.md)。负责人待认领；当前仅有绑定与显式失败骨架。

BPU、FTQ、IFU、IBuffer、InstrUncache、ICache 的单元合同各自由所属包维护。
这里负责经评审的真实连接、背压、取消、WFI 等组合性质；各子模块通过并不代替顶层证据。
FrontendBridge 物理位于 MemBlock，其缓冲与三通道组合合同由
[frontend_bridge](../../../../../memblock/frontend_bridge/docs/spec/verification/README.md) 维护。
