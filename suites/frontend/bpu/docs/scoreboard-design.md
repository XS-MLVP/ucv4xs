# Scoreboard 设计

状态：**已在 xreactor 实现，并迁移到本仓库**。

本仓库的 DUT 专用比较组件位于 `suites/frontend/bpu/<dut>/checker/`，目录职责见
[repository-layout.md](repository-layout.md)；本文所述通用机制仍在 xreactor。

本文定义 xreactor/BPU 验证环境 Scoreboard 的职责、用户接口和失败语义。通用
`Scoreboard`、`XTransfer`、异常和状态位于 xreactor；本仓库的 predictor agent 已绑定
新接口，旧 `InOrderPipelineRouter` 和本地 `XTransfer` 已删除。

设计目标不是照搬 UVM 类层级，而是保留硬件验证中真正有用的职责边界，并让
pytest 用户只需要理解一个检查对象：

- 已经拿到一对 expected/actual 时，直接 `check()`；
- 输入输出来自并行流水线时，`bind()` driver 和 monitor，由同一个对象自动对齐后
  调用同一个 `check()`；
- 比较失败一定能到达 pytest，并带有事务、时序、状态和字段差异；
- reference model、输入输出关联和数值比较互相独立；
- driver/monitor 负责协议与时序，测试用例不出现边沿和裸信号操作。

## 1. 从验证需求得到的两个维度

验证场景可以用两个正交维度描述。

第一个维度是数据如何到达比较点：

- **直接模式**：测试或 agent 已经取得 actual，输入输出关系天然明确；
- **异步模式**：通过 `bind()` 连接 driver 和 monitor；driver 连续接受请求，monitor
  连续产生响应，需要自动关联。

第二个维度是 expected 从哪里来：

- **显式期望**：常量、测试向量或由用例直接构造的期望值；
- **参考模型**：根据 request 和模型状态计算期望值。

由此得到的四种用法如下。它们不是四套类，也不应形成四套测试风格。

| 数据到达方式 | 显式期望 | 参考模型 |
| --- | --- | --- |
| 直接 | `check(actual=..., expected=...)` | 先调用模型，再调用同一个 `check()` |
| 流水线 | `submit(..., expected=...)`，自动关联并检查 | `submit(...)`，接受时调用模型，自动关联并检查 |

这里最重要的边界是：

1. **关联只回答“这个 actual 属于哪个 request”**；
2. **期望值生成只回答“这个 request 应该得到什么”**；
3. **比较只回答“expected 和 actual 是否一致”**。

三者不得互相猜测。关联策略不能判断对错，比较函数不能决定 actual 应该匹配哪个
request，reference model 也不负责等待 monitor。

## 2. 一个具体类，两种工作模式

对用户只暴露一个主要类型：`Scoreboard`。它是可直接实例化的具体类，默认做结构化
相等比较。需要定制时优先传入普通比较函数；只有需要复用状态和行为时才继承。

建议的最小公共接口为：

```python
class Scoreboard(Generic[RequestT, ExpectedT, ActualT]):
    def __init__(
        self,
        name: str,
        *,
        compare: Callable[[ExpectedT, ActualT], None] | None = None,
        expected: Callable[[RequestT, CheckContext], ExpectedT] | None = None,
    ): ...

    def check(
        self,
        *,
        expected: ExpectedT,
        actual: ActualT,
        context: CheckContext | None = None,
    ) -> None: ...

    def compare(self, expected: ExpectedT, actual: ActualT) -> None: ...

    def bind(
        self,
        execution: Execution,
        *,
        driver: AcceptedDriver[RequestT, ActualT],
        monitor: Monitor[ActualT],
        latency_cycles: int | None = None,
        request_key: Callable[[RequestT], Hashable] | None = None,
        response_key: Callable[[ActualT], Hashable] | None = None,
    ) -> Self: ...

    def associate(
        self,
        observation: Transfer[ActualT],
        pending: Sequence[XTransfer[RequestT, ActualT]],
    ) -> XTransfer[RequestT, ActualT] | None: ...

    def submit(
        self,
        request: RequestT,
        *,
        expected: ExpectedT | Missing = MISSING,
    ) -> XTransfer[RequestT, ActualT]: ...

    async def drain(self) -> ScoreboardStatus: ...
    async def aclose(self) -> None: ...

    @property
    def status(self) -> ScoreboardStatus: ...
```

普通测试作者通常只会看到 `check()` 或 agent 包装后的 `predict()` / `submit_predict()`；
agent 作者使用 `bind()` 和 `submit()`；accepted/observed stream 与关联缓冲区属于框架
实现细节。这个分层是用户体验的一部分，不能把完整底层 API 都推给测试用例。

`CheckContext` 是不可变诊断快照，不是另一个控制对象。异步模式由框架填充它，直接
模式通常无需构造：

```python
@dataclass(frozen=True, slots=True)
class CheckContext:
    scoreboard: str
    mode: ScoreboardMode
    sequence_id: int | None = None
    request: object | None = None
    transfer_state: TransferState | None = None
    accepted_event: XEvent | None = None
    observed_event: XEvent | None = None
```

`check()` 是唯一检查入口，内部调用可覆写的 `compare()`。`bind()` 不换一套比较语义，它只启动并行的数据获取和
关联；关联得到 `(transfer, observation)` 后仍然调用 `check()`。直接模式失败就在
`check()` 调用点抛出，而不是返回容易被忽略的布尔值。

`associate()` 是关联能力唯一的可覆写方法。普通用户不调用它；框架在 accepted 或
observed stream 增加数据时调用它。它只选择 observation 对应的 pending transfer，
不生成 expected，也不比较数据。

`submit()` 是异步模式下的便利入口，它把 request 交给已绑定的 driver，并允许把
本次显式 expected 附着到对应 `XTransfer`。它不接触 DUT 信号，也不取代 driver。
agent 可以继续提供领域接口，例如 `submit_predict()`，内部转调 Scoreboard 即可。

异步模式下 expected 的优先级固定为：

1. `submit(request, expected=value)` 提供的本事务期望；
2. 构造 Scoreboard 时传入的 `expected(request, context)`；
3. 两者都不存在时抛出 `MissingExpectedError`，不允许把 `None` 默认为“无需检查”。

这一区分让静态向量和参考模型共用同一个接口，而不需要引入 `ReferenceScoreboard`、
`PipelineScoreboard` 等组合类。

## 3. 四种场景的用户写法

### 3.1 串行 + 显式期望

driver 在这种场景中只是 agent 内部的 interface/protocol 封装；Scoreboard 无需绑定
driver 或 monitor。

```python
scoreboard = Scoreboard("ubtb.prediction")

actual = await agent.predict(pc)
scoreboard.check(actual=actual, expected=wanted)
```

如果只有一两个局部性质，直接写 pytest `assert` 仍然合理。Scoreboard 的价值是统一
结构化差异、上下文和统计，而不是禁止普通 assertion。

### 3.2 串行 + 参考模型

```python
scoreboard = Scoreboard("tage.prediction")

request = TageLookup(pc, history)
actual = await agent.predict(request)
expected = model.predict(request)
scoreboard.check(actual=actual, expected=expected)
```

与上一种模式相比，只改变 expected 的来源；比较逻辑完全相同。

### 3.3 流水线 + 显式期望

```python
scoreboard = Scoreboard("mbtb.prediction").bind(
    execution,
    driver=lookup_driver,
    monitor=prediction_monitor,
    latency_cycles=3,
)

for request, wanted in vectors:
    scoreboard.submit(request, expected=wanted)

await scoreboard.drain()
```

提交循环中没有 `await`，所以 driver 可以每周期接受一个新 request。`drain()` 是
Scoreboard 对外的批次同步点：它等待调用前已经提交的事务全部完成，并在任一事务失败
时直接向 pytest 抛出异常。测试不需要保存 transfer 列表，也不需要知道内部是否使用
哪一种批量等待机制。

只有确实需要取得某个 actual、单独等待或取消事务时，才保留 `submit()` 返回的
`XTransfer`：

```python
transfer = scoreboard.submit(request, expected=wanted)
actual = await transfer
```

不能在每次提交后立刻 `await transfer`，否则会主动把流水线重新串行化。

### 3.4 流水线 + 参考模型

```python
scoreboard = Scoreboard(
    "tage.prediction",
    expected=lambda request, context: model.predict(request),
).bind(
    execution,
    driver=lookup_driver,
    monitor=prediction_monitor,
    latency_cycles=3,
)

for request in requests:
    scoreboard.submit(request)

await scoreboard.drain()
```

对于有状态模型，`expected` 必须在 request 的**接受事件**上调用，而不是在 Python
调用 `submit()` 时调用。这样 backpressure、并行 train/predict 以及模型状态更新的
顺序都与 DUT 可见的事务顺序一致。`CheckContext` 会携带接受事件，模型不需要读取
时钟或 DUT 信号。

如果 train 和 predict 可以在同一周期被接受，reference model 还必须声明与 RTL 一致
的同周期优先级。agent 应按 accepted event 的时戳和协议优先级更新模型，不能依赖两个
asyncio task 恰好谁先运行。这个排序属于输入事务语义，不属于 response association。

## 4. 异步模式的数据流

```text
test / sequence
      |
      | submit(request [, expected])
      v
    driver ---- accepted XTransfer ---- expected source ----+
                         |              (if not explicit)    |
                         |                                   v
                         +---------------------------- [ association ]
                                                             ^
                                                             |
    monitor ---------------- observed Transfer --------------+
                                                             |
                                                             v
                      Scoreboard.check(expected, actual)
                              |                 |
                            pass              fail
                              |                 |
                    XTransfer.complete   XTransfer.fail
                                                |
                                  pytest await/drain/aclose
```

driver 和 monitor 始终独立推进。Scoreboard 不采用“发送一个 request，等一个 response，
再发送下一个”的循环。它分别消费 accepted stream 和 observed stream，所以同一时刻可
以存在多个 `PROCESSING` 状态的事务。

`@on()` 属于 monitor 的实现机制：它在采样相位同步捕获不可变 snapshot，再交付给
Scoreboard。Scoreboard 不直接订阅裸信号，也不出现 `RisingEdge`、`FallingEdge`、
`AsRiseWrite` 或 `AsFallWrite`。写入相位由 interface/driver 封装，采样相位由 monitor
封装。

## 5. 关联不是基类，但有独立覆写点

不引入 `InOrderPipelineMatcher` 之类要求用户继承的基类。关联是异步模式的内部能力，
通过少量配置选择：

- `latency_cycles=N`：按接受周期加固定延迟关联。适合当前 BPU 中每周期都采样、输出
  没有独立 valid 的 predictor；
- 不指定 latency 和 key：按 accepted/observed 的先后顺序关联。适合 monitor 只在
  真正完成事务时发布 observation 的 in-order ready/valid 协议；
- 同时提供 `request_key` 和 `response_key`：按架构 tag/ID 关联乱序响应。

`latency_cycles` 的单位是接口时钟周期。实现不得把 picker/xcomm 的半周期 tick（当前
代码里的 `cycles * 2`）暴露给用户；event 到 cycle 的换算是 clock/backend 的内部
细节。

三种配置互斥。只提供一个 key、同一个 key 重复占用、找不到 request 的响应、一个
request 收到多个响应，都必须作为协议/关联错误报告，不能进入比较阶段。

内部可以使用策略对象实现这三种算法，但它不是 Scoreboard 的公共继承体系。将来新增
关联算法时，不要求再建立一个 matcher 基类；特殊协议直接覆写 `associate()`：

```python
class TaggedScoreboard(Scoreboard[Request, Expected, Response]):
    def associate(self, observation, pending):
        response_tag = observation.value.tag
        return next(
            (
                transfer
                for transfer in pending
                if transfer.request.tag == response_tag
            ),
            None,
        )
```

这里的 `pending` 是按接受顺序排列的只读快照。返回值只有两种：

- 返回其中一个 `XTransfer`，表示建立一对一关联；
- 返回 `None`，表示当前信息不足，observation 继续保留，等新 accepted transaction
  到来后重试。

框架负责从缓冲区移除已经匹配的两项，并验证返回的 transfer 确实属于 `pending`、尚未
匹配且没有重复使用。`associate()` 必须是同步、确定、无副作用的，不能等待时钟、调用
reference model 或执行比较。如果一个硬件响应由多个拍组成，应先由 monitor 组装成一
个完整 `Transfer`，而不是让 `associate()` 同时承担协议解码。

普通 FIFO、固定延迟和 tag/ID 协议继续使用 `bind()` 参数，不需要继承。覆写
`associate()` 只服务于无法由这些配置表达的协议，并且不影响同一个 `check()`。

## 6. 比较语义

默认比较器执行结构化相等比较，并在失败时生成字段级差异。至少支持：

- dataclass；
- mapping；
- list/tuple 和嵌套组合；
- xreactor `BundleValue`；
- 标量和四态逻辑值。

差异路径采用稳定、可复制到代码中的表示，例如：

```text
prediction.entries[1].target: expected 0x40001234, actual 0x40001230
prediction.entries[1].taken:  expected 1,          actual 0
```

为防止大型 bundle 淹没 pytest 输出，默认显示前 20 个差异，并报告被省略的数量。

定制比较优先使用普通函数：

```python
def compare_prediction(expected, actual):
    assert actual.valid == expected.valid
    if expected.valid:
        assert actual.target == expected.target

scoreboard = Scoreboard("prediction", compare=compare_prediction)
```

比较函数只接收 expected 和 actual，不负责查 request、等时钟或改变 transfer 状态。
Scoreboard 会保留原始 `AssertionError` 作为异常 cause，并补充事务上下文。需要复用
复杂有状态比较时可以覆写 `compare()`，但这只是 Python 扩展点，不是必需用法。

## 7. 异常必须可靠到达 pytest

### 7.1 异常类型

建议的异常层次很小：

```text
AssertionError
└── ScoreboardError
    ├── ScoreboardMismatch       # expected 与 actual 不一致
    ├── ScoreboardAssociationError
    └── ScoreboardIncompleteError
```

它们都继承 `AssertionError`，所以 pytest 原生把它们判为验证失败，不需要自定义 pytest
插件来决定 verdict。配置错误（重复 bind、负延迟、缺少成对 key）使用 `ValueError` 或
`RuntimeError`，以区别于 DUT 行为失败。

### 7.2 失败信息

一次 mismatch 至少展示：

```text
ScoreboardMismatch: mbtb.prediction
  mode: ASYNC
  sequence_id: 17
  transfer_state: PROCESSING
  request: MbtbLookup(pc=0x40000800)
  accepted: cycle 142
  observed: cycle 145
  expected: MbtbPrediction(...)
  actual:   MbtbPrediction(...)
  differences:
    entries[1].target: expected 0x40001234, actual 0x40001230
  status: checked=8, passed=7, failed=1, pending=3
```

直接模式没有 sequence/timing 时只省略不存在的字段，不伪造默认值。

### 7.3 后台任务不能吞异常

异步模式的比较发生在 monitor/关联后台任务中，不能依赖 asyncio 的 “Task exception
was never retrieved” 警告。第一次失败必须同时：

1. 用该异常调用对应 `XTransfer.fail(error)`，使 `await transfer` 立即抛出；
2. 在 Scoreboard 中保留失败，使 `await scoreboard.drain()` 抛出；
3. 若调用方两者都没有等待，在 `await scoreboard.aclose()` 时抛出。

内部后台 task 可以捕获异常以完成清理，但不得把捕获当作处理完成。公共同步点必须
重新抛出原异常。比较成功后才允许调用 `XTransfer.complete()`，避免调用方先取得一个
随后被判错的 actual。

同一个 failure 只应作为 pytest 结果报告一次。`await transfer` 或 `drain()` 抛出后会
把该 failure 标为已观察；随后 `aclose()` 只负责清理，不再额外制造 teardown error。
如果调用方从未等待任何公共同步点，`aclose()` 才承担最后兜底报告。实现需要在
`XTransfer` 的 await 路径或等价的 completion handle 上提供 acknowledgement，不能靠
检查 asyncio Future 的 `exception()` 是否被读取来猜测。

第一版采用 **fail-fast**：保存并抛出第一个 mismatch，其他仍在途事务进入明确的
FAILED 或 CANCELLED 状态。异常中的 status 保留失败瞬间的队列信息。后续如果需要
一次显示多处失败，可以在不改变 `check()` 语义的前提下增加聚合模式；第一版不引入
策略开关。

## 8. `XTransfer` 生命周期

Scoreboard 不创造另一套 transaction 状态。异步模式沿用现有 `XTransfer`：

```text
submit        driver accepts       compare passes
PENDING  -----------------> PROCESSING -------------> COMPLETED
   |                              |                        result=actual
   |                              |
   +------------------------------+----> FAILED
   |
   +-----------------------------------> CANCELLED
```

- `accepted_event` 只由 driver 设置；
- `completed_event` 来自关联后的 monitor observation；
- Scoreboard 在比较通过后 `complete(event, actual)`；
- 比较、关联或 reference model 失败时 `fail(error)`；
- redirect/flush 是协议行为，显式 `cancel()`，不能伪装成通过或静默丢失。

`drain()` 在调用时建立一个 submission watermark，等待该 watermark 之前的事务全部
进入 terminal state，并在存在失败或意外未完成时抛出；并发发生在 watermark 之后的
新提交属于下一次 drain。成功时只返回 `ScoreboardStatus`，不复制或长期保存所有
actual。它不自行推进未知数量的时钟，也不内置墙钟超时；用例仍可使用
`asyncio.timeout(...)` 定义场景级上限。

`aclose()` 先停止接受新事务，再清理 subscription 和后台 task。正常关闭时若仍有未
说明原因的 PENDING/PROCESSING 事务，抛出 `ScoreboardIncompleteError`。只有显式的
reset/redirect/fixture-abort 路径可以请求取消，避免 teardown 把漏响应变成假通过。

## 9. 生命周期与仿真推进

agent 拥有 Scoreboard、driver 和 monitor 的生命周期。推荐在 agent `start()` 中完成
bind，在 `aclose()` 中等待 drain 并关闭；测试通常只看到 `predict()`、
`submit_predict()` 和返回的 `XTransfer`。

当前事件驱动 backend 中，永久时钟 subscription 会让仿真继续推进。因此绑定不等于
永久采样：

- 第一个 outstanding transfer 出现时启用 monitor subscription；
- 最后一个 transfer terminal 后进入 quiescent 状态并撤销 subscription；
- 下一批提交时自动重新启用；
- bind/关闭的重复调用具有明确错误或幂等语义，不泄漏 task。

这一行为应由组件实现和测试覆盖，不能要求用例手工 start/stop monitor。

## 10. Scoreboard 的统计职责

Scoreboard 有**诊断统计**，但没有**验证计划统计**。

`ScoreboardStatus` 是只读快照，建议包含：

- mode：`DIRECT` 或 `ASYNC`；
- submitted、accepted、observed；
- checked、passed、failed；
- pending、processing、completed、cancelled；
- unmatched request/observation 数量；
- first failure（如果存在）。

这些数字用于异常消息、调试和发现漏响应，不用于计算“功能完成度”。各层职责如下：

| 层次 | 回答的问题 | 结果归属 |
| --- | --- | --- |
| Scoreboard | 已关联的 transaction 是否比较一致？是否有漏项？ | transaction 诊断计数和异常 |
| pytest | 本次 test 是否通过？ | PASS/FAIL/XFAIL/ERROR |
| functional-point plan | 需求/功能点是否被执行并通过？ | 功能点完成率、通过率 |
| functional coverage | 指定场景/bin 是否被观测？ | bin/cross 命中率 |
| RTL coverage | 哪些 RTL 结构被执行？ | line/toggle/branch 等覆盖率 |

功能点通过率和 functional coverage 是两部分。一次测试可以命中某个 coverage bin 后又
因 Scoreboard mismatch 失败；也可以所有 transaction 都比较通过，但仍未命中计划中的
某个 bin。统一 HTML 报告可以并列展示它们，但不得把 Scoreboard 的 `passed/checked`
冒充功能点完成率或 functional coverage。

## 11. 与 UVM 的关系

本设计采用 UVM 中成熟的职责划分，但不复制 factory、phase、objection 和 analysis
port 类层级：

| UVM 概念 | 本设计 |
| --- | --- |
| sequence item | request dataclass + `XTransfer` |
| sequencer/driver | XReactor driver submission scheduling + accepted stream |
| monitor analysis transaction | immutable xreactor `Transfer` |
| analysis FIFO / matching | Scoreboard 异步模式内部关联 |
| predictor/reference model | `expected(request, context)` callable |
| scoreboard compare | `Scoreboard.check()` |
| report/objection | pytest exception + `drain()`/fixture lifetime |

UVM scoreboard 通常还承担 analysis port 汇聚、matching 和 report。Python 中不需要为了
这些职责建立多层组件树；一个 Scoreboard 用直接/异步两种模式即可保持相同的用户体验。

## 12. 对 xreactor 组件契约的要求

基础 `Driver.send()` 只表示一次发送的结束事件，不承担多个 outstanding request
与最终 response 的生命周期。xreactor 现用 `AcceptedDriver` Protocol 和
`AsyncDriver` 模板补足异步提交能力：

- 异步 driver 可以 `submit(request) -> XTransfer`；
- driver 发布 accepted transfer stream；
- monitor 发布不可变 observed `Transfer` stream；
- Scoreboard 可以在 terminal 时通知 driver retire bookkeeping；
- 所有 stream 都有有界容量和明确 overflow 错误。

这些能力不要求所有简单 `Driver` 改成异步 driver，也不要求 reference model 继承
框架基类。`AsyncDriver(max_active=1)` 将输入发射串行化；更大的
`max_active` 允许不同 transfer 的阶段重叠，但具体 Driver 必须仲裁共享端口。
输入重叠与已经接受的请求有多个未完成响应，是两个不同的概念。

`Transfer` 与 `XTransfer` 的含义继续严格区分：

- `Transfer[T]` 是 monitor 在某一事件捕获到的不可变 observation；
- `XTransfer[RequestT, ResponseT]` 是从提交到完成、可 await 的任务句柄。

不要把所有 event 或 monitor snapshot 都命名成 `XTransfer`。

## 13. 已完成的迁移

迁移按以下步骤完成：

1. 在 xreactor 增加具体 `Scoreboard`、异常、context、status 和直接 `check()`；
2. 为 pipelined driver/monitor 定义 accepted/observed 契约，把通用 `XTransfer` 生命周期
   下沉到 xreactor；
3. 实现 `bind()`、固定延迟/FIFO/key 三种关联以及后台异常传播；
4. 在本仓库把 `InOrderPipelineRouter` 替换为 `Scoreboard`，例如
   `prediction_router` 改为 `prediction_scoreboard`；
5. agent 的 `submit_predict()` 转调 `scoreboard.submit()`，保持现有测试入口稳定；
6. 通过全部流水线回归后删除 router，不保留两套长期并行的抽象。

旧 Router 各职责的去向为：

| `InOrderPipelineRouter` 当前内容 | 迁移后 |
| --- | --- |
| `reference(request)` | Scoreboard 的 expected source |
| `checker(expected, actual)` | `Scoreboard.check()` / compare callable |
| accepted + observation 字典 | bind 模式内部 association |
| `transfer.complete/fail` | Scoreboard 的统一成功/失败路径 |
| monitor start/stop | bind 模式生命周期 |

## 14. 验收条件

实现验收至少需要以下自动化测试，而不只是“现有 BPU 用例还能跑”：

- 直接模式默认比较通过和字段级 mismatch；
- 自定义 compare 的 `AssertionError` 保留为 cause；
- 多个 request 连续 submit，接受周期连续且完成顺序正确；
- 显式 expected 与 reference model 两种 async 用法；
- reference model 在接受事件而不是提交调用点执行；
- 固定延迟、FIFO、tag 三种关联；
- 自定义 `associate()` 可以匹配特殊协议，且无法读取 expected 或调用 compare；
- 重复 key、未知 response、重复 response、monitor overflow；
- mismatch 能分别从 `await transfer`、`drain()`、`aclose()` 到达 pytest；
- compare 成功前 transfer 不进入 COMPLETED；
- redirect/flush 后 transfer 为 CANCELLED，普通漏响应为 incomplete failure；
- drain 后 monitor subscription 停止，再次 submit 可以重新启用；
- status 计数与每个 `XTransfer` 的 terminal state 一致；
- 测试代码中不出现显式边沿等待或裸 `Set()`；
- 本仓库的串行、并行和已知 strict xfail 回归结果不退化。

完成这些条件后，Scoreboard 才同时满足易理解、低心智负担和流水线验证所需的完整失败
语义，而不只是把现有 Router 改一个名字。
