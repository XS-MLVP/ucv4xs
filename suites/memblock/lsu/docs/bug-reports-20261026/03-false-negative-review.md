# 漏报复核：为什么518项全绿仍不能说明没有Bug

**结论：确认1项被原模型隐藏的 RTL 性能缺陷，以及多类验证侧漏检风险；已补强可定位路径并重跑。** 不把验证代码问题冒充额外 RTL Bug，不把38项故障对照当作穷尽 mutation coverage。

## 1. 同源预期隐藏了性能事件错误

旧 `suites/memblock/lsu/load_s2/env.py:701–703` 将 `is_hw_prefetch && cause[6]` 直接作为 perf3 预期，因而与 RTL 一样永远期望0。旧 `docs/gaps/load_s2.json` 又把它列为结构死计数器，`defect_claim=false`。这证明实现等价，不证明命名的硬件预取 miss 事件语义正确。

新规范测试 `tests/load_s2/test_spec_prefetch_miss.py` 直接检查公开输出，命中对照通过、miss反例失败。**规范失败现已纳入默认 tests，不放在一个全绿回归之外。** 详见 `01-LSU-HWPF-MISS-001.md`。原实现等价模型保留并注明用途；没有把它改得也报错然后宣称已修RTL。

## 2. 三处恒真断言

复核开始前的源码与行号完整保存于 `review/failure_recheck_20261026/before/` 和 `inventory.json`。

| 原始位置 | 原断言 | 修正 |
|---|---|---|
| `tests/new_load_unit/test_new_load_unit.py:347` | `... if False else True`，且用的是不存在的 RAW lqIdx 字段 | 明确检查实际 RAW 的 SQ索引及两段flag |
| `tests/new_store_unit/test_new_store_unit.py:226` | `paddr == PADDR or True` | 在有效 SQ 地址拍比较实际 paddr，并检查 valid |
| `tests/new_store_unit/test_new_store_unit.py:388` | `stout_valid == 0 or True` | 对 debug trigger 异常的 CBO，检查必须写回且 trigger 为 DEBUG |

原语句不会因为比较失败而报错，属于确定的**局部断言无效**。但相邻 env 可能已经检查相同字段，因此不声称这三处各自都曾让真实 RTL Bug逃过整套测试。更不能简单说“修了3个 RTL Bug”。

## 3. S1 尾段身份缺失有旧/新检查器故障对照

### 正常应该怎样

未对齐 Load 注入尾段时，除地址、mask及明示变换字段外，ROB/SQ/uop身份须随原请求传递；不能只有地址正确，所属指令却换了。

### 原问题

旧 `LoadS1Env` 只把 tail.valid/vaddr/fullva/mask 加入检查表，其余公开尾段字段未统一检查。新增检查枚举真实 `io_unalignTail_bits_*`，逐字段比较应转发值；未改变原生S1或内部MemTrigger。

### 怎样证明补强有效

- `test_old_tail_checker_real_counterexample`：装入本轮开始前的旧env，在**Python读取边界**翻转 tail ROB bit，旧检查仍通过。
- `test_old_tail_checker_misses_rob_corruption_new_checker_rejects`：同类错误经新检查明确触发 `tail.uop_robIdx_value` AssertionError。
- 同时检查真实DUT原引脚仍为42，说明这是**检查器灵敏度实验**，不是“真实RTL已经输出错误”的证据。
- `test_tail_all_forwarded_fields_have_raw_observations` 以固定种子16组身份检查真实公开输出。

新旧结果分别证明“以前存在漏检路径”和“该路径现在能拦住此类错误”；不证明所有S1字段/所有变异已穷尽。

## 4. 输入拼写可让声称的情形根本没到达

父块驱动读取嵌套键，例如 `rarResp`、`bypass1/2`、`sq`、`ldld`；把引脚名风格字符串直接塞在顶层可能被静默忽略。

现增加 `validate_input_keys`：未知字典键与列表形状会在走钟前报错；补齐真实 `dcache.resp.bits.data` 和 `bypass2.bits.data` 的合法schema，不把支持的数据字段误拒绝。负对照验证三种典型错误键都会被拒绝。

旧测试还有一个声称制造 hardware-prefetch replay 的 `accessType_pftType` 键，但该replay接口根本没有此字段；`entrance=0x20` 是vectorIssue码，不是能凭空创造的硬件预取入口。现删除这段无效刺激，改为检查父块真实软件指令预取输出与 noQuery 导致的训练无效。不再声称覆盖了不存在的父块硬件预取输入。

**限制**：schema只验证形状和键名，不证明每个随机组合满足上游协议及微架构合法域。`random_inputs` 中逐字段独立随机应解释为接口/位级鲁棒性检查，不能全数称为“合法事务随机”。

## 5. 跨16B测试原来可能没测到合并

旧datapath定向用例在head与tail之间插入bubble，数据模式也没有提供足够的高位区分，最后主要检查参考模型的valid。

现将tail S1与head S2安排同拍，给head高字节非零模式，直接检查真实输出：

```text
offset=13: expected = (head >> 104 | tail << 24) mod 2^128
offset=0:  实现定义的零偏移头段保持，不额外左移尾段
```

另有6种offset的独立字节列表预期、父块aligned/crossing的精确单次RF写回，以及S3异常来自合并head的公开引脚检查。不会因某个参考返回值等于自己就算通过。

## 6. 19 DUT 的最低限度灵敏度检查

`review/failure_recheck_20261026/test_checker_sensitivity.py` 对每个DUT选一条原有测试：

- 19个baseline必须通过；
- 19个readback-fault必须被检查器拒绝，合计38项通过；
- 故障只加在Python读数，不修改RTL，不替换硬件子块；
- `pytest.raises(AssertionError)` 只用于验证“故障应被检查器拒绝”的元测试，**没有包住真实性能反例**。

最终回归38项再次通过，但这不等于对每个端口、每个时序及每种RTL变异都做过mutation测试。

## 7. 初始化和功能覆盖不能被过度解读

父块 `prime()` 的 `compare=False` 是已存在的初始化盲区。本轮补充 `test_first_load_after_reset_without_unchecked_prime`，不运行prime、不使用参考模型预期，核对reset后首条Load的真实RF/ROB/LQ有效位、身份和数据；该测试通过。**只补证这条首访问序列，不声称初始化所有行为已覆盖。**

大量功能bin由测试显式 `sample_case()`，`observe()`是空实现。全绿报告的100%只说明被声明的bin都被采样，不是自动独立证明每个bin均 reached 且 checked。新增直接断言和故障对照增强了具体路径，但本轮**没有完成全工程逐bin的独立 reached/checked 重构**；该限制明确保留，撤回旧的无条件关闭声明。

## 8. 修正后的实际结果

`results/failure-recheck-final-03/` 当时为 **582 PASS / 1普通FAIL**；上游核查后当前为 `upstream-review-regression-02`：**582 PASS / 7普通FAIL**。真正的性能缺陷仍能被默认测试检出；修正的检查器、独立公开引脚检查和19组敏感性对照通过。

以上是有证据的补强，不是“从此不存在任何假阴性”的保证。未恢复的历史逐节点失败、随机合法域、逐bin reached/checked及初始化全状态证明仍是明确的证据边界。
