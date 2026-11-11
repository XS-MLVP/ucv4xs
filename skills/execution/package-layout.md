# 如何组织验证包的 driver/monitor 分层

## 何时使用、准备什么

新建验证工程、把“测试直接操作引脚”的旧用例改成可复用环境，或复核环境是否存在
“驱动与观察混在用例里”时使用。输入是真实实例层次、生成 DUT 的引脚/端口清单、
producer/consumer 合同，以及工程内已有的参考布局；不需要先有一套完整模型。

分层不是目的。它要解决三个具体问题：测试能否只描述事务；同一引脚是否只有一个
驱动者；观察是否每拍发生、比较是否有独立依据。只建目录而不约束这些行为，仍然是
旧环境。

## 先确认框架已经提供什么

本仓库的验证框架是 `uc-toffee`（导入名 `toffee`）。名称、锁定源码位置和已知缺口见
[项目工作流](../ucv4xs-workflow/SKILL.md#验证框架toffee)；这里只保留选型规则和能力归属。

**先查框架，再决定自己写。** 直接复用框架组件时，工程只需提供端口绑定、有效条件、
解码、参考模型和比较规则；自建一套 driver/monitor 会丢掉框架已有的接受事件、
丢拍报错和原生覆盖自动收集。

| 能力 | 框架已有 | 工程自己负责 |
|---|---|---|
| 引脚绑定与方向检查 | `Bundle` / `Bundle.bind` / `SignalDriver`（拒绝驱动输出） | 生成端口名、位宽、idle 值 |
| 单/多周期输入、重叠提交 | `SyncSingleCycleDriver` / `SyncMultiCycleDriver` / `AsyncDriver` | 具体接受条件与阶段划分 |
| 输出采样 | `SamplingMonitor`（`delivery=lossless/latest`，溢出报错，带 tick） | 有效条件、解码、快照类型 |
| 组件装配与事务检查 | `Agent` + `Scoreboard`（顺序/编号/固定延迟关联） | 参考模型、比较规则 |
| 功能覆盖 | `CoverGroupDef` / `CoverPointDef` / `CrossDef` | 覆盖点语义 |
| 原生行/分支覆盖收集 | `toffee run` + `NativeCollector` | RTL 闭包映射、报告口径 |
| 事务类型、合法域、oracle | 无 | 全部 |

只有框架组件无法表达本 DUT 的时序或观察语义时才自建，并在工程 `docs/` 写明：框架哪
一项不适用、自建版本保留了哪些行为、缺少哪些行为（例如是否返回接受事件、是否在丢拍
时报错、覆盖率是否仍被自动收集）。

## 推荐目录

目录职责、单文件/子包选择、README 与 schema 适用范围见
[testbench 目录规范](../../docs/reference/module-layout.md)。这里说明运行时的分层方法。
以 schema2 的一个工程一个 pytest 根、每个 DUT 在其 `testbenches/<dut>/` 内有明确的
agent/环境身份为例：

```text
suites/<group>/<suite>/
├── __init__.py              # 唯一导入命名空间及 ROOT，不创建 DUT
├── testbenches/<dut>/
│   ├── README.md             # 工具生成的规格、实现、用例、命令和问题入口
│   ├── transactions.py       # 或 transactions/；事务合法域、单位、身份
│   ├── env.py                # 或 env/，内部组织 agent、ports、driver、monitor
│   ├── checker.py / model.py # 或同名子包；独立 oracle/性质比较
│   ├── coverage.py           # 按需：行为覆盖
│   └── tests/                # 功能用例、自检、scenarios/ 场景复用
├── testbenches/shared/       # 真正跨 DUT 组件，同用上述六职责及独立 README
├── conftest.py               # 唯一 fixture / pytest 插件注册入口
├── tools/                    # 离线汇总、审计等工程命令（可无）
├── ucv.json                  # DUT 配方：真实 top、导出类、测试根
├── pytest.ini                # testpaths = testbenches；feature / rtl_defect / selftest 等标记
└── docs/                     # 责任边界、功能点、追溯、残余、证据
```

shared 与 DUT 同名职责同义，只有真正跨 DUT 复用的组件才进 shared；单 DUT 实现归所属
`testbenches/<dut>/`。双方根只放六类职责，不放 `agent/`、`conftest.py` 或 `pytest.ini`；
tests 为目录，其余按需用文件或同名包，不创建空壳。同一参数化实现的多个实例可以共用
代码、规格和参数化 fixture，通过配方与 `workspace.json` 的 `duts.<name>.testbench`
明确身份。父模块组合用例属于父 DUT，使用各子 agent 或父 agent，不复制子模块的编码逻辑。

`shared` 是保留名，不登记为 DUT，没有独立 top 或本地原生库。共享实现不得反向 import
具体 DUT 或工程 tools；shared/tests 可检查集成引用。通用加载器、绑定、驱动、采样与插件
归 shared/env，共同事务、独立参考计算、比较、覆盖分别归 transactions/model/checker/coverage。
DUT 专用参数生成放其 tests/插件，通用插件放 shared/env/pytest_plugins，由工程唯一 conftest
注册；离线审计与汇总命令放 tools。

工程根自身是 `suites.<group>.<suite>` 包。BPU 使用
`suites.frontend.bpu.testbenches.mbtb`；LSQ 示例为
`from suites.memblock.lsq.testbenches.deq.env.agent import PsqAgent`。不保留 *verify 包名兼容别名，
不使用 import common 或 import deq。运行器显式提供仓库根导入路径；可编辑安装后
也可从其他 cwd 导入。ROOT 从工程 __init__.py 解析，不按移动后的目录深度猜 parents[n]。
当前六个工程的 legacy_pins.py 只是兼容字段，仍需事务适配；不以去掉 common 证明
语义完成。具体迁移见[命名空间重构](../../docs/lessons/suite-namespace-refactor-20261031.md)。

## 各层职责与禁止项

| 层 | 职责 | 不应做 |
|---|---|---|
| `harness` | 装载原生 DUT、推进时钟、登记引脚所有权、运行每拍安全网 | 判断功能对错；安全网只保护合同不变量 |
| `transaction` | 在进入环境前拒绝非法编码、缺字段、越界和互斥冲突 | 用 RTL 内部状态反推期望值 |
| `bundle/ports` | 把逻辑名映射到生成端口；缺端口立即报错 | 在测试里拼物理字符串或默认补零 |
| `driver` | 声明并占用引脚；按协议发射、保持、撤销、重试 | 读 DUT 输出决定下一个请求 |
| `monitor` | 按合同在指定边沿或组合稳定点采样公开输出，生成不可变事务 | 驱动任何引脚 |
| `checker` | 用独立 oracle、性质或账本比较 | 把“观测到了”当作“值正确” |
| `agent` | 装配上述对象，提供测试可读的事务方法 | 让测试直接 `.set()` 或访问 `.dut` |
| `tests` | 组织场景、断言事务和不变量 | 复制编码逻辑、直接读写引脚 |

## 操作步骤

1. **先定事务和身份。** 为每个 producer 写请求类型，为每个可观察输出写事务类型；
   标明地址/数据单位、字段宽度、有效条件、身份（索引、UID、指针 flag）和完成语义。
   合法域校验放在构造器，非法输入在 fixture 边界失败。
2. **建引脚组。** 按通道分组，而不是按测试用例分组。只映射当前 DUT 实际存在的
   端口；生成器裁掉的常量端口单独登记，不能静默当 0。
3. **先写 driver 的发射与撤销。** 请求的“保持一拍、撤销、再走一拍”由 driver 统一，
   测试不应自己数边沿。对组合型请求要撤销整个 payload；只清 `valid` 可能留下
   下一拍仍生效的 override/flag。
4. **再写 monitor。** 采样函数返回 `None` 表示本拍无有效事务；有 valid 时再解码
   payload。需要“同一拍组合观察”或负对照时，提供显式解码函数，不让测试绕过
   monitor 直接读端口。
5. **最后接 checker。** 优先用独立 oracle 或可证明性质；内部信号只用于身份、
   指针不变量和存储证据，不作为 payload 期望来源。checker 要能在错误期望下失败。
6. **agent 收口。** agent 只暴露事务方法、快照读取和必要的精确对齐接口
   （如 `drive_*` / `finish_*`、`resolve_cycle`）。测试中出现物理引脚名、`.pins`、
   `.dut`，就说明抽象漏了。
7. **fixture 在工程 conftest.py 显式注册。** 每 DUT 一个 function-scoped fixture，负责
   DUT、Execution、agent 和覆盖率文件；不要在每个子目录复制同名 fixture。子目录
   需要特殊构造时，应在 agent 上加方法，而不是另起一套驱动。
   这是本仓库的默认，不是 pytest 的合法性限制。多个 DUT 可以由参数化工厂覆盖，单个
   DUT 也可能需要合法的不同配置。不要用 fixture 函数数量推断 DUT 覆盖数，不要为了
   保留短名字引入按文件路径隐式选择不同模型的 dispatcher；优先显式命名/参数化。
8. **加自检与负对照。** 至少包括：重复 claim 同一引脚必须报错；缺端口/未知键必须
   报错；同一观察路径在错误期望下必须失败；oracle 对错序、错 payload、错范围的
   拒绝。自检标 `selftest`，不计硬件功能 credit。

## 产出

- 目录树与每层职责表；
- 一份事务到引脚、引脚到事务的映射；
- 引脚所有权清单和 claim 冲突自检；
- driver 的发射/保持/撤销时序说明；
- monitor 的采样点、有效条件和历史窗口；
- checker 的独立答案来源与负对照 nodeid；
- 测试中“无直接引脚访问”的检查命令和结果。

## 如何验收

- 所属 testbench 的 `tests/` 功能用例不再出现 `.pins`、`.dut`、物理引脚字符串或驱动编码调用；
  测试只调用 agent 方法并断言事务。编码/绑定的自检可以单独保留，但标 `selftest`，
   不计硬件功能 credit。可用如下命令核对（命中应为 0；自检文件单独说明）：

  ```sh
   # 在 schema2 工程根运行，替换 <testbench> 为实际实现名
   grep -rnE '\.(pins|dut)\.|io_[A-Za-z]' testbenches/<testbench>/tests --include='*.py'
  ```
  此 grep 只能发现部分泄漏；P.p_*、P.io(...) 仍然是引脚级耦合，不能靠改名绕过。
  当前静态审计用 `--require-transaction-boundary` 单列它们；零命中也不能替代采样、
  所有权、独立 oracle 与正负对照的语义验收。
- 逻辑字段字典也不能直接交给用例中的 `agent.*_driver.set/send`；直接读 `agent.ports`、
  修改 `agent.model` 或调用私有编码/边沿 helper 仍是基础设施耦合。静态工具现单列
  `owner infrastructure`，与旧 pin/signal 数字分开；独立 oracle 和普通事务字段仍允许。
  不能把这些调用改个名、藏进转发壳或改标 selftest 来取绿，见
  [门禁漏检与真实债务](../../docs/history/transaction-goal-component-boundary-20261102.json)。
- 零沿persistent level源也必须接入SDK的真实signal claim，与单/多周期driver共用所有权；
  “不推进时钟”不是绕过唯一驱动的理由。set()只表示驱动电平，不表示已接受，见
  [ICache level所有权证据](../../docs/history/transaction-goal-icache-level-ownership-20261102.json)。
- 同一引脚被两个 driver 声明时，fixture 边界立即失败，而不是后写覆盖前写。
- 把某个期望字段故意改错，至少一条用例失败；只有“观测到 valid”不算检查。
- 关闭 monitor 后，依赖它的功能用例必须失败或缺少输入，不能静默通过。
- 从一条 PASS 能追到事务、driver 调用、monitor 采样和 checker 比较；从一条 FAIL
  能回到具体层，而不是只看到 pytest 栈。
- 新增 DUT 时登记真实 top、资源与测试选择，并接入独立子包或明确的共享参数化实现；
  不改其他 DUT 的编码逻辑，不为每个生成实例复制子包和 fixture。

## 常见坑

- **只清 valid。** RTL 可能仍用 override/flag 位更新指针；撤销整个 payload。
- **寄存器化输入。** 某些来源（如 IFU resolve）比同拍后端 lane 晚一拍。需要精确
  对齐时，用“保持上一拍报告 + 下一拍观察”的方法，不能假设所有来源同拍。
- **monitor 快照被下一次采样覆盖。** 测试应在边沿后立即读取，或用 `take()` 消费；
  长序列用有界历史，不保存无限日志。
- **consumer ready 互相覆盖。** 多通道 ready 用合并语义，设置一个通道时不能把其他
  通道意外清 0；否则会出现“预取/取指停住但用例仍绿”。
- **内部信号当期望。** 内部指针可用于身份和不变量；payload 期望仍应来自事务参数、
  规范或独立模型。
- **fixture 放错层级。** 子目录 `conftest.py` 的 fixture 对兄弟目录不可见；需要跨
  子包共享时放到 pytest 根。
- **收集前切 cwd。** 不在 pytest_configure 中将控制进程切入 scratch；xdist worker
  会继承该目录，无显式路径时可能根本不使用工程 testpaths。用执行期 session/function
  fixture 隔离原生 dumpfile，并核验无显式选择的单/多 worker collection、执行与 cwd 恢复。
- **只扫 .dut 或 io_*。** raw_dut、通道字典的 .Set/.U、xport 等仍是原生耦合。
  信号操作应单列检查；普通不可变事务的 .value 字段不应被机械误判为引脚。
- **fixture 名相同但模型随路径变化。** 不根据 request.node.path 或目录名切换参考模型。
  为不同合同注册显式 fixture 名，让用例签名声明依赖；搬动用例后模型语义应保持。
  验收同时比较有序 nodeid、原生判定及在任意目录的 fixture 注册，不只比较收集数。

## 案例

- FTQ 的三个 DUT（`ResolveQueue`、`CommitQueue`、`Ftq`）采用同样的事务分层，测试不再直接
  操作引脚；结构与约束见
  [FTQ 验证包结构](../../suites/frontend/ftq/docs/spec/verification/architecture.md)。
- BPU 的 RAS/UBTB 等模块提供同构的 `agent/bundle/driver/monitor/checker` 参考实现，
  见 `suites/frontend/bpu/testbenches/ras/` 与 `suites/frontend/bpu/testbenches/ubtb/`。
- 引脚绑定、缺端口默认 0、复位随机化等“静默变绿”案例见
  [IFU 环境完整性案例](../../docs/lessons/ifu-harness-integrity-20261029.md)。

相关方法：[合法激励](legal-stimulus.md)、[独立 oracle](independent-oracle.md)、
[checker 与运行时](checker-and-runtime.md)、[实现与追溯](../design/traceability-and-implementation.md)。
