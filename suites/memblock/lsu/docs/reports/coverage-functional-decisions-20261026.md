# 覆盖率、功能点分组与Bug是/否判定（2026-10-26）

覆盖率数字绑定 `failure-recheck-final-03`（582 PASS / 1 FAIL）；上游核查后当前回归 `upstream-review-regression-02` 为 **582 PASS / 7 FAIL**。覆盖分母未变。**是/否只回答表头的具体命题；证据不足不能伪写成不存在Bug。**

## 1. 逐DUT覆盖率与功能bin

| DUT | 行 | branch | toggle | 功能bin命中/总数 | 交叉bin | 分组数 | 采样数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| store_arbiter | 32/32 | 62/62 | 1126/1128 | 26/26 | 39/39 | 3 | 3926 |
| store_trigger | 48/48 | 16/16 | 762/762 | 32/32 | 0/0 | 1 | 37 |
| store_delay | 29/29 | 5/6 | 978/978 | 18/18 | 0/0 | 1 | 20 |
| store_s0 | 83/83 | 67/68 | 3090/3100 | 47/47 | 0/0 | 1 | 63 |
| store_s1 | 86/86 | 30/31 | 3836/3872 | 63/63 | 0/0 | 1 | 67 |
| store_s2 | 32/32 | 5/6 | 1042/1042 | 28/28 | 0/0 | 1 | 30 |
| store_s3 | 51/51 | 10/12 | 2502/2506 | 26/26 | 0/0 | 1 | 28 |
| store_s4 | 0/0 | 0/0 | 572/572 | 5/5 | 0/0 | 1 | 7 |
| new_store_unit | 242/257 | 111/119 | 13231/13964 | 22/22 | 0/0 | 1 | 26 |
| std_exe_unit | 11/11 | 12/12 | 1058/1058 | 22/22 | 0/0 | 1 | 26 |
| load_arbiter | 195/195 | 346/346 | 3702/3702 | 22/22 | 0/0 | 1 | 24 |
| load_trigger | 33/33 | 10/10 | 762/762 | 30/30 | 0/0 | 1 | 31 |
| load_datapath | 122/122 | 17/18 | 3928/3928 | 21/21 | 0/0 | 1 | 26 |
| load_s0 | 285/285 | 387/388 | 8546/8582 | 35/35 | 0/0 | 1 | 44 |
| load_s1 | 128/128 | 33/34 | 6338/6376 | 36/36 | 0/0 | 1 | 37 |
| load_s2 | 108/108 | 5/6 | 4234/4280 | 44/44 | 0/0 | 1 | 46 |
| load_s3 | 84/84 | 55/56 | 5400/5408 | 40/40 | 0/0 | 1 | 44 |
| load_s4 | 0/0 | 0/0 | 1168/1168 | 6/6 | 0/0 | 1 | 8 |
| new_load_unit | 762/762 | 502/508 | 39686/40024 | 25/25 | 0/0 | 1 | 42 |

共21个covergroup、23个coverpoint、548/548个普通bin、39/39个交叉bin。采样事件共4532，不是唯一事务数。0/0表示无该类插桩，不写成100%。

## 2. 功能点语义分组与数据

叶子按原bin前缀、store仲裁按实际coverpoint/交叉分组；父块按原bin语义做穷尽互斥映射。139个展示子组不是新增covergroup，不重新定义原分母。

| DUT | 语义子组 | bin命中/总数 | 命中事件总数 |
|---|---|---:|---:|
| store_arbiter | 仲裁拍型（beat_kind） | 4/4 | 683 |
| store_arbiter | 标量反压（scalar_ready） | 2/2 | 683 |
| store_arbiter | 载荷字段组（payload_group） | 13/13 | 3239 |
| store_arbiter | 载荷位型（shape） | 3/3 | 3239 |
| store_arbiter | 字段组×位型交叉（cross:group_x_shape） | 39/39 | 3239 |
| store_arbiter | 源隔离（isolation_case） | 4/4 | 4 |
| store_trigger | 触发动作（action） | 4/4 | 7 |
| store_trigger | 缓存块操作（cbo） | 4/4 | 4 |
| store_trigger | 触发链（chain） | 5/5 | 5 |
| store_trigger | 触发门控（gate） | 4/4 | 4 |
| store_trigger | 多槽触发（multi） | 4/4 | 4 |
| store_trigger | 优先级（priority） | 1/1 | 1 |
| store_trigger | 标量（scalar） | 7/7 | 9 |
| store_trigger | 向量（vector） | 3/3 | 3 |
| store_delay | 接口边界（boundary） | 2/2 | 2 |
| store_delay | 时序延迟（delay） | 6/6 | 8 |
| store_delay | ROB半项顺序（former） | 2/2 | 2 |
| store_delay | 取消/过滤（kill） | 3/3 | 3 |
| store_delay | 重定向级别（level） | 1/1 | 1 |
| store_delay | 重定向（redirect） | 2/2 | 2 |
| store_delay | 环形绕回（wrap） | 2/2 | 2 |
| store_s0 | 地址就绪（addrready） | 2/2 | 2 |
| store_s0 | 对齐（align） | 5/5 | 11 |
| store_s0 | 仲裁（arb） | 4/4 | 4 |
| store_s0 | 跨页（cross4k） | 4/4 | 8 |
| store_s0 | 非法发射（illegal） | 4/4 | 4 |
| store_s0 | 取消/过滤（kill） | 6/6 | 6 |
| store_s0 | 流水寄存/传递（pipe） | 5/5 | 7 |
| store_s0 | 标量（scalar） | 6/6 | 6 |
| store_s0 | 地址翻译（tlb） | 8/8 | 8 |
| store_s0 | 未对齐头段（unalignhead） | 3/3 | 7 |
| store_s1 | 异常（exc） | 7/7 | 10 |
| store_s1 | 反馈（feedback） | 9/9 | 9 |
| store_s1 | 取消/过滤（kill） | 10/10 | 10 |
| store_s1 | LFST依赖更新（lfst） | 4/4 | 4 |
| store_s1 | 依赖冲突查询（nuke） | 5/5 | 5 |
| store_s1 | 流水寄存/传递（pipe） | 4/4 | 5 |
| store_s1 | 队列交接（queue） | 4/4 | 4 |
| store_s1 | SQ地址（sqaddr） | 8/8 | 8 |
| store_s1 | 尾段/头尾合并（tail） | 5/5 | 5 |
| store_s1 | 地址翻译（tlb） | 4/4 | 4 |
| store_s1 | 触发器（trigger） | 3/3 | 3 |
| store_s2 | 异常（exc） | 9/9 | 10 |
| store_s2 | 头段（head） | 1/1 | 1 |
| store_s2 | 内存属性（memtype） | 9/9 | 9 |
| store_s2 | 流水寄存/传递（pipe） | 6/6 | 7 |
| store_s2 | SQ重执行（sqre） | 3/3 | 3 |
| store_s3 | 时序延迟（delay） | 10/10 | 12 |
| store_s3 | 异常（exc） | 4/4 | 4 |
| store_s3 | 混合情形（mix） | 3/3 | 3 |
| store_s3 | 流水输出（pipeout） | 6/6 | 6 |
| store_s3 | Store写回（stout） | 3/3 | 3 |
| store_s4 | 直通保真（pass） | 5/5 | 7 |
| new_store_unit | 发射/优先级/顺序（发射/优先级/顺序） | 3/3 | 4 |
| new_store_unit | 未对齐/跨页/尾段（未对齐/跨页/尾段） | 3/3 | 3 |
| new_store_unit | 异常/触发器/设备访问（异常/触发器/设备访问） | 3/3 | 3 |
| new_store_unit | 翻译/反馈/重放（翻译/反馈/重放） | 4/4 | 5 |
| new_store_unit | 取消/依赖/空闲（取消/依赖/空闲） | 4/4 | 6 |
| new_store_unit | 写回/预取/向量（写回/预取/向量） | 5/5 | 5 |
| std_exe_unit | 反馈（feedback） | 5/5 | 5 |
| std_exe_unit | ROB身份（rob） | 1/1 | 2 |
| std_exe_unit | SQ窗口/数据（sq） | 5/5 | 6 |
| std_exe_unit | 有效位/分流（valid） | 11/11 | 13 |
| load_arbiter | 仲裁（arb） | 8/8 | 9 |
| load_arbiter | 入口编码（entrance） | 3/3 | 4 |
| load_arbiter | 字段保真（field） | 7/7 | 7 |
| load_arbiter | 源隔离（isolation） | 1/1 | 1 |
| load_arbiter | 就绪/背压（ready） | 3/3 | 3 |
| load_trigger | 触发动作（action） | 4/4 | 4 |
| load_trigger | 缓存块操作（cbo） | 1/1 | 1 |
| load_trigger | 触发链（chain） | 4/4 | 4 |
| load_trigger | 触发门控（gate） | 4/4 | 4 |
| load_trigger | 多槽触发（multi） | 4/4 | 4 |
| load_trigger | 预取抑制（prf） | 2/2 | 2 |
| load_trigger | 优先级（priority） | 1/1 | 1 |
| load_trigger | 标量（scalar） | 7/7 | 8 |
| load_trigger | 向量（vector） | 3/3 | 3 |
| load_datapath | 符号/零/浮点扩展（extend） | 6/6 | 10 |
| load_datapath | 数据源合并优先级（merge） | 8/8 | 9 |
| load_datapath | 元数据寄存（meta） | 2/2 | 2 |
| load_datapath | 字节偏移（rotate） | 2/2 | 2 |
| load_datapath | 尾段/头尾合并（tail） | 2/2 | 2 |
| load_datapath | 有效位/分流（valid） | 1/1 | 1 |
| load_s0 | 对齐（align） | 4/4 | 12 |
| load_s0 | 仲裁（arb） | 2/2 | 2 |
| load_s0 | 跨bank（crossbank） | 1/1 | 1 |
| load_s0 | DCache请求/取消（dcache） | 3/3 | 3 |
| load_s0 | 前递（fwd） | 4/4 | 4 |
| load_s0 | 128位请求（is128） | 2/2 | 2 |
| load_s0 | 入口合成（lane） | 5/5 | 6 |
| load_s0 | 入口年龄顺序（order） | 4/4 | 4 |
| load_s0 | 性能事件等价检查（perf） | 1/1 | 1 |
| load_s0 | 寄存器保持（reg） | 2/2 | 2 |
| load_s0 | 地址翻译（tlb） | 4/4 | 4 |
| load_s0 | 唤醒（wakeup） | 3/3 | 3 |
| load_s1 | 数据通路元数据（datapath） | 1/1 | 1 |
| load_s1 | DCache请求/取消（dcache） | 1/1 | 1 |
| load_s1 | 异常（exception） | 2/2 | 2 |
| load_s1 | 前递（forward） | 1/1 | 1 |
| load_s1 | 取消/过滤（kill） | 7/7 | 7 |
| load_s1 | 性能事件等价检查（perf） | 1/1 | 1 |
| load_s1 | 预取（prefetch） | 2/2 | 2 |
| load_s1 | 寄存器保持（reg） | 2/2 | 2 |
| load_s1 | 重放（replay） | 6/6 | 6 |
| load_s1 | 尾段/头尾合并（tail） | 3/3 | 4 |
| load_s1 | 地址翻译（tlb） | 7/7 | 7 |
| load_s1 | 触发器（trigger） | 3/3 | 3 |
| load_s2 | 重放原因（cause） | 13/13 | 13 |
| load_s2 | DCache请求/取消（dcache） | 1/1 | 1 |
| load_s2 | 异常（exception） | 6/6 | 6 |
| load_s2 | 快速重放（fastreplay） | 5/5 | 5 |
| load_s2 | 前递（forward） | 6/6 | 6 |
| load_s2 | 取消/过滤（kill） | 2/2 | 3 |
| load_s2 | 前递匹配无效（matchinvalid） | 1/1 | 1 |
| load_s2 | 依赖查询（nukequery） | 2/2 | 2 |
| load_s2 | 性能事件等价检查（perf） | 1/1 | 2 |
| load_s2 | 预取训练（prefetchtrain） | 1/1 | 1 |
| load_s2 | 寄存器保持（reg） | 1/1 | 1 |
| load_s2 | RR bank冲突（rrbank） | 1/1 | 1 |
| load_s2 | 非缓存访问（uncache） | 2/2 | 2 |
| load_s2 | 唤醒（wakeup） | 2/2 | 2 |
| load_s3 | 取消/合并取消（cancel） | 3/3 | 3 |
| load_s3 | 头尾载荷拼接（concat） | 4/4 | 4 |
| load_s3 | 异常（exc） | 2/2 | 2 |
| load_s3 | 异常地址信息（excinfo） | 2/2 | 2 |
| load_s3 | 取消/过滤（kill） | 1/1 | 1 |
| load_s3 | LQ/原因编码（lq） | 12/12 | 13 |
| load_s3 | 寄存器保持（reg） | 1/1 | 1 |
| load_s3 | 重放（replay） | 4/4 | 4 |
| load_s3 | 寄存器文件写（rfw） | 5/5 | 7 |
| load_s3 | 顺序违例回滚（rollback） | 3/3 | 3 |
| load_s3 | 写回（wb） | 3/3 | 4 |
| load_s4 | 直通保真（pass） | 6/6 | 8 |
| new_load_unit | 数据/合并/写回（数据/合并/写回） | 6/6 | 11 |
| new_load_unit | 背压/仲裁/重放（背压/仲裁/重放） | 5/5 | 7 |
| new_load_unit | 取消/异常/触发器（取消/异常/触发器） | 5/5 | 6 |
| new_load_unit | 非缓存/空闲（非缓存/空闲） | 2/2 | 3 |
| new_load_unit | 依赖查询/回滚（依赖查询/回滚） | 3/3 | 8 |
| new_load_unit | 预取/训练/性能（预取/训练/性能） | 4/4 | 7 |

## 3. 功能数据的检查边界

全部普通bin与cross已采样达标；这是工具100%的含义。逐bin独立reached/checked认证：**否**，不是说所有行为都没测。可追到测试字面量的引用保留在CSV，静态引用也不等于动态检查证明。

新增硬件预取miss规范测试单列：2个参数情形，均实际执行并检查；hit=0情形PASS、miss=1情形FAIL。它们没有偷偷并入旧bin分母。因此不能用旧功能100%掩盖1个真实FAIL。

## 4. 每项已确认缺陷的是/否

RTL列的否表示该条是验证/报告缺陷而不是一项已确认RTL缺陷，不代表整个模块无Bug。日志问题修复闭环=否：后续采集已修正，但历史日志不能恢复。

| ID | 问题 | 确认RTL Bug | 确认验证/报告Bug | 修复闭环 |
|---|---|---|---|---|
| LSU-HWPF-MISS-001 | 硬件预取miss性能事件恒0 | 是 | 否 | 否 |
| VER-ASSERT-001 | 三处恒真断言 | 否 | 是 | 是 |
| VER-TAIL-001 | S1尾段身份未统一检查 | 否 | 是 | 是 |
| VER-INPUT-001 | 错误输入键被静默忽略 | 否 | 是 | 是 |
| VER-DATAPATH-001 | 头尾数据合并激励和独立检查不足 | 否 | 是 | 是 |
| VER-REACH-001 | 22个可达toggle误归为不可达 | 否 | 是 | 是 |
| VER-NATIVE-001 | factory创建DUT未自动登记覆盖 | 否 | 是 | 是 |
| VER-LOG-001 | 旧运行未保存逐节点日志与源码版本 | 否 | 是 | 否 |
| VER-SCHEMA-001 | 本轮新增schema曾拒绝真实bypass数据键 | 否 | 是 | 是 |
| VER-SENS-001 | 本轮故障对照脚本的测试名和挂接点错误 | 否 | 是 | 是 |
| VER-SWPREF-001 | 新增软件指令预取训练有效位预期错误 | 否 | 是 | 是 |
| VER-FCOV-001 | 把手动bin100%当成独立reached/checked闭环 | 否 | 是 | 否 |

## 5. 历史记录的二元证据结论

不能从缺日志推导没有RTL Bug。下面给出明确的是/否：是否足以裁定、是否确认RTL Bug、是否已排除RTL Bug；不把后一列的否当成确认有Bug。

| run | FAIL观测数 | 证据足以裁定 | 确认RTL Bug | 已排除RTL Bug |
|---|---:|---|---|---|
| load-s3-initial-01 | 1 | 否 | 否 | 否 |
| new-load-unit-final-02 | 1 | 否 | 否 | 否 |
| new-load-unit-final-03 | 1 | 否 | 否 | 否 |
| new-load-unit-final-05 | 3 | 否 | 否 | 否 |
| store-arbiter-initial-02 | 11 | 否 | 否 | 否 |
| store-delay-shared-ptr-01 | 0 | 是 | 否 | 是 |

前5个run共17次FAIL不能恢复逐nodeid根因；裁定证据是否充足=否。这不是‘Bug是否存在=否’。这些记录的报告处理结论为：证据不满足认定门槛，不计为确认Bug；并非宣告RTL无缺陷。收集失败run在native DUT执行前失败，不计成其RTL功能Bug。

## 6. 可核对的数据文件

- `review/failure_recheck_20261026/coverage-functional/data.json`：全部数据、输入SHA、分组和明确布尔字段。
- 同目录 `coverage-per-dut.csv`、`functional-bins.csv`、`bug-decisions.csv`、`historical-evidence-decisions.csv`：逐项原始数字。
- 同目录 `all-functional-bins.md`：每个普通/交叉bin完整名称、命中次数、门槛与达标是/否。
- `docs/bug-reports-20261026/README.md`：根因、源码、复现与证据限制。

本次只生成展示数据，没有重跑已完成仿真，没有修改目标RTL、测试、覆盖bin或原结果目录。

## 7. 上游核查追加的6个RTL Bug

| ID | 问题 | 确认RTL Bug | 已复现 | 修复闭环 |
|---|---|---|---|---|
| `LSU-STORE-TVAL-001` | Store故障tval未用TLB指针掩码地址 | **是** | 是，原生DUT | 否 |
| `LSU-CBO-NC-AF-001` | PBMT=NC的CBO误报Store AF | **是** | 是，原生DUT | 否 |
| `LSU-S3-KILL-WB-001` | redirect kill的S3 Load仍写回 | **是** | 是，原生DUT | 否 |
| `LSU-MATCHINV-CAUSE-001` | matchInvalid回写仍带replay cause | **是** | 是，原生DUT | 否 |
| `LSU-PREFETCH-W-INTENT-001` | prefetch.w丢失写意图 | **是** | 是，原生DUT | 否 |
| `LSU-STD-PERF-001` | StdExe越界发射计数器取反 | **是（仅性能）** | 是，固定源码静态检查 | 否 |

加上 `LSU-HWPF-MISS-001`，确认RTL Bug总数为 **7**。详细上游依据、排除项与证据见 `docs/bug-reports-20261026/05-upstream-review-20261026.md` 和 `review/upstream_check_20261026_01/audit.json`。
