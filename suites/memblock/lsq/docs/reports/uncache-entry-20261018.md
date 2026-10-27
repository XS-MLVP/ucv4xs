# UncacheEntry全16个ID：生命周期、路由与取消的实际验证闭环

**结论：16个实际特化top全部完成独立UT和覆盖迭代，384/384 PASS，各自106/106插桩行；ID0语义75/75、ID1～15各77/77 checked。** 未修改原始Chisel或RTL，未用单一ID结果推断其他ID；此结论不代表LoadQueueUncache、LoadQueue或LSQ组合通过。

## 1. 功能合同和实际变体

`docs/contracts/uncache-entry.md` 在用例前定义14类人类可读微架构行为：所有权、MMIO/NC发起、请求保持、mask半部、mid/sid、回包、唤醒、数据消费、异常报告、各阶段取消、ROB年龄、重用、reset和空闲。

每个ID独立提取原样单文件、Picker导出、实例化走钟，再使用xreactor被动采样运行。完整构建报告分别位于 `results/builds/20261018T051833889230Z-uncache_entry_0/` 至 `20261018T052247749623Z-uncache_entry_15/`，精确映射见 `manifest/duts.json`。来源为开源固定基线，未使用XiangShan-internal。

接口差异并未抹平：ID0两类wakeup ready常量化删除，按实际恒ready观察；ID1～15保留背压，分别真实驱动检查。所有top都没有req.ready、uncache请求ID输出、response ID输入或response ready输出，未伪造这些端口。ID特化通过完整7位mid正反例及slaveId实际输出检验；父级sid→response路由仍待真实父块验证。

## 2. 首轮、逐行分类、补例重跑

| 运行 | 结果 | 每ID本体DA行 | 每ID语义checked |
|---|---|---|---|
| `entry-initial-01` | 48 PASS（每ID3例） | 100/106 = 94.34% | 17/75或17/77 |
| `entry-directed-01` | 38 PASS / 4 FAIL，294未选 | 保留原始证据 | 刺激/人工断言的former默认值标签错误，非DUT/参考不一致 |
| `entry-directed-02` | 42 PASS，294未选 | ID0/15的定向诊断，不作为最终家族结果 | 显式区分former/latter后重跑 |
| `entry-expanded-01` | **384 PASS（每ID24例）** | **106/106 = 100%** | **ID0 75/75；其余77/77** |

首轮每top的6条缺口逐条定位为：

| 原始路径 | 每top缺口 | 分类与补例 |
|---|---:|---|
| 保存请求/等待ROB许可时的取消判断和回空闲赋值 | 2 | 既有UE-FLUSH/AGE/REUSE缺少该阶段；命中/不命中redirect、年龄边界、公开flush及新身份正常完成 |
| 总线未接受时的取消判断和回空闲赋值 | 2 | 既有UE-FLUSH/REQ/REUSE缺少该阶段；总线背压下取消、当拍抑制请求、安全释放和重用 |
| wakeup阶段的取消判断和回空闲赋值 | 2 | 既有UE-FLUSH/WAKE/REUSE缺少该阶段；当前redirect/ready竞争、后续无数据消费及重用 |

ID0对应252/253、263/264、273/274行，其余ID相同路径整体偏移2行。16份共96条，全部保留并补例，不排除可达行。原始清单 `results/entry-initial-01/line-audit.json` 与人工映射 `line-audit-mapped.json` 分别保存。

首轮高行覆盖仍漏掉大量功能，补例没有停在上述6行：覆盖每ID全部128种mid（1正、127反）、全部16种sid、mask两半的16个单字节位置、64个单bit数据、四种错误组合、8个输入异常位、ROB许可寄存相位和年龄、五个阶段的取消及reset、三处背压和完整重用。功能点继续用微架构行为描述，SID/byte等只作为相应行为的情况枚举。

## 3. 关键实际检查

- **MMIO/NC差异**：NC在ROB尚未许可时发起；MMIO保持等待；pendingPtr改变先经过一级寄存，再允许发出请求。ROB同entry former/latter、159→160回绕及flushSelf/After均有正反例。
- **背压与数据**：总线请求保持8拍；ID1～15的wakeup在阻塞6拍时不提前输出数据；消费者阻塞8拍保持LQ、paddr、64位data和两个错误位，非选择通道ready不推进事务。ID0没有背压端口的两点明确不入其分母。
- **完整路由**：每ID扫描127个其他mid，包括相同低4位而高位不同的别名；不能提前绑定sid。每ID都逐一绑定0～15号sid并完成实际消费；空闲时收到本ID回执也不能制造有效路由。
- **回包/异常**：00/01/10/11响应错误独立保留；data逐位覆盖bit0～63；8个保留源异常位、fullva/gpaddr/Hyper/PTE及原ROB逐字段比较。输入异常位透传仅属于entry接口级检查，不声称父级允许已有异常的load入队。
- **精确报告相位**：消费在边沿N接受后，一级寄存的exception.valid即对应该次消费，N+1无新消费则撤回；无错误也报告，不能按error门控，也不额外插一个idle边沿修补检查。
- **取消边界**：等待ROB/总线未接受时直接取消；已接受请求的redirect粘滞保留，必须等真正response才释放；当前redirect与response同拍也检查。wakeup当前拍可能仍握手、Out与redirect同拍仍可能消费并报告，按真实接口检查而不是擅加门控。
- **重用/reset/随机**：正常或取消后NC/MMIO交替，新身份不能继承旧sid/error；五个阶段分别reset后重新完成。每ID两个Python种子88、20261018，各80条合法事务，变化许可、三处背压、总线响应延迟、错误和取消；实际初始化种子1。

早期4个失败来自测试把 `RobPtr.encode` 默认former=True误当latter；逐拍checker与DUT并无冲突。修正显式参数而不改模型年龄或RTL，失败运行保留，未xfail或跳过。

## 4. 参考与checked证据

独立参考以不可变Owner/UID和“保存/等待许可、总线接受、等待回包、等待唤醒、等待消费”语义阶段建模，不读取DUT内部状态。driver只驱动真实端口；参考只消费DriveStable/RisingEdge被动观察，并消费包括fixture切换空拍在内的全部周期。

普通行为的checked等待同UID实际数据消费及exception有效报告；取消行为等待公开flush和后续新UID真正完成。reset清空旧证明，不将中断旧事务计作收到响应或正常完成。SID/mask/data的审计集合进一步限定为最终实际消费的事务，而非只送过输入。

`verify_run.py entry-expanded-01 --require-semantic-complete --require-line-complete` 已通过：committed、384 PASS、16个原生构建、32个完整功能组、95份冻结验证源/合同/manifest文件，全部产物/build/快照SHA一致，checked≤reached。

`tools/audit_entry_trace.py` 不导入领域模型，独立按公开请求和事件时间戳重建Owner、pending历史、发起/握手、sid、回包、wakeup、消费、异常及延迟取消，逐拍重新比较所有适用输出：

| 量 | 实际统计 |
|---|---:|
| 连续观察记录 | **86129** |
| 非reset成功比较周期 | **83345** |
| reset边沿 | 2784 |
| 分配 | **5812** |
| 总线实际接受 / ID实际绑定 | 5280 / 5280 |
| response / wakeup | 5264 / 4752 |
| 消费 / exception报告 | **4672 / 4672** |
| 非消费取消释放 | **1060** |
| reset中断活动所有者 | **80** |
| 其他mid实际输入 | **2032 = 16×127** |

每例及全局所有权守恒：**5812 = 4672次消费 + 1060次取消释放 + 80次reset中断**。全部384例结束时无所有者或待报告事务。5280次总线接受与5264个response之差16，是五阶段reset中每ID各一次等待回包的中断，未虚构收到旧响应。wakeup数高于消费包含当前redirect允许的wakeup握手及reset等，未当作完成。

审计为每个ID分别确认：完成事务中的16种sid、127种其他mid反例、64个单bit数据、两半×8字节mask位置、4种响应错误；不是跨ID汇总后掩盖某ID遗漏。

## 5. 证据与复现边界

路径相对LSQ工程根目录：

- `results/entry-expanded-01/execution/`：committed manifest、16构建的原生coverage/LCOV、功能JSON/HTML。
- `results/entry-expanded-01/{command.json,pytest.xml,console.log,line-audit.json,evidence-check.json,trace-audit.json}`。
- `results/entry-expanded-01/cases/**/uncache_entry_<ID>.jsonl`及同目录FST：逐拍输入、pre/post实际与预期、Owner变化及波形。
- `results/entry-expanded-01/{verification-source/,source-evidence.json,evidence-auditors/}`：95份冻结源码与事后审计器哈希；后续合同的相位文字澄清另有当前文件，不覆盖历史快照。

```sh
python3 -B tools/run.py --name entry-recheck-<新后缀> --workers 1 -- tests/uncache_entry
python3 -B tools/coverage_audit.py entry-recheck-<新后缀>
python3 -B tools/verify_run.py entry-recheck-<新后缀> --require-semantic-complete --require-line-complete
python3 -B tools/audit_entry_trace.py entry-recheck-<新后缀>
```

行分母为原始SV的Verilator 5.052 DA，每top106行（16份分别统计，合计1696）；不含Picker外壳，不声称分支、表达式、非法覆盖活动entry、任意参数或整体穷尽。未测试父级已经路由之外的stale/无sid response输入，非法覆盖请求不冒充合法功能。下一步为保留真实16个entry和FreeList/仲裁/流水的LoadQueueUncache父块；RAR-REL-001仍开放，整体目标未完成。
