# LoadQueueUncache：真实父块闭环与未通过项

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


**结论：NOT_PASS，仍未验收。** 完整 `load-uncache-expanded-03` 为 **64 PASS/8 FAIL，42个语义情形reached、40个checked**。真实22文件闭包未替换任何下级，原始RTL/Chisel未修改。SID合法重用存在数据与错误保持问题；另有一项明确不属于常规ROB许可域的多MMIO selector接口边界失败，二者分开统计。

## 1. 请求到交付物的检查清单

| 要求 | 实际产物和证据 |
|---|---|
| 先子块、再真实父块 | 已验收16个entry与FreeList_3；`rtl/load_queue_uncache/source.json`保留真实22文件，原生构建`results/builds/20261018T054848945017Z-load_queue_uncache/` |
| 用例前定义人类可读功能点 | `docs/contracts/load-queue-uncache.md`的15类微架构行为及合法输入/相位/边界，先于首轮用例 |
| Picker+xreactor真实运行 | 独立原生DUT、驱动、DriveStable/RisingEdge被动观察，完整72例；全部输入初始化，未绑定已删除ready/perf端口 |
| 独立正确性参考 | `lsqverify/load_uncache/model.py`：请求UID/排序、独立FreeList、16个已验收entry语义、等待者序列仲裁、弹性总线、外部SID义务与bypass/恢复到期报告；不读DUT内部寄存器 |
| 初轮逐行定位并补例 | 初轮762条本体、992条真实子块缺口分别映射；高行覆盖后继续补阶段取消/回收对齐/历史redirect/消费同拍/reset |
| 缺口迭代后实际检查 | 本体364/1126→1120/1126；真实闭包1421/3175→3169/3175；全部真实子块DA命中，剩6条guarded default有窄范围结构证明，原分母未改 |
| 真实失败不豁免 | `manifest/known-issues.json`保留7个合法SID失败及1个域受限接口边界，不被测试导入，不xfail、不跳过、不改RTL |
| 冻结与审计 | expanded-03运行后110份当前验证文件与启动快照全一致；`trace-audit.json`核验产物/build/快照SHA与9163条连续记录，明确NOT_PASS |

## 2. 分阶段结果

| 运行 | 实际结果 | 本体DA | 语义checked | 说明 |
|---|---:|---:|---:|---|
| `load-uncache-initial-01` | 3 PASS/2 FAIL | 诊断 | 首轮probe | 一个端口拼写KeyError与一个真实SID数据失败，分开保留 |
| `load-uncache-initial-02` | 4 PASS/1 FAIL | 364/1126，32.33% | 14/38 | 首轮端到端probe，不冒充完整逐拍参考 |
| `load-uncache-sid-expanded-01` | 10 PASS/7 FAIL | 368/1126 | 14/38 | SID0/3/15与必要条件正反对照 |
| `load-uncache-model-initial-01` | 2 PASS | 相位确认 | 完整参考首测 | 独立参考逐拍检查正常NC/MMIO |
| `load-uncache-full-directed-01` | 28 PASS/1 FAIL | 1120/1126 | 33/38 | 一个人工断言把回收FIFO分配顺序当槽号数值顺序，非DUT/参考不一致 |
| `load-uncache-expanded-01` | 44 PASS/8 FAIL | 1120/1126 | 37/39 | 7个SID失败；另一个人工断言忘记早期低组独占留下的低组偏好 |
| `load-uncache-boundary-directed-02` | 2 PASS | 定向复查 | 修正刺激断言 | FIFO分配顺序与候选撤回两例修正后通过，不改模型或RTL |
| `load-uncache-expanded-02` | 64 PASS/8 FAIL | 1120/1126 | 非最终冻结证据 | 新多MMIO接口边界失败；运行期间改进了coverage完成证明，因此另开最终运行 |
| **`load-uncache-expanded-03`** | **64 PASS/8 FAIL** | **1120/1126，99.47%** | **40/42** | 测试/参考运行期不再修改，运行后全部110份文件哈希与启动快照一致 |

最终全部72例使用通用逐拍参考，包括原先仅端到端probe的17例；旧运行保留自己的源码与结果，没有以新参考追溯宣称旧probe已完成一般检查。覆盖完成证明已收紧：同UID必须实际消费/报告且**s2数据成功比较**，不能只在s1消费就记作完整数据检查。取消则必须等待公开行为正确及后续新UID真正完成。

## 3. 未覆盖行逐项分类与补例

初轮本体762条全部为已有功能点的缺少情形：

| 本体缺口 | 数量 | 补例与检查 |
|---|---:|---|
| 排序后第1/2项保存元信息 | 128 | 三lane六排列、稀疏、同年龄、former/latter、ROB跨环，检查实际mid与最终数据/恢复身份 |
| 三路bypass选择不同entry的地址/数据/错误 | 372 | 16项×NC/MMIO×3 lane，正常、反匹配、同entry重复lane和多entry并行消费；逐拍s1/s2及异常 |
| redirect历史/rollback | 24 | 容量余0/1/2、最老拒绝者FTQ/RVC/checkpoint，当前/前1/前2拍取消与前3拍过期反例 |
| 更高entry异常汇聚 | 238 | 逐ID真实消费、错误/完整VA/50位GPA，多个消费按最低entry选一条报告，不虚构全部异常都上报 |

首轮真实子块另缺FreeList_3的112条、16个entry合计880条，均按集成功能缺少情形补，不能套用叶子100%覆盖。两级NC仲裁、弹性寄存器和wakeup仲裁首轮DA已满，但高低组公平、候选撤回、保持/替换等语义仍继续实测。

第二轮剩余90条高ID entry阶段取消、1条FreeList尾位置15由bank0写回，分别用逐ID等待许可/请求取消、16条合法合并回包后的wakeup取消，以及先真实返回15项、最后返回bank0、完整池再使用补齐。最终所有真实子块DA已命中：合计2049/2049。

最终本体6条缺口为2816/3012、3088/3284、3360/3556（三lane各data与paddr默认值）。每条受 `NC_any OR MMIO_any` 写使能保护，而写default要求 `NOT NC_any AND NOT MMIO_any`。`tools/audit_lqu_static.py` 对**固定原RTL哈希**检查三组向量的所有成员、使能和三目选择，枚举4种布尔输入，证明交集矛盾。证据为 `static-gap-proof.json`：仅证明这6条结构不可写，不是全DUT形式化验证，不改RTL/LCOV，也不将raw比例伪报100%。

- 原始本体：**1120/1126**；6条单独静态说明。
- 原始真实闭包：**3169/3175**；去重22文件，包括同文件FastArbiter被两次实例化的原生计数。
- 全部可达DA：本轮全部命中；**不代表分支、表达式、合法流量功能或整体LSQ通过**。

原首轮 `line-audit.json`（needs_review）和人工 `line-audit-mapped.json` 分开保存。最终原始line-audit仍是保守缺口映射，窄范围静态分类在独立proof文件中，不覆盖历史。

## 4. 已实际检查的父级语义

- 排序/过滤：真实ROB slot年龄而非lane/value数值；10个源异常位、其他replay原因、非NC/MMIO和两拍redirect过滤；完整池容量证明无隐藏分配，C_UNCACHE正常进入。
- 16项预分配及回收：余0/1/2项的部分/全拒绝、最老rollback、真实FreeList回收等待、跨池多轮，正常消费/共享redirect/reset分别计账。
- NC仲裁：高低两组进展、记忆候选撤回后回退当前有效项；弹性总线空/满保持、同拍换出/换入。区分entry内部接受与外部握手，redirect不能抹掉已捕获总线请求。
- 正常MMIO按一级pending许可，活动selector可以阻止后续NC但不能改写已缓冲NC；MMIO和NC各自低entry优先wakeup，阻塞者保持，接口不虚构外部wakeup ready。
- 全7位mid：父块16个有效mid正例与16～127高位反例；全部sid、乱序回包、未绑定sid反例；合法相同属性/地址的多mid同sid合并正例通过，不将任意异地址事务硬凑为合法合并。
- bypass：LQ flag/value和类型的正反匹配、等待回包时不命中、消费后不命中；每ID×两类型×三lane共96种组合都有**成功s2数据/错误比较**的独立见证，6个逐ID正向用例均完整通过。补充工具`audit_lqu_successful_tuples.py`只从checked周期提取正向证据，`successful-bypass-tuples.json`逐组合记录UID、s1/s2 tick、journal和SHA，不使用8个失败输出凑正向覆盖。
- 重复三个lane消费同一个entry只回收一次；不同entry同拍消费有各自数据输出，exception单通道只选最低entry，不能声称被舍弃事件都上报。
- 共享redirect的former/latter、flushSelf/After、159→160回绕；保存、等待许可、请求、缓冲、响应、wakeup、数据阶段取消/reset；消费与redirect同拍仍检查s1/s2与exception。
- 2个Python种子88与20261018，各10轮×16项合法批次，变化输入lane、属性/mask/数据、两个响应错误、乱序返回、外部背压与三lane消费。原生初始化种子1。

不比较无valid payload或读请求Don'tCare data；同时置NC/MMIO的非法普通事务未当作常规功能；没有把未保留perf、ready或内部寄存器冒充公开观察点。

## 5. 两项未通过行为必须分开解读

### LQU-SID-001：合法SID返回后重用会污染旧entry

序列：A(mid0/LQ11/SID3)总线→ID→回包dataA→wakeup，但不消费；外部释放SID3，接受B(mid1/LQ12)并重用SID3；B回包dataB。随后取A，paddr仍属于A，但s2得到B数据。

期望64位数据 `0x0123456789abcdef`，实得 `0xfedcba9876543210`；128位bypass为相应值复制两遍。SID0/3/15均复现，若B带error，A的exception hardwareError也错误变1。**7个普通失败**分别保留；6个“旧A先消费才重用/旧A未消费但B使用不同SID”的必要条件对照均通过，多mid同一次合并回包的正例也通过。

合法性依据：开源 `cache/dcache/Uncache.scala:493-499` 的resp.fire立即updateReturn，`UncacheEntryState.updateReturn:166-171`清除外部valid；没有等LDU消费的接口。不能为了测试变绿，强迫SID一直保留到LDU消费。

根因证据：父块 `LoadQueueUncache.scala:438-439` 仅按slaveId.valid/id广播回包；旧entry的slaveAccept持续至消费/flush，`193-197`又无状态过滤地保存每个收到的response。独立entry合同假设response已正确路由，所以叶子通过不会掩盖父块合法重用错误。当前严格父级参考按**尚未完成的外部事务义务**接收回包，旧数据不随新SID同号事务更新。

### LQU-MMIO-IF-001：仅UNIT-INTERFACE多selector边界

单列刺激让pending跨过两个未完成MMIO，两个entry同时selector有效。高ID1正确优先上总线，但ready广播给所有selector，低ID0也进入response。消费ID1后期望ID0还可发起，实际无有效总线请求。

这是**1个普通失败的单元接口边界**，不符合常规ROB许可代理，未证明合法架构流量可达，不应和前述合法SID缺陷混作两项已证实系统缺陷。仍保留失败及完整输入域说明，不通过改成“低ID丢失也是正确行为”使参考变绿。常规MMIO/NC优先及合法ROB推进的独立用例通过。

## 6. 审计与守恒

`tools/audit_lqu_trace.py`不导入领域模型，先核验所有committed产物、build文件及110份源码快照哈希、测试节点和功能组，再按输入/FIFO、公开总线、mid/sid义务、第一次回包、wakeup、bypass和exception重建生命周期；完整仲裁顺序仍依赖已执行的逐拍参考，不宣称第二条动态RTL复现或独立仲裁实现。

| 统计 | 数量 |
|---|---:|
| 连续公开引脚记录 | **9163** |
| 完整逐拍比较成功的非reset记录 | **8621** |
| reset / 最终失败记录 | **534 / 8** |
| 分配 | **943** |
| entry内部捕获（由公开弹性总线变化重建） | 901 |
| 外部总线握手 / idResp | **893 / 893** |
| response输入 / 对有效等待者投递 | 892 / 892（包括无匹配sid反例输入，合并时多投递） |
| wakeup握手 | 874 |
| 实际消费（含失败例停止前发生的消费） | **863** |
| 取消释放 / reset活动中止 | **59 / 13** |
| 测试结束保留的Owner | **8，仅8个失败例各1个** |
| bypass lane命中 / s2有效结果（含失败） | 865 / 862 |
| exception有效报告 / rollback报告 | 660 / 4 |

守恒：**943 = 863消费 + 59取消释放 + 13活动reset中止 + 8失败结束保留**。64个成功例结束均无Owner、外部未完成事务或缓冲请求；8个失败不伪装已排空。多个entry同拍消费只出一条exception，因此660不冒充863个并行异常报告。s2有效结果包括4个错误data结果，不把862都称作成功比较。

## 7. 复现、证据和后续

相对独立LSQ根目录：

- `results/load-uncache-expanded-03/execution/manifest.json`：committed，72例真实64/8，1构建、2完整功能组、原生LCOV及HTML/JSON。
- `results/load-uncache-expanded-03/{pytest.xml,console.log,command.json,line-audit.json,static-gap-proof.json,trace-audit.json}`。
- `results/load-uncache-expanded-03/{successful-bypass-tuples.json,successful-bypass-tuples-audit.json}`：96个成功s2组合的逐项见证和补充审计器哈希。
- `results/load-uncache-expanded-03/cases/**/{load_queue_uncache.jsonl,public-checks.jsonl,load_queue_uncache.fst}`。
- `results/load-uncache-expanded-03/{verification-source/,source-evidence.json,evidence-auditors/}`。

```sh
python3 -B tools/run.py --name lqu-recheck-<新后缀> --workers 1 -- tests/load_uncache
# 预期会如实保留8个FAIL，不把退出码1吞掉或当PASS
python3 -B tools/coverage_audit.py lqu-recheck-<新后缀>
python3 -B tools/audit_lqu_static.py lqu-recheck-<新后缀>
python3 -B tools/audit_lqu_trace.py lqu-recheck-<新后缀>
python3 -B tools/audit_lqu_successful_tuples.py lqu-recheck-<新后缀>
```

`verify_run.py`零失败门禁不能用于本次验收；专用审计明确`NOT_PASS`。最新53份原始RTL SHA全部一致，开源XiangShan工作树干净。RAR-REL-001保持开放，本块也保留未验收；继续独立Replay，再Store分支与真实LoadQueue/StoreQueue/LsqWrapper组合，不能将当前叶子/父块覆盖当作整体完成。
