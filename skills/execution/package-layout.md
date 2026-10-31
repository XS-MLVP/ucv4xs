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

以一个工程一个 pytest 根、每个 DUT 一个 agent 为默认：

```text
suites/<group>/<suite>/
├── __init__.py              # 唯一导入命名空间及 ROOT，不创建 DUT
├── native.py / harness.py   # 小工程的原生资源边界；复杂时用 runtime/
├── drivers/                 # 仅真正跨 DUT 的共享驱动机制（可无）
├── monitors/                # 仅真正跨 DUT 的共享采样机制（可无）
├── pytest_plugins/          # 项目级插件；小工程可用 fixtures.py（可无）
├── <dut>/
│   ├── agent.py             # 或 agent/main.py，按复杂度选，不强制空角色目录
│   ├── ports.py             # 或 bundle/ports.py：逻辑名到真实端口
│   ├── driver.py            # 事务编码、发射、保持与撤销
│   ├── monitor.py           # 合同采样与不可变事务解码
│   ├── checker.py / model.py # 独立 oracle/性质比较，不产生激励
│   └── types.py             # 事务合法域、单位、身份
├── tests/
│   ├── conftest.py           # 每 DUT 一个 agent fixture，子目录共享
│   └── <dut>/test_*.py       # 只调用 agent 事务 API
├── tools/                    # 回归、覆盖率合并、追溯等工程入口（可无）
├── ucv.json                  # DUT 配方：真实 top、导出类、测试根
├── pytest.ini                # feature / rtl_defect / selftest 等标记
└── docs/                     # 责任边界、功能点、追溯、残余、证据
```

不创建泛化的 common 包；共享机制按职责命名，没有共享行为就不要造目录。多 DUT 层次每个真实实例一个
`<dut>/` 子包，父模块组合用例只使用各子 agent 或父 agent，不复制子模块的编码逻辑。

工程根自身是 `suites.<group>.<suite>` 包，例如
`from suites.memblock.lsq.deq.agent import PsqAgent`。不保留 *verify 包名兼容别名，
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
7. **fixture 集中在 pytest 根。** 每 DUT 一个 function-scoped fixture，负责
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

- `tests/` 下的功能用例不再出现 `.pins`、`.dut`、物理引脚字符串或驱动编码调用；
  测试只调用 agent 方法并断言事务。编码/绑定的自检可以单独保留，但标 `selftest`，
  不计硬件功能 credit。可用如下命令核对（命中应为 0；自检文件单独说明）：

  ```sh
  grep -rnE '\.(pins|dut)\.|io_[A-Za-z]' tests --include='*.py'
  ```
  此 grep 只能发现部分泄漏；P.p_*、P.io(...) 仍然是引脚级耦合，不能靠改名绕过。
  当前静态审计用 `--require-transaction-boundary` 单列它们；零命中也不能替代采样、
  所有权、独立 oracle 与正负对照的语义验收。
- 同一引脚被两个 driver 声明时，fixture 边界立即失败，而不是后写覆盖前写。
- 把某个期望字段故意改错，至少一条用例失败；只有“观测到 valid”不算检查。
- 关闭 monitor 后，依赖它的功能用例必须失败或缺少输入，不能静默通过。
- 从一条 PASS 能追到事务、driver 调用、monitor 采样和 checker 比较；从一条 FAIL
  能回到具体层，而不是只看到 pytest 栈。
- 新增 DUT 时只增加一个 `<dut>/` 子包和 fixture，不改其他 DUT 的编码逻辑。

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

## 案例

- FTQ 的三个 DUT（`ResolveQueue`、`CommitQueue`、`Ftq`）按本布局落地，测试不再直接
  操作引脚；结构与约束见
  [FTQ 验证包结构](../../suites/frontend/ftq/docs/architecture.md)。
- BPU 的 RAS/UBTB 等模块提供同构的 `agent/bundle/driver/monitor/checker` 参考实现，
  见 `suites/frontend/bpu/ras/` 与 `suites/frontend/bpu/ubtb/`。
- 引脚绑定、缺端口默认 0、复位随机化等“静默变绿”案例见
  [IFU 环境完整性案例](../../docs/lessons/ifu-harness-integrity-20261029.md)。

相关方法：[合法激励](legal-stimulus.md)、[独立 oracle](independent-oracle.md)、
[checker 与运行时](checker-and-runtime.md)、[实现与追溯](../design/traceability-and-implementation.md)。
