# StoreQueue：真实VSQ与PSQ闭环的组合验证合同

状态：**用例前合同已完成覆盖迭代与独立审计；sq-expanded-03 79例55 PASS/24 FAIL、43/51 checked，八项严格失败语义阻止验收，NOT_PASS**。开源`893e1580b`固定原样`StoreQueue.sv` SHA `de7c7b075e7b557cc0fb874d34f4b1c593144efe0093b402647e239a0501578e`，实际七文件闭包保留VirtualStoreQueue、PhysicalStoreQueue及其全部四个下级；没有Python替换下级。详见[报告](../reports/store-queue-20261018.md)。

## 1. 实际端口与输入合同

- 182输入（不含clock）、338输出。八路Valid-only dispatch含needAlloc、ROB、0..16 flow及紧凑exclusive SQ end快照；ROB head和redirect；其余STA/STD/S2/UQ/forward、Cache/Uncache/WB/Sbuffer与PSQ相同。实际top没有VSQ ready/canAccept端口，外部发行账本须遵守分配容量与恢复stall。
- 相比独立PSQ，`enqueue/retired/preCommit/redirect SQ/headRob`不再是可驱动输入：由真实VSQ产生，经真实连接和寄存进入PSQ；PSQ公开`sqDeqPtr/sqDeq`反馈真实VSQ。禁止从内存直接赋committed或隐藏指针。
- 普通producer的dispatch与同拍redirect互斥，前拍dispatch可与下一拍redirect相遇；同拍接口压力单列，不冒充正常生产者可达。恢复中不新dispatch；等待真实`sqRecoverStall`落下及必要流水清空后，用恢复后的exclusive tail重发新UID。
- 一个虚拟uop可含多个物理flow，共享ROB、只有最后flow释放后虚拟项才由PSQ释放反馈退休；普通ROB前进也可先于写出退休虚拟项，物理字节必须继续保持至实际消费。虚拟128个uop和物理flow占用128上限分开记账，发行仍仅当前64项物理窗口。
- STA/STD valid-only仅低6位slot，外部代理保证物理窗口/本代身份；S2按前拍同lane STA配对，TLB miss重试、跨word首末及真实UQ保持PSQ合同。CBO在ROB头许可域发行；特殊项只能等真实WB/NC确认后推进ROB，普通项可按已完成执行前进，但不能借此提前消费未许可/异常项。
- Uncache删去的响应错误/ID字段、常量WFI/inactive、未初始化payload和perf不假造动态功能；WB/exception有效时的ROB/VA/isHyper/Cache错误仍严格检查。所有Sbuffer ready为前缀，实际fire是副作用与完成依据。

## 2. 独立参考、采样和完成

参考由公开dispatch/ROB/redirect历史构造虚拟uop及end快照，公开STA/S2/STD构造物理语义entry，用标量SQ年龄检查完整flags。组合已有独立VSQ/PSQ语义参考时，必须同时由**旧状态**建立连接后再推进两个参考；不能把一方新状态当同拍真实连线。仅映射真实端口，不读取DUT内部VSQ/PSQ寄存器或层次信号作答案。

外部actor另记虚拟uop与每flow UID，使用公开physicalUpper/sqDeqPtr及分配历史约束发行。实际Sbuffer/WB/NC确认完成与随后SQ释放分别记账；普通flow/拆分片段只完成一次，取消/reset单列。检查empty须同时满足真实虚拟退休和物理写出完成，不能把ROB退休当内存副作用完成。活动恢复/reset后同物理槽新UID必须真正输出/完成。

## 3. 用例前可读功能点

| 组 | 微架构行为与必需情形 | 实际检查义务 |
|---|---|---|
| SQ-RESET | 空/活动/响应/WB等待reset不泄漏旧事务 | 同槽新UID完成、旧UID中止守恒 |
| SQ-DISPATCH | 八lane稀疏分配、needAlloc过滤、零/多flow紧凑end | 所有实际flow的原始字节及最终end一致 |
| SQ-PERMIT | ROB头preCommit与已退休边界各自驱动真实PSQ | 无许可不能提前写；普通/NC/IO/CBO正确完成 |
| SQ-RETIRE | VSQ普通先退休与PSQ未写出并存 | empty仍false，旧数据保持直到真实fire |
| SQ-CREDIT | 一个多flow uop须最后flow释放才退休 | 分段无early credit；VSQ/PSQ闭环无重复完成 |
| SQ-READY | STA/STD先后、洞/重试、前缀跨物理窗口推进 | 真实LoadQueue ready指针/位图与UID历史相符 |
| SQ-WRITE | 两入口/全槽/四圈、size/offset/跨word/line/page | 原PA字节、第二页、wline及真实消费 |
| SQ-FORWARD | 三load阶段、最年轻候选、缺数据/地址与等待 | 原值或重放、完整依赖身份、PA来源安全 |
| SQ-SPECIAL | NC/IO、四类CBO、请求/响应/WB背压与异常 | 请求只回应一次、错误保持到实际fire |
| SQ-ZERO | 老普通项驻留下级时再处理CBO.zero | 必须真实消费自己的零写后才WB/释放 |
| SQ-RECOVER | 合法前拍dispatch、idle/release/walk、幸存/取消 | 真实sqRedirectPtr、无ghost、取消后复用完成 |
| SQ-CAPACITY | 64物理发行与128虚拟flow占用、full/forceWrite | 无越代发行，fair drain真实完成全部UID |
| SQ-CONCURRENT | 固定种子乱序执行与写出/forward/总线/恢复并发 | 独立UID守恒与公平排空，不靠模型内部决定刺激 |
| SQ-FAULT | 真实VSQ约束下重新检查六类子块失败 | 可达则保留普通FAIL；不可达须具体上游证据，不以未触发当证明 |

## 4. 实施与覆盖闭环

先原样构建/实际端口codec/采样校准，再首批dispatch→执行→真实许可→写出→PSQ释放反馈→VSQ empty，含多flow和特殊流。首轮逐行分析本体及全部下级原生DA，每条未覆盖行分类为已有功能缺情形或遗漏整体功能；补例重跑。即使连接层本体全命中，仍继续完整语义/恢复/并发和独立公开历史审计。现存PSQ、VSQ失败不xfail、不读问题表、不改原RTL；本层验证不能等价为完整LoadQueue/LsqWrapper验收。

首轮`sq-initial-01`9 PASS，26/26本体但仅5504/8968闭包、11/50 checked；独立审计360公开记录、8虚拟uop/16物理flow实际完成、24个forward响应及239源SHA。3464条缺口逐项分类：VSQ1822（高虚拟slot快照、八lane优先和release/walk/恢复）、PSQ1601（高槽STA/STD/S2/CBO、跨flag计数和redirect）、Deq12（NC/IO）、ESB11（奇数尾单双消费）、Forward3（跨low/high且低域slot48..63）、UQ15（第二PA/消费/恢复）。全为既有合同缺少情形，未排除行。

下一补例必须由真实ROB head产生许可：两STA lane的NC/IO请求→方向确认/响应→WB→释放；Cache CBO四类和错误保持到实际fire；先退休普通项保留下级请求，再发射ROB头zero，检查自己的零写不能丢。普通split已执行后ROB前进到后续zero头，再发行zero，检查尾段实际fire的wline；不再用任意年轻CBO来代替上游可达性。别名/范围用真实dispatch/STA/STD构造三lanePA字节安全，不从PSQ伪造bank。

`sq-stream-directed-01`必要条件随机25090又由独立UID账本捕获SQ120的释放比规定Sbuffer credit早一拍：SQ121 NC确认时SQ120 split仍驻留，下拍释放计数混入第二head的handleFinish；原Deq阶段参考同样按RTL的PopCount求和，未检查其年龄前缀。这不是可直接当检查器误差消除的时限：补第51项`SQ-CREDIT.special_order`，用旧普通请求完全背压、年轻NC/IO实际完成但旧请求消费0次的最小probe，检查不能释放旧SQ；以原始公开输出决定问题分类，保留旧随机和参考快照。

最小probe三类均真实失败：旧普通请求消费0次，年轻NC确认或IO实际WB后，sqDeqPtr从0变1，旧请求仍valid。现已将Deq参考收紧为按完整SQ身份完成的连续前缀，不再照抄无身份求和，actor原严格时限/副作用检查未放宽。`sq-expanded-01`66例44 PASS/22 FAIL、36/51 checked，闭包5504/8968→8716/8968；余252行再次逐项分类（PSQ246主要为高槽/另一lane CBO保存，VSQ6为lane4/6最后有效分配）。下一轮补全64slot×两STA lane的逐head CBO实际完成、lane4/6稀疏dispatch、ready洞/重试、youngest/wait、kill/deq窗口和前拍dispatch在途恢复；再执行独立全历史审计，不能以本体26/26或局部失败提前结束。

`sq-expanded-02`79例55 PASS/24 FAIL、43/51 checked，本体26/26、七文件闭包8968/8968 DA。独立审计7105记录及1553 actor flow UID，但取消10个UID只有7个具有同槽新UID完成见证：UQ取消项复用的是另一槽、release/walk取消3项只补回1项。旧覆盖`SQ-RECOVER.page/REUSE.cancelled`口径因此过宽，不能把43/51当全部严格语义已闭合。补同槽新页和完整三项后缀后另跑新目录，旧目录/审计器不改写；新v2审计必须逐个取消UID绑定实际新owner消费与完成。
