# PTW 请求与完成身份（2026-11-01）

## 范围与独立依据

这是 public-893e1580b + DefaultConfig 的 standalone PTW 合同，不是整个 MMU 或 ISA
签核。PTW 单 outstanding；根/中级 leaf 通过 resp 返回，4KB leaf 的剩余工作通过 LLPTW
handoff 交出。输入身份来自调用者的 VPN、source、s2xlate，不从返回字段倒推。

## 接受、取消与完成

`l2/ptw_walker.py` 为每次 issue 建立 sequence：

1. 在任何写引脚前校验字段范围。xcomm 的 mWidth=0 是 scalar logic（1 位逻辑），
   不是零位字段；正常请求只接受 0/1，拒绝 Z/X 的 2/3 编码和向量截断。
2. 持有 offer 并服务其他通道；edge 的沿前 valid && ready 快照才建立 accepted_tick，
   不是 issue 调用或沿后 ready。接受后撤销 valid 和本次请求 payload。
3. 冻结 `WalkRequest(sequence,vpn,source,s2xlate,accepted_tick,handoff_start)`。
   response 核对 source/stage，LLPTW 核对 VPN/source/stage 且只看本次接受后的记录。
4. 当前请求最多消费一次 response/handoff；没有已接受请求时 wait_response 立即失败，
   旧 handoff 日志、重复 handoff、错 source 或等待期间取消均不能返回成功。
5. 已观察的 sfence/CSR change 将活跃请求记为 flush；reset 清理本环境的状态。未完成
   请求禁止被下一次 issue 覆盖。等待超时保留未完成状态，供显式恢复或后续检查。

accepted_tick / completion.tick 使用 PtwEnv.edge 的沿计数，不是框架 XEvent.tick；本轮
不把它作为跨 agent 的全局时间关联凭据。接受本身仍必须经过实际 RisingEdge，而不能
只因读取到 ready 或调用 issue 就计数。

response 的具体翻译答案仍由 PageMemory 的调用者构造和原有断言核对；本次身份检查
不是新的页表 golden。bitmap/HPTW responder 和其他 MMU 模块的完整义务账本未因此完成。

## 正反对照

- `tests/checkers/test_ptw_completion.py`：历史 handoff、零接受、重复完成、错误 source、
  当前合法 handoff、取消以及 scalar 非法编码。这里是完成观察/驱动边界注入，不计
  原生功能 credit，也不是 RTL mutation。
- `tests/l2/test_ptw_identity.py`：真实 PTW 先 handoff，再保留累积日志，以相同 VPN/
  不同 source 做新 root-leaf 翻译，独立检查无故障、PPN/level 和逐请求完成类型。
- 对 0017350 的旧 wait_response 冻结函数实验：历史 handoff 能让零接受/无新完成
  返回 None；新函数在相同错误对照下 fail closed，合法新 handoff 仍通过。

## 限制

本环境仍通过手工 edge + RisingEdge 维护多端口快照，尚未完整迁入 Toffee 的
SamplingMonitor/Driver/Agent；绕过环境推进时钟、其他模块的原生句柄和手工 service
仍是架构技术债。不能把本轮回归通过或旧 408 PASS 变成“MMU 语义全部无误”。
当前源代码及实际结果见[本轮复核](../../../../docs/lessons/semantic-boundary-repair-20261101.md)。
