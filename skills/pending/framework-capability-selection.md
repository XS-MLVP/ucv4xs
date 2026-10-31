---
name: framework-capability-selection
description: 在编写 driver、monitor、agent、checker 前决定复用 toffee 的哪个组件、工程侧还欠什么，以及自建组件必须记录的差异。适用于新工程或旧工程重构时避免重复实现框架能力。
---

# 框架能力选型（待审核）

## 何时使用、准备什么

- 新建验证包，准备写 driver/monitor/agent；
- 旧工程里出现自己的时钟推进、采样队列、scoreboard 或接受事件；
- 需要判断某个能力（UNCERTAIN、覆盖、原生收集）是否应由框架负责；
- 想给框架缺口补工程侧组件，但担心“自建版本被当成框架等价物”。

先确认当前锁定源码和文档，而不是凭记忆：

```sh
sed -n 1,80p docs/lessons/build-and-toolchain.md
ls .tools/sources/toffee/docs/zh/guides
sed -n 1,80p .tools/sources/toffee/docs/zh/guides/agents-and-reference-models.md
.venv/bin/python -c "import toffee; print([n for n in dir(toffee) if n[0].isupper()])"
```

## 先查框架，再决定自建

| 需求 | 优先使用 | 工程侧仍负责 | 不应重复实现 |
|---|---|---|---|
| 引脚绑定、方向检查 | `Bundle` / `Bundle.bind` / `SignalDriver` | 生成端口名、位宽、idle 值 | 自己遍历 XData 并猜方向 |
| 单/多周期输入 | `SyncSingleCycleDriver` / `AsyncSingleCycleDriver` / `SyncMultiCycleDriver` / `AsyncDriver` | 接受条件、阶段、撤销 | 无行为差异说明地重造调度器 |
| 输出采样 | `SamplingMonitor` / `ReadyValidMonitor` | 有效条件、解码、快照 | 自己维护无界队列 |
| 事务关联与响应检查 | `Agent` + `Scoreboard` | 参考模型、key、延迟、比较 | 自己实现 expected 队列和超时 |
| 功能覆盖 | `CoverGroupDef` / `CoverPointDef` / `CrossDef` | 覆盖点语义 | 手写 JSON 计数器 |
| 原生行/分支覆盖 | `toffee run` + 原生 collector | 闭包映射、报告口径 | 伪造覆盖率 receipt |
| UNCERTAIN | `@pytest.mark.uncertain(reason=..., reference=...)` | 证据和残余登记 | 把缺证据写成 PASS |

## 选型步骤

1. **写事务和身份**：请求/响应类型、字段单位、有效条件、完成语义、合法域。
2. **画接口表**：producer → driver；DUT 输出 → monitor；checker 的独立答案来源。
3. **逐项对照上表**：能直接用框架组件的，不新增同名包装；需要组合多个 driver 或
   多接口顺序时，手写 agent 装配是合理的，但要在工程 `docs/` 写明为什么
   `toffee.Agent` 的单 driver 模型不适用。
4. **自建组件必须写差异**：框架哪一项不适用、保留了哪些行为（接受事件、丢拍报错、
   覆盖率自动收集）、缺少哪些行为、关闭条件。
5. **用负对照验收**：错误期望必须失败；缺端口/未知键必须失败；重复 claim 必须失败；
   monitor 关闭后依赖它的场景不能静默通过。

## 本仓库的落地例子

- BPU：`drivers/signal.py` 对 Toffee 驱动做薄适配；`CycleMonitor` 包装
  `SamplingMonitor` 以提供不可变快照和 observer；各 DUT 自己提供事务、参考模型和
  checker。多接口 agent 是手写装配，因为单个 `toffee.Agent` 只覆盖一个主 driver。
- FTQ：`harness` 负责 DUT/时钟/引脚所有权，`agent` 只暴露事务；训练输出和
  commit/redirect 由 monitor 解码，checker 用独立 oracle。
- ICache：fixture 收敛到 pytest 根；`WayLookupAgent` 封装 flush 与同拍写探针，
  测试不再直接操作 level driver。

## 验收与边界

- `pytest --collect-only` 能导入所有 fixture；
- 至少一个纯模型目录全 PASS，且至少一条负对照失败；
- 原生用例的构建、冒烟、功能判定、覆盖分别陈述；没有重建就写“未验证”；
- 自建组件出现在报告里时，注明它代替了哪些框架断言、遗漏什么。

相关方法：[验证包 driver/monitor 分层](../execution/package-layout.md)、
[独立 oracle](../execution/independent-oracle.md)、
[checker 与运行时](../execution/checker-and-runtime.md)。
