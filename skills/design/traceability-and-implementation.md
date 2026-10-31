# 如何把功能点实现为可运行、可检错的测试

## 何时使用、准备什么

定义功能点后、开发环境前，或复核“写了用例却没查到错误”时使用。输入是需求来源、DUT 合同、行为等价类和可用观察点。

## 怎么做

1. **明确可观察承诺。** 将每个功能点拆为激励前提、状态历史、结果、副作用、完成条件；注明哪些字段有效、哪些未定义。
2. **独立推导答案。** 用适用版本的规范、已确认设计合同、固定配置或独立性质推导 expected。可以读 RTL 确认接口/时序，但不能因实现如此就把它写成正确答案。ISA 模型也要核实适用版本与语义，不是无条件 golden。
3. **画最小执行路径。** 确定 fixture、producer/内存代理、driver、monitor、scoreboard 的职责和采样点；先做单事务，再加入目标历史/并发。正常用例接真实 RTL，不以模型自测冒充 DUT。目录与分层落位见 [验证包 driver/monitor 分层](../execution/package-layout.md)。
4. **先列字段再接比较器。** 每项观察字段写单位、身份来源、有效条件和比较规则；不比较的字段写依据与影响。只有模型计算、没有观测/比较的字段仍是缺口。
5. **设计成对控制。** 合法行为应通过；选择能破坏该承诺的代表性错误变体，使检查失败。分别标清 expected 注错、观测注错、环境故障或 RTL mutant，不混成一种证明。
6. **定义完成性。** 需要最终接受/完成的用例设置目标、UID 账本、重试与有界收尾。允许拒绝或取消的场景按合同结清义务；不能机械要求每笔 offered 都完成。
7. **加入实际执行与持续检查。** 对账定义、pytest collection、选择器和实际结果。先小范围验证，再接入适用回归；未选入的探针与 checker 自检单列。不得声称尚未接入的 CI/门禁已生效。
8. **反查报告。** 从结论找到 nodeid、断言、输入和当轮证据；失败或缺口回填需求/实现计划。

## 产出：一条可审计的实现记录

```yaml
requirement_id: <需求及来源版本/条款>
class_id: <等价类/组合>
dut_and_legal_precondition: <责任与准入>
stimulus_and_history: <驱动入口与构造序列>
oracle_and_independence: <答案/性质及独立来源>
observations_and_assertions: <字段、条件、比较器位置>
completion_obligation: <接受/完成/合法拒绝或取消>
legal_control: <应通过的场景>
error_control_and_layer: <应失败的变体与注入层>
collection_and_run: <nodeid、实际选择及结果>
continuous_check: <当前入口，未接入就写待实施>
evidence_and_residual: <版本/结果位置、未证明范围>
```

## 如何验收

至少沿一条高风险需求走完“来源 → 合法激励 → 真实 DUT → 独立答案 → 实际比较 → 正负对照 → 运行证据”；反向从一条 PASS 也能回到需求。缺一环不得按已完成填写。

执行方法分别见 [合法激励](../execution/legal-stimulus.md)、[独立 oracle](../execution/independent-oracle.md)、[checker 与运行时](../execution/checker-and-runtime.md)。历史案例见 [跨模块漏检总结](../../docs/lessons/false-negatives-20261026.md)。
