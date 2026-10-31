# FTQ 验证包结构

## 分层

| 层 | 职责 | 不允许做的事 |
|---|---|---|
| `harness` | 装载原生 DUT、维护执行上下文、登记引脚所有权、每拍检查指针安全网 | 提供功能判断；功能判断属于 checker |
| `transaction` | 合法域校验、事务身份与字段单位 | 引用 RTL 内部状态构造期望 |
| `bundle/ports` | 逻辑引脚名到生成 DUT 扁平引脚的映射 | 在测试里直接拼物理字符串 |
| `driver` | 占用引脚，按协议发射/保持/撤销请求 | 读取 DUT 决定下一个请求 |
| `monitor` | 每拍被动采样公开输出，生成不可变事务 | 驱动任何引脚 |
| `checker` | 独立 oracle/不变量比较 | 把 `reached` 或采样命中当作功能通过 |
| `agent` | 装配 driver、monitor、checker，提供测试事务 API | 在用例里直接 `.Set()` 引脚 |

测试文件只调用 agent 方法并断言事务；引脚所有权冲突、缺失引脚、非法编码会在
fixture 边界立即失败。

## 三个 agent

| Agent | 事务 | 驱动 | 监视 |
|---|---|---|---|
| `ResolveQueueAgent` | `ResolveReport`、`Training` | 后端 3 lane + IFU + 重定向 + BPU 入队 + ready | 训练输出（8 分支槽） |
| `CommitQueueAgent` | `CallRet` | 8 条 commit lane | `bpuTrain` 队首 |
| `FtqAgent` | `Prediction`、`Meta`、`BackendRedirect`、`IfuRedirect`、`ResolveReport`、`CallRet`、`Consumers` | prediction/meta/重定向/resolve/commit/ahead/consumer ready | prefetch、fetch、training、commit、redirect、flush、topdown、backend write、指针不变量 |

## 时序约定

- `predict()` / `override()`：拉高请求一拍，撤销全部 prediction 引脚，再走一拍。
  不能只清 `valid`：RTL 用 s2/s3 override 位更新 `bpuPtr`，残留的 override 位属于
  生产者协议违规。
- `backend_redirect()` / `ifu_redirect()`：请求在第一次采样边仍保持，随后撤销并再走一拍；
  `drive_*` + `finish_*` 用于需要精确对齐的单拍检查。
- `resolve_cycle()` / `set_resolve_lanes()`：不附加释放边，用于把同一 entry 的多个报告
  连续送入，避免训练在分支集合完整前出队。
- `allocate()`：按 prediction → s3 meta 的顺序产生合法所有权；需要 32 条以上时同时打开
  ICache 消费者以维持 PrefetchDepth。
- `Consumers` 更新是合并语义：只改调用中出现的通道，未出现的保持原值。

## 观察点

- 公开输出经 monitor 解码为 `TrainingEntry`、`CommitEvent`、`RedirectEvent`、
  `PrefetchRequest`、`FetchRequest`、`FlushEvent`、`Topdown`、`BackendWrite`。
- 所有权指针与 entry/meta 数组通过内部信号读取，只用于身份、不变量和存储证据；
  payload 期望来自 transaction 参数或独立 oracle。
- 生成闭包中没有 `$fatal`；`harness` 的每拍安全网和 FTQ agent 的 `InvariantMonitor`
  都检查同一份 CircularQueuePtr 合同，前者保证未启动 agent 的用例也不放过指针越界。
  其余 RTL 断言（EnumUInt 合法值、异常 one-hot 等）由 transaction 构造器在激励侧保证。

## 自检

`tests/checkers/` 标 `selftest`，不计硬件功能 credit：

- oracle 对错序、错 payload、错误冲刷范围的拒绝；
- 合法域拒绝（50 位地址、offset 0..31、异常互斥、lane 范围）；
- 活观察负对照：同一读取路径必须对错误 PC/指针/commit payload 报错；
- `tests/test_plan_audit.py` 校验功能点与用例双向可追溯。

## 扩展方式

新增能力时按此顺序落位：transaction 字段 → bundle 引脚 → driver 发射/撤销 →
monitor 解码 → checker 比较 → agent API → 用例。只有 `feature` 标记的用例计入
功能覆盖；自检、压力探针和被 RTL 缺陷阻塞的 strict XFAIL 单独统计。
