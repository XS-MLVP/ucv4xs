# IFU 功能点（微架构语义表述）

功能点按“这个模块对硬件行为承诺了什么”表述，而不是端口/信号清单。每个功能点都有
独立参考模型或架构规则作为期望来源（见“依据”列），测试用独立编码器构造激励，因此
期望与激励是两份独立描述，不复述 RTL 赋值。

功能点 ID 与 `verification_plan.json` 一一对应；`tests/` 中每个用例必须挂至少一个
ID，未挂或引用未知 ID 会直接报错。

## RvcExpander（`IFU-RVC-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | 低两位为 11 的字已是 32 位操作，展开必须原样返回且永不报非法 | 截断/改写普通指令 | RISC-V 压缩指令规范 |
| 002 | 压缩立即数/寄存器/栈指针形式展开为唯一 RVI 操作，目的/源寄存器与符号扩展立即数不变 | 立即数符号位或寄存器映射错误 | 规范编码表 |
| 003 | 压缩访存展开后访问相同字节：宽度、按比例偏移、符号/零扩展、栈基址不变 | 偏移错位或符号扩展错 | 规范编码表 |
| 004 | 压缩跳转/分支展开为相同目标 PC、条件与链接寄存器 | 位移符号扩展或链接寄存器错 | 规范编码表 |
| 005 | FP 状态开启时压缩浮点形式按 RVI 展开，关闭时必须报非法；整数形式不受 FS 影响 | FS 门控缺失或被误用于整数形式 | 规范 FS 状态规则 |
| 006 | 保留编码必须报非法，不得发出伪操作 | 保留编码被当作合法 hint | 规范 reserved 定义 |
| 007 | hint 编码合法且不产生异常（允许生产者规范化） | hint 被误判非法 | 规范 hint 定义 |
| 008 | Zcb 字节/半字访存与窄整数扩展的偏移、符号性与扩展操作正确，保留子编码报非法 | Zcb 偏移或 subop 解码错 | Zcb 规范 |
| 009 | 展开只依赖当前输入与 FS，无隐式状态 | 非法锁存或历史依赖 | 组合语义 |

## InstrBoundary（`IFU-IB-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | 取指窗口是 16 位槽的字节流；压缩映射给出每条起始指令宽度，carry-in 表示槽 0 是上窗口的后半。必须每个架构指令恰好产生一个起始 | 多/漏指令起始 | 指令边界定义 |
| 002 | 每个起始携带压缩位、所属 fetch block、块内起止偏移与 cacheline index | 偏移交换导致取错字节 | 取指坐标定义 |
| 003 | end mask 标记每条指令最后一槽，任意前缀的 popcount 等于该前缀内的架构指令数 | 计数偏一 | 指令计数语义 |
| 004 | 窗口在 32 位指令前半结束时必须报告“下一窗口续取后半”，分别对第一块结束位与总结束位报告 | 丢半条指令 | 半指令续取语义 |
| 005 | 落在块边界上的 32 位指令是一条指令：标记 cross-block 由第二块提供高半；已压缩或已 taken 的结束不标记 | 拆成两条无关指令 | 跨块组装语义 |
| 006 | 第二块槽位使用自身块内坐标（blockSel、起止偏移、index） | 延续第一块编号 | 块归属语义 |

## PredChecker（`IFU-PC-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | 只有控制流指令可被预测 taken：直接跳/间接跳/返回必须 taken，条件分支可任意，非 CFI 不得 taken | 违规不被发现 | 前端预测合同 |
| 002 | 无违规时整个窗口保持可入队且不重定向 | 误杀正确路径 | 预测合同 |
| 003 | 首个违规处截断入队窗口（含违规 lane，之后全部不入队），后续违规不影响首个 | 使用后续更“显眼”的故障 | 推测执行语义 |
| 004 | 直接跳/条件分支用 PC+位移算目标；间接跳/返回本阶段不可知，必须顺序 PC；顺序步长为压缩/非法 2 字节、否则 4 字节 | 编造目标或步长错 | 重定向语义 |
| 005 | 重定向携带违规 lane 的 taken、invalid-taken、非 CFI-taken、branch attribute、RVC、块归属、end offset、cross-block；invalid-taken 无有效属性 | 属性张冠李戴 | FTQ 训练接口语义 |
| 006 | 取指顺序决定故障优先级，报告必须来自最早违规 lane | 优先级编码器选错 | 顺序语义 |
| 007 | 重定向是“对上一拍请求的响应”，请求撤销后必须消失；背靠背请求各自产生自己的重定向 | 陈旧重定向或状态粘连 | valid-ready 语义 |

## IfuUncacheUnit（`IFU-UC-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | 空闲时接受一个请求并锁存地址与内存类型；忙时新请求不得扰动已锁存值 | 覆盖在飞请求 | 单槽语义 |
| 002 | MMIO 与 PBMT=IO 非幂等，须等更老指令排空；PBMT=NC/PMA 普通非缓存可立即发起 | 非幂等访问超车 | 内存序语义 |
| 003 | 请求保持到总线真正握手；反压或 IFU 不能接收响应时不得丢弃 | 丢请求或地址漂移 | valid-ready 语义 |
| 004 | 出站属性正确表达 MMIO vs 主存、NC 页 | 属性反了 | 互连协议语义 |
| 005 | 总线完成变成读数据与指令异常：corrupt→硬件错、denied→访问错、干净→无异常；保留 needResend | 异常映射错 | TileLink/异常语义 |
| 006 | 每次请求只有一个完成脉冲，脉冲带稳定数据/异常，随后回到空闲并可立即接受下一个 | 多脉冲或漏脉冲 | 完成事件语义 |
| 007 | flush 中止任意阶段、清除完成脉冲与载荷；迟到响应必须被丢弃 | 迟到响应产生指令 | 冲刷语义 |
| 008 | 单请求槽互斥；完成当拍即可接受新请求，不多等一拍 | 重复接受或空转 | 单槽+吞吐语义 |

## FrontendTrigger（`IFU-TR-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | 配置按索引原子更新，只替换该 trigger；下一拍可见，不出现部分更新 | 更新泄漏到相邻 trigger | Sdtrig CSR 语义 |
| 002 | 用完整虚拟 PC 与 **64 位 `tdata2`** 按 EQ/GE/LT 匹配；超出实现地址空间的 trigger 值不得混叠到真实地址，不支持的模式不得命中 | 只比较低 50 位（当前 R-13 缺陷） | Sdtrig 匹配语义 + CSR `Tdata2Bundle RW(63,0)` |
| 003 | enable、select（本单元仅 PC 匹配）、debugMode 三重门控，清/恢复即时生效 | 门控失效 | Sdtrig 语义 |
| 004 | 合法成对链：chain=1 自身不开火，只在两者都命中时允许紧随者开火；断链或未配置伙伴抑制终端动作，同 PC 的独立无链 trigger 仍开火 | 链式误开火 | Sdtrig chain 规则 |
| 005 | 同 lane 多 trigger 动作优先级 debug > breakpoint（需 CSR 允许）> none；不支持的 trace 动作不得变成 breakpoint | 优先级/动作错 | TriggerAction 语义 |
| 006 | 动作按 lane 解析，一个 lane 的命中不得泄漏到相邻 lane | lane 串扰 | 逐 lane 语义 |
| 007 | 复位后配置与使能为空，即使使能输入为高也不得开火；复位后可重新编程 | 复位后残留 | 复位语义 |

说明：本配置所有 trigger 由 CSR 生成为 before-execution timing，接口未暴露 timing
输入，因此链式条件中的“timing 相同”恒成立；功能点 004 只承诺可达语义。

## IfuPerfAnalysis（`IFU-PA-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | top-down 理由随三级取指流水传播，输入快照 N 拍后原样出现在输出 | 理由错拍或位错 | 流水语义 |
| 002 | ICache/I-TLB miss bubble 注入等待级并随流水输出 | 归因到后续重定向 | top-down 归因语义 |
| 003 | 前端回写重定向对在飞全部级标记 BTB miss，报告持续流水深度而非单拍 | 只报一拍 | 报告宽度语义 |
| 004 | 后端控制流重定向用后端 blame 覆盖前端预测类理由（本配置 SC/BTB 无端口） | 覆盖不生效 | top-down 覆盖语义 |
| 005 | 内存违例与其他重定向分别标记各自理由，不得混淆 | 两类合并 | 归因分类语义 |
| 006 | 并发注释按文档优先级：回写 BTB 覆盖后端控制流覆盖的同位，后端覆盖只替换其点名的预测类位、不清除无关在飞理由 | 误清无关理由 | 覆盖优先级语义 |
| 007 | 理由是逐级替换而非累积；不再在飞的理由三级后必须消失 | 陈旧理由残留 | 老化语义 |

## Ifu（`IFU-TOP-*`）

| ID | 语义 | 典型错误 | 依据 |
|---|---|---|---|
| 001 | 取指请求握手：仅当第一级可吸收时接受，接受后窗口恰好前进一次 | 丢窗口或重复 | valid-ready 语义 |
| 002 | 入队指令流保持取指程序：混合 16/32 位、跨块组装、展开后指令字、RVC 标志、FTQ 归属、end offset、预测 taken 与折叠 PC 均正确 | 指令流错位 | 组合语义（复用 IB/PC/RVC 模型） |
| 003 | 非法压缩指令不得发出伪操作，保留原字并定位到该 lane 的非法指令异常 | 伪造操作 | 异常语义 |
| 004 | 入队对齐跟随 IBuffer 写 bank 指针：第二次取指按前次入队数移位，不丢不乱序；指针跨 48 窗口回绕时仍正确 | 对齐错位 | 预对齐语义 |
| 005 | 预测错误时在故障指令后停止入队并向 FTQ 发带架构下一 PC、taken、属性、FTQ 索引与 end offset 的重定向；含 invalid-taken（预测指向 32 位指令中段） | 错误路径入队 | 重定向语义 |
| 006 | IBuffer 反压期间拍载荷与 valid 保持稳定，ready 恢复时恰好释放一拍 | 拍内容漂移 | valid-ready 语义 |
| 007 | 后端重定向（含 BPU stage3 冲刷）丢弃在飞取指，之后可接受重定向后的取指 | 被冲刷取指到达 IBuffer | 冲刷语义 |
| 008 | ICache 异常元数据与 GPF 地址写回：PF/GPF/AF 附着到正确 lane，GPF 同时把 guest 物理地址与 FTQ 索引写入后端 GPA 存储器；第二块异常落在该块首指令 | 异常挂错 lane | 异常传递语义 |
| 009 | 非缓存取指：离开发起正确属性的 uncached 读、等待响应、展开返回指令、附着总线异常、顺序重定向 FTQ；跨页 resend 保留已完成半字并在下一窗口组装 | 非缓存路径漏指令 | 非缓存语义（复用 UC/RVC 模型） |
| 010 | 前端 PC trigger 命中恰好标记对应指令 lane，其他 lane 无动作 | 动作串扰 | 触发传递语义 |
| 011 | 跨越两个取指窗口的 32 位指令恰好组装一次：第一窗口不入队截断指令，第二窗口以原 PC 入队完整指令 | 拆成两半或漏指令 | 半指令续取语义（复用 IB 模型） |

## DUT 合同（单位、身份、复位、时序与取消）

下表补足功能点描述中不适合逐条重复的合同字段；不适用项给出理由，不以“接口名暗示”
代替合同。

| DUT | 单位 / 地址域 | 身份 | 参数与配置 | 复位 | 背压 | 同拍顺序 | flush / redirect | 异常优先级 | 可取消边界 / 时间保证 |
|---|---|---|---|---|---|---|---|---|---|
| `RvcExpander` | 32 位输入字；PC 不在本层 | 无（纯组合） | `fsIsOff`；XLEN=64、F/D 开启 | 无寄存器，复位不适用 | 无握手 | 输出只依赖当前输入 | 无 | `io_ill` 为唯一异常输出 | 无状态；任意时刻可换输入 |
| `InstrBoundary` | 16 位槽；PC 不出现；`takenCfiOffset`/`totalEndPos` 为槽号 | 无（纯组合） | `FetchBlockInstNum=32`、`MaxFetchReqNum=2` | 无寄存器 | 无握手 | 所有输出对同一输入同拍有效 | flush 不适用（组合层） | 不产生异常，只报告 end mask 与半指令 | 无状态 |
| `PredChecker` | 51 位 `GuardedPc`（端口 `addr` 字段为 `[50:1]`）；`endOffset` 为块内槽号（5 位，回绕按字段宽度） | lane 身份由取指顺序决定，不从返回标签倒推 | `IBufferEnqueueWidth=36`，lane 35 由 IFU 置 0 | 异步复位清 `wbValid`；其余故障寄存器随 `io_req_valid` 更新 | 无 ready；请求 valid 保持时重定向按拍产生 | stage1 为组合截断，stage2 为下一拍重定向；同拍只能看 stage1 | 无 flush 端口；请求撤销后重定向在下一拍消失 | 首个违规优先：invalid-taken > 非 CFI-taken > 直接跳/间接跳/返回未预测；实现按 lane 顺序取首个 | 重定向可被后续请求覆盖；无跨拍完成义务 |
| `IfuUncacheUnit` | 47 位物理地址（端口 `addr` 字段为 `[46:1]`） | 单请求槽；请求身份=锁存地址 | PBMT 2 位、isMmio；FSM 4 态 | 异步复位回 Idle 并清数据/异常/地址 | 总线 ready 与 `ifuStall` 分别阻塞发射；响应恒 ready | 完成脉冲与回 Idle 同拍；完成当拍可接受新请求 | `flush` 在任意态立即回 Idle 并清脉冲；迟到响应丢弃 | corrupt→硬件错、denied→访问错、两者→访问错；干净→无异常 | 请求不因反压丢失；无完成时间保证，靠上层 watchdog |
| `FrontendTrigger` | 50 位 PC（端口 `addr` 为 `[49:1]`）；`tdata2` 为 64 位 CSR 字段，**比较必须使用全部 64 位**（当前 RTL 只用低 50 位，缺陷 R-13） | 4 个 trigger 索引 | `TriggerNum=4`；CSR 生成 before-execution timing，接口无 timing 端口 | 配置与使能寄存器清 0 | 无握手 | 配置更新下一拍生效；使能向量同样下一拍 | flush 不适用 | 动作优先级 debug > breakpoint（需 CSR 允许）> none | 无状态机；动作按拍重算 |
| `IfuPerfAnalysis` | 理由位编号 0..75；stage 为 3 级 | 按流水级身份传播 | 本配置只有 10 个理由位有驱动端口 | 复位清三级快照 | 无握手 | 输入快照 3 拍后到输出 | 无 flush；重定向仅覆盖理由位 | 不产生异常 | 无状态机；理由逐级替换 |
| `Ifu` | 取指窗口 32 槽；端口 PC 为 `GuardedPc[50:1]`，模型内为字节 PC；GPA 端口为字节地址 | FTQ 指针 + IBuffer 写指针；lane 身份由对齐决定 | `IBufferEnqueueWidth=36`、`AlignWidth=4`、`FetchPorts=2` | 异步复位；复位后首个有效周期不接收入队 | `toIBuffer.ready` 反压保持整拍；`ibufferEmpty/backendEmpty` 参与非缓存等待 | s0 接收、s1 组装/对齐、s2 展开/检查/入队；同拍 IBuffer beat 与 FTQ 重定向可同时出现 | backend redirect 与 BPU stage3 flush 清除在飞窗口；uncache flush 走独立重定向 | ICache 异常优先于 RVC 非法；GPF 另行写 GPA；跨页异常单独标记 | 被 flush 的窗口不承诺入队；重定向为单拍响应；无完成时间保证 |

`Ifu` 的 `toFtq.wbRedirect.pc` 在本基线固定 50 位，不能承载 `GuardedPc` 的 guard 位；
该限制由 `IFU-ENV-005` 记录，见 [上游差分复核](upstream-review-20261029.md)。

## 责任边界与上层承接

| 行为 | 本层责任 | 不在本层（承接层与状态） |
|---|---|---|
| 取指请求/响应握手时序 | `Ifu` 只对 `fromICache.req` 的 valid/ready 负责 | ICache MainPipe 的延迟与 miss 行为：由 ICache 工程验证；本工程用模型驱动请求 |
| 非缓存总线协议 | `IfuUncacheUnit` 只产生 `toUncache` 属性并消费响应 | InstrUncache/TileLink 的通道语义与顺序：未在本工程验证（out-of-domain） |
| IBuffer 写入/银行语义 | `Ifu` 保证 beat 有效位、对齐与 `prevInstrCount` | IBuffer 的 bank 写入/回绕与满判：由 IBuffer/后端验证；本工程只验证接口契约 |
| FTQ 重定向消费 | `Ifu` 产生重定向字段 | FTQ 如何训练与恢复：FTQ 工程；`IfuRedirectReceiver` 的 guard 重装见上游复核 |
| 后端调试动作 | `FrontendTrigger` 只标记 lane 动作 | 实际 breakpoint/debug 入口由后端在 pre-match 阶段决定 |
| Top-down 计数消费 | `IfuPerfAnalysis` 传播理由位 | 性能计数器的累加与上报：由性能分析/后端承接，未在本工程验证 |
| guard=1 的重定向 PC | 本基线 `pc` 端口 50 位，无法承载 | FTQ 侧重装；上游 `b716aade` 已修，本地未含 → 残余 `IFU-ENV-005` |

## 验证环境功能点（`IFU-ENV-*`，不计入硬件通过率）

| ID | 语义 | 对应检查 |
|---|---|---|
| 001 | 被综合删除的端口只能以显式常量声明读取/驱动；声明已存在的端口必须失败；每条声明可审计 | `tests/framework/test_pruned_ports.py` 的 `test_*` + `DutHarness.read_pruned/set_pruned` |
| 002 | 每个 DUT 比较器都能拒绝被篡改的期望/观测（负对照），也能拒绝四个“冻结的错误算法”，且未篡改时通过 | `tests/framework/test_checker_discrimination.py`、`tests/framework/test_oracle_independence.py` |
| 003 | 功能点与用例双向可追溯；每个组件至少一条完整实现记录（requirement/oracle/observations/controls/tests/residual），记录中的 nodeid 必须存在 | `tests/framework/test_traceability.py` 的 `test_*` + `verification_plan.json` 的 `metadata.traceability` |
| 004 | 非法窗口（对齐、压缩位、容量、carry-in、异常/属性范围）在夹具边界被拒绝；端口地址单位由 schema 固定 | `tests/framework/test_stimulus_legality.py` + `build_window` 校验 |
| 005 | 基线交接面限制被动态探测并以残余登记，不混入硬件 PASS | `tests/ifu/test_ifu_guard_handoff.py` + [上游复核](upstream-review-20261029.md) |
