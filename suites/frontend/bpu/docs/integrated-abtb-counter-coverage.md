# 集成 ABTB 的物理计数器功能覆盖

2026-10-10 01:44 北京时间：生产组件及接入已完成资格验证；正式全量报告尚未刷新。
这项工作补全覆盖定义，不把已有 PASS 重复登记为新功能点，也不提前合入隔离行增益。

## 为什么需要补充

完整比较 1024 个 counter，只能证明已执行的更新和未选状态正确，不能证明每个
物理 cell 的每条路径都被激活。原自然循环的两个用例都通过，但按新完整矩阵
各只命中 10/12288 个路径 bin。旧 99.2058% 是旧覆盖组定义下的均值。

独立 ABTB 的 100% 行覆盖也不能替代集成 BPU；二者的输入、反馈来源和时序不同。

## 生产分层

- 静态 Bundle 和 `@on()` monitor 仍负责观测；memory-direct、时钟相位和 IO 细节不进入测试。
- 原 `IntegratedChecks` 继续检查完整 PHR、公开事务关联、S1→S3 metadata、counter 和 PLRU。
- `CounterCoverage.collect()` 独立从完整两相位观测重放 metadata、counter、T2 touch 和 PLRU。
- `check_integrated_case()` 在两个覆盖收集器都重放成功之后才发布功能覆盖文件。

正常测试仍然只表达场景意图：

```python
await check_integrated_case(agent, output, kind='natural', bank=0)
```

这里的 `bank` 是原场景的 PC bank 参数，不能直接当作实际 ABTB bank。此次
两个真实用例观测到的 ABTB 物理 bank 分别为 0、2；bin 身份取自已比较的真实元数据。

## 三个覆盖组

| 覆盖组 | 完整分母 | 采样条件 |
|---|---:|---|
| 物理 counter 路径 | 1024 × 12 = 12288 | T1 更新执行，下一拍完整状态比较通过 |
| 写响应初始化为 2 | 1024 | 真实 reset-counter write response，下一拍比较通过 |
| 同 cell reset 优先级 | 1024 × 12 = 12288 | 真实 T1 与 reset write 同 cell 重叠，下一拍结果为 reset |

每 cell 的 12 个更新路径为：

- 同位置取走：`inc0_1`、`inc1_2`、`inc2_3`、`inc3_3`。
- 最终不取：`dec3_2`、`dec2_1`、`dec1_0`、`dec0_0`。
- 后项取走：相同四个 decrement/hold，但保留独立原因。

reset 优先级的 12 类为三种更新原因 × 四种原始 counter 值。reset 覆盖掉的
训练更新只记入优先级组，不冒充已经执行的普通增减。低/高保持必须观察到真实
`dec0_0`/`inc3_3`，不能靠命中 guard 行推断。未证实不可达的 bin 保留，后续需
审查实际可达性，不能为了覆盖数字而删除。

实现使用“物理 cell × 已合并的合法路径标签”交叉；不将增减类型与互斥原因
分别做笛卡尔积。cell/path 边际权重为 0，完整交叉权重为 1，避免边际命中抬高
矩阵覆盖率。schema 为不可变缓存，各用例的计数和来源仍独立。

## 证据门禁

收集器要求从真实 reset 开始、连续交替观测，比较全部 counter、所有 PLRU
状态/shadow/victim，以及完整捕获 metadata、fastTrain 和 T2 使能/身份。
待确认事件只在下一 rising 的完整状态通过之后入账；缺少最后响应不计入。
整次重放后才提交计数，晚期失败不会留下部分覆盖。缓存的 `confirmed_transitions`、
alias 清单、期望结果、用例通过标志本身都不是采样依据。

它不声称独立推导 ABTB SRAM 分配或 write-response 生成，也不替代上层 PHR、
SRAM、输入资格和 FTQ 检查。这些边界在 summary 中明确保留。

## 本轮验证结果

- 新增 45 项 collector 契约及 1 项双报告原子发布回归；相关完整模型回归 1389 PASS。
- 原生产测试在两个独立 pytest worker 中实际 2 PASS，并完整重放新观测。
- 独立标准库检查器核对两份 FC 的完整分母、边际/交叉计数、权重和 provenance，
  拒绝 16 个真实导出数据故障；旧 normal raw/FC/四报告身份均未变。
- 两份正式归档自然循环只读重放通过，各 10 个路径 bin。
- 两份已完整审计的 final-NT 归档只读重放通过：bank0/set0 为 32 个路径，
  bank1/set0 为 18 个路径，复现非零 bank 低 way 缺口；这不是新 DUT 或正式增益。
- 当前完整 pytest 收集为 8254 项；正式功能点仍为 286，未凭 collector 增加 PASS。

证据见 [生产资格验证](../results/coverage-bpu-integrated-counter-production-qualification-v1-readonly.json)、
[独立导出审查](../results/coverage-bpu-integrated-counter-export-review-v1-readonly.json) 和
[final-NT 重放](../results/coverage-bpu-integrated-counter-final-NT-production-replay-v1-readonly.json)。

后续仍需迁入已资格验证的五 alias/四节点场景与完整 index/write/SRAM 组件，
登记真实新功能需求，再保护旧完整证据、正常全量刷新并审计。全部物理 way、
两种负向原因、保持、真实重叠、deep SC-used、full dirty overwrite、完整 FTQ 和
既有 7 strict XFAIL 的原完整范围不因本轮组件完成而缩小。
