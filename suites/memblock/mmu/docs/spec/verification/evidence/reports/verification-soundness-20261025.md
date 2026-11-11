# TLB/MMU 验证可信度复核（2026-10-25）

## 方法与范围

本轮为独立复核，不继续或重写已经关闭的目标。先冻结交付报告和归因登记中的
结论，再沿报告→证据→接口定义/RTL→环境→用例反查；完成归因复核后才全面审计
现有 case。旧的 PASS、strict XFAIL 和交付自检均不是本轮的正确性前提。

假阳性：无效激励、环境错误或错误契约被误报为 DUT 缺陷。
假阴性：漏检、宽泛 XFAIL、错误期望或丢失响应使 DUT 错误被报告为通过。

## 执行计划

1. 从所有模块报告及 known-issues 提取闭合、缺陷、不可达和范围声明，检查证据强度。
2. 先核实 sfence 编码、并发/内存响应时序、PMP 调度、预取归因等高风险结论；
   使用接口定义和最小对照实验，不将相关性当成根因。
3. 逐一枚举全部 case 和实际 pytest collection，检查重复定义、checker 完整性、
   握手、时序、复位、参考模型独立性、XFAIL 范围、超时、覆盖采样和隔离。
4. 修复证实的环境/检查问题，增加有实际断言的回归与 checker 负向自检；
   保留新旧证据，重跑受影响的独立 DUT 和直接上层组合。
5. 更新报告、归因、基线及交付自检；未复核/未解决项明确列出，不以覆盖率替代验收。

## 初始发现（待证实）

- 报告将 `rs1=0/rs2=0` 直接称为 all-address，尚缺 bundle 编码定义证据。
- `mem_latency=7` 下通过只能证实时序相关性，不能单独证明零延迟双 beat 丢失根因。
- LLPTW/Bitmap responder 串行服务可能漏掉同时发生的公共端口握手，须独立审计。
- 5 个 strict XFAIL 不等于 5 个独立缺陷；LLPTW PMP 间隔并未包含在该计数内。
- `known-issues` 中多个 resolved 项仍保留相互矛盾的 impact 文字；报告存在旧 run
  计数与强于证据的根因/不可达表述。

## 报告驱动的归因复核

先读取全部 14 份模块/交付报告与 34 条 known-issues，再核对接口定义和环境。
旧报告及修改前 case 全文分别保存在 `evidence/soundness-20261025/` 的
`before-reports.json`、`before-case-sources.json`，不是修改后重述旧结论。
逐条归因复核见 `claims.json`，其中 8 条旧缺陷/限制归因被撤回。

| 旧结论 | 反证及处理 | 判定 |
|---|---|---|
| all-address sfence 不失效 | 两份设计源 `backend/fu/Fence.scala` 都令 rs1/rs2 为寄存器编号是否 x0。1/1 才是全地址/全 ASID。原 0/0 + addr=0 不应清掉非零 VPN。更正极性和字节地址后通过；加入目标页/邻页对照。 | 错误契约引起的误报 |
| LLPTW 多 allStage 停顿 | 旧 service 的 if/continue 在处理响应时漏掉其他 ready=1 的请求。改为每个时钟沿并行捕获所有 fire 后，两个 entry 均返回正确 VPN/source/PPN/fault。响应延迟 0/1/3 对照通过。 | 环境误报，撤回 RTL 调度归因 |
| Bitmap 连续请求 PMP alias | 同类串行 service 漏 cache fire。修复全通道采样后两个 ID/cf/cfs 均正确。 | 环境误报，未证实 PMP alias |
| Bitmap multi-miss 必须两次读 | 修复监测后两个响应均到达；0x80000/0x80008 应合并一个 bitmap block 读取。原第二个读数量断言错误，被整例 XFAIL 掩盖。另加不同 block 必须两次读。 | 环境 + 错误期望误报 |
| 第三个共享 leaf demand 被预取替代 | D beat 发送分支 continue，但 A.ready 仍为 1，漏记同拍 demand。修复 A fire 捕获后零间隔通过。相邻 prefetch 不是 demand 被替代的证明。 | 观测不完整，撤回因果归因 |
| LLPTW 必须至少空闲 3 拍 | 连续 normal 请求在修复环境后直接通过。 | 未证明的限制已撤回 |
| mem_latency=7 证明第二个 D beat 丢失 | latency=7 通过只说明相关性。导出接口无 D.ready；真正已定位的问题为 D 发送期间漏 A fire。0/1/7 重新验证。 | 撤回旧双 D beat 根因解释 |

这里“假阳性”指错误报告 DUT 缺陷；“假阴性”指 DUT 或验证错误被漏检。
撤回误报不等于证明所有并发状态正确，更不等于 MMU 签核。

## 所有现有 case 的常见问题审计

覆盖整个 `tests/` 的 AST 定义、实际 pytest collection、assert、helper/checker
调用与 decorator 清单，详见 `case-inventory-before.json`、`case-audit.json`
和 `collection.json`。静态检查是全量的；语义证明和 mutation testing 并非穷尽。

| 问题 | 已处理内容 | 仍需注意 |
|---|---|---|
| 重名覆盖 | L2TLB 19 组完全相同的重复定义、HPTW 1 组不同重名定义；旧文本已保存，去掉 shadowed 版本。 | 名称计数不等于实际 collection；新增防回归审计。 |
| 注释中失活 | 两个 PORT-02 函数被字面量反斜杠 n 写成单行注释，从未收集；恢复 L2TLB/wrapper 双端口测试。 | 旧版本还在时钟沿前撤 valid，根本没有 fire；已改为沿前采样、沿后撤销。 |
| 恒真/条件逃逸 | PtwCache 两处 `else True`/`if False` 已修复；TLB/DTLB 地址 OR 表达式只加了澄清括号。 | Python 的位运算优先于比较，原地址表达式并非恒真或漏检；撤回对此的缺陷归因。 |
| 响应漏字段 | 多个“成功”用例仅查 v/PPN，不查 af；all-ones Bitmap deny 被当成功刺激。 | 正例改允许 bitmap，成功 checker 同时检查 valid/tag/PPN/stage/fault；deny 有独立负例。 |
| 整例 XFAIL | 任意 assertion、timeout 或 setup 异常均可能被宽泛 XFAIL 吞掉；strict 只防 XPASS，不限制失败原因。 | 本轮证伪的 5 个 marker 全部移除；不以 runxfail 结果充当通过。 |
| 自指参考答案 | PMP reset 把 live DUT PMA 初值当期望，无法抓初值错误。 | 改为固定配置表及 SHA；它仍是 build-specific 配置 oracle，不是完整架构模型。 |
| 纯位压力 | PTW/PtwCache/PTWFilter 位扫描只有激励，或同时驱动多种不合法控制。 | 标为 structural_stress，加恢复后的真实事务断言；不得算功能要求闭合。 |
| 误名场景 | MQ simultaneous 原来只有顺序 enqueue/dequeue。 | 改为真实同拍入/出 fire 并检查保序。 |
| 复位与隔离 | 多个环境 reset 未清 pending；HPTW 默认额外 sfence 可能掩盖首走行为。 | 清服务队列；reset-without-flush 作为单独 characterization，不能用默认初始化习惯推出 RTL 缺陷。 |
| 无界等待 | 若干 issue 的 ready while 无超时；等待时还不服务其他端口。 | 增加有界超时；walker 等待时服务通道；运行器设 1800 秒硬边界。 |
| 缺省端口 | DTLB opt() 对任何缺失输出静默补 0。 | 只允许明确列出的端口裁剪；必须输出缺失立即失败。 |
| 模型错误 | Prefetch model flush 把 history 清为 []，后续消费会越界。 | 恢复固定 4 项 None，增加模型负向/恢复自检。 |
| 事件采样 | Prefetch 空闲周期也被记为 consume；手工采样默认 stage/page 可能夸大 bin。 | 改真实 consume；功能覆盖数字只代表已定义 sampled marginals，不能证明语义点或交叉覆盖完整。 |

## 不能继续沿用的强结论

- “逐项分类”不等于“不可达已证明”。没有 direct-way selector 不证明合法替换
  序列无法触达该 way，PtwCache 7577 个功能信号残余仍是数据/情况枚举缺口。
- LLPTW 299 行、Bitmap 441 行和 HPTW/PTWFilter toggle 残余均是旧 run 的观测，
  新环境必须重新计算；不能复用旧不可达/闭合措辞。
- TLBFA fake-PTE 的 level3 arm 死分支由 RTL 条件顺序支持，但现有 case 期望
  实现的 level0，只能作为 characterization；设计期望 level3 是否仍有效需独立
  规格/设计者确认，不能把“匹配 RTL 模型”的 PASS 算架构正确。
- PLRU 不优先 invalid 为实现/性能观察，不自动构成功能缺陷。
- HPTW accessFault 每拍重新赋值；无同步 reset 不足以推导 spurious first fault。
- SFENCE 允许 over-fence；邻页保留是本实现的精细作用域观察，不是 ISA 必须
  保留缓存的要求。不能因多刷新而误报 ISA 缺陷。

## 当前状态

修复均在验证环境、checker、case 与文档，未修改 DUT RTL。17 个独立 DUT
最终 suite 与 checker 自检已完成；精确结果及保留范围见末节。

## ISA 补充复核（2026-10-26）

详见 `isa-confirmation-20261026.md`。修正 PageMemory root leaf 布局后，完整
wrapper 回归暴露了旧 PMP 正例 PPN=0x3000 对 1GiB 页不对齐，硬件 page fault
符合 ISA；改为对齐正例，并另存未对齐负例，不放松 PF 检查。
另外撤回“satp 无 sfence 就在软件契约外，可接受 timeout”的笼统豁免：
但也不能反向主张所有 no-fence 请求必须完成：ISA 对 satp 有效时已开始、
随后 satp 不再有效的翻译明确不要求完成/终止（无匹配 fence 时）。必须先区分
该例外与切换后新请求；旧 timeout 尚不是修正环境下可分类的证据。

## 最终回归与交付边界（2026-10-26）

最终选定 17 个真实 RTL DUT run：395 PASS；checker/model 自检单独 13 PASS，
合计 **408 PASS，0 FAIL/XFAIL/SKIP**。实际 collection 为 408 unique nodeids，
395 个 Python test 定义；分类为 functional 390、characterization 2、
structural-stress 3、checker-selftest 13。functional 只是用例分类，
不是所有语义点均已证明。静态审计 PASS/0 failures 也不是 helper/oracle 完整性证明。

| 模块/组合 | PASS | 行 covered/total | toggle covered/total | branch covered/total | 最终 run |
|---|---:|---:|---:|---:|---|
| TLBFA | 31 | 3419/3419 | 17766/17766 | 1016/1018 | `soundness-final-tlbfa-01` |
| TlbStorageWrapper | 8 | 3431/3431 | 18798/18798 | 1019/1022 | `soundness-final-wrapper-01` |
| TLB | 25 | 3655/3657 | 18785/23074 | 1094/1104 | `soundness-final-tlb-01` |
| TLBNonBlock | 30 | 4839/4956 | 20486/37422 | 1424/1568 | `soundness-final-tlbn-01` |
| L2TlbMissQueue | 5 | 24/24 | 829/854 | 17/18 | `soundness-final-l2mq-01` |
| L2TlbPrefetch | 6 | 39/39 | 657/784 | 22/23 | `soundness-final-l2pf-01` |
| PTWRepeaterNB | 7 | 72/72 | 3114/3114 | 7/8 | `soundness-final-ptwrepeater-01` |
| PTWFilter | 14 | 206/206 | 4412/4414 | 91/92 | `soundness-final-ptwfilter-01` |
| HPTW | 21 | 133/133 | 5069/5270 | 97/98 | `soundness-final-hptw-01` |
| PTW | 30 | 530/530 | 12213/15344 | 418/420 | `soundness-final-ptw-01` |
| PMP | 12 | 2117/2117 | 47680/51404 | 437/470 | `soundness-final-pmp-01` |
| BitmapCache | 12 | 314/323 | 6953/14174 | 124/148 | `soundness-final-bitmapcache-01` |
| Bitmap | 19 | 994/1415 | 2138/6636 | 290/398 | `soundness-final-bitmap-01` |
| PtwCache | 50 | 13744/13748 | 95616/110892 | 3182/3226 | `soundness-final-ptwcache-01` |
| LLPTW | 27 | 1660/1955 | 4330/20770 | 359/407 | `soundness-final-llptw-01` |
| L2TLB | 46 | 17079/22249 | 96980/255430 | 4330/6304 | `soundness-final-l2tlb-02` |
| L2TLBWrapper | 52 | 17460/22289 | 96604/260640 | 4430/6304 | `soundness-final-l2tlbwrapper-02` |

各 run 的已定义 sampled functional groups 均为 100%，但不能推导未定义功能点、
交叉覆盖、oracle 独立性或架构正确性。全部分母保留，覆盖下降不回退成历史较高
数字：wrapper corrected run 为 17460/22289 行、96604/260640 toggle，
不复用旧 17697/22289 和 102301/260640。

### 源码、时间与失败证据

- seed=1；每个 run 的 before/after 源码快照完全相同，
  stable_during_run=true。交付检查逐项核验 RTL、构建产物、coverage processor
  及覆盖输入哈希，不把同一 build 名称当成二进制相同的证明。
- 前 15 个 DUT 和 checker run 的 recorded finished_at 是 2026-10-25；
  两个顶层 -02 run 的 recorded finished_at 是 2026-10-26；覆盖审计及本轮
  汇总在 2026-10-26 完成。按原记录保留，不重写时间或重跑完成项。
- 历史全树 run 快照不等于当前全树：后加 ISA case/helper 只影响已重跑的
  l2tlb/l2tlbwrapper，其他 suite 的选择范围和保守本地 import 闭包不含这三文件。
  audit_cases 后续只改 category/review 输出元数据，保留哈希匹配的旧源码并
  验证去掉这两个字段后的 AST 相等；交付 verifier 是未进入测试运行的离线工具。
  逐 run 差异、依赖和旧/新 SHA 见 source-drift-review.json，不伪称全树相同。
- soundness-final-l2tlbwrapper-01 原 50 PASS + 1 FAIL 和完整日志保留。
  未对齐 1GiB PMP 正例是测试错误；soundness-isa-controls-01 的 16 PASS
  仅作对照，不重复加到 408。最终基线只选 wrapper -02（52 PASS）。
- runner committed 只是产物完成状态，不是 git 提交。本轮未提交或推送。

### 仍然开放

- fake-PTE 内部 level 到架构 guest fault/GPA 的影响：当前仅实现刻画。
- 条件化 no-fence liveness（含 satp inactive 旧在途翻译例外）、HFENCE.GVMA
  定点 GPA、A/D 并发更新、完整 privilege/异常优先级交叉覆盖。
- LLPTW 295 行、Bitmap 421 行、DTLB 117 行及顶层数千行等残余仍需合法事务和
  状态/数据序列；逐点清单保存在各最终 run 的 coverage-audit.json。
- PtwCache 当前 15276 个未 toggle 点中 15254 启发式标为 other、22 为 initial；
  分类名和缺少 direct-way selector 都不证明不可达，旧 7577 数字仅属旧 run。
- MBIST/DFT 明确排除。完整 CSR WARL/异常退役级 ISA、整个 MMU/SoC 均未签核。

### 最终证据与自检

入口：evidence/soundness-20261025 下 final-runs.json、final-residuals.json、
source-drift-review.json、collection.json、case-audit.json、isa-sources.json。
执行 python3 tools/verify_delivery.py，结果写入 results/delivery-audit.json。
增强检查包括固定 seed、运行内源码稳定、已审计的运行后差异、RTL/build/native
coverage 哈希、collection 分区与 PASS-only、固定 PMA oracle 和残余披露；
另有 16 项交付判定逻辑正/负向检查，不重复计入 408。
该 PASS 仅表示证据与所选回归范围一致，不表示关闭上述开放项。
