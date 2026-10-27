# 集成 ABTB 场景迁移与完整刷新

本轮将已经隔离资格验证的五 alias 正向场景、四节点 true-final-NT 场景及其
index/write/SRAM 支撑迁入正常 pytest。不是把旧临时运行直接标为新生产 PASS。
旧 8197 项正式结果完整保留；当前完整收集为 10370 项，功能计划为 288 点。

## 分层与用法

正常测试仅表达意图，256 个正向 bank/set 和五个明确的 final-NT 坐标由参数化展开：

```python
await check_counter_case(agent, output, kind='five_alias', bank=2, entry_set=31)
await check_counter_case(agent, output, kind='final_not_taken', bank=2, entry_set=31)
```

- `alias_plan` / `final_not_taken_plan`：地址、容量、非零历史和输入资格；不依赖 provider
  hit 输出决定哪些输入可以接受。final-NT 使用实际两拍前的 C→D 索引 token。
- `alias_scenario` / `final_not_taken_scenario`：通过已有 agent/driver 发出真实预测、反馈和
  恢复事务；不使用测试级 edge/get_set 或内部状态写入。
- `WriteMonitor`：静态 Bundle 与 `@on` 被动观测 525 个 memory-direct 叶子。
- `WriteLineageReference` / `WriteChecker`：从 reset 和输入独立推导 T1/T2 分配、清理、
  四个写缓冲、完整 SRAM 写载荷和跨拍读响应。读请求对应下一 rising 的响应，不能
  拿同一次 sample 的输出作为该请求响应。
- `WriteObservation`：共用启动/异常关闭生命周期；正向预算 20000、final-NT 32768，
  不删帧或抽样规避超限。
- `check_counter_case`：场景正常退出、scope 关闭、bypass 和 counter 完整重放都成功后
  才发布 FC。每次执行保留唯一的无损 gzip 完整轨迹，重复 pytest 不覆盖旧见证。

## 两个新增功能点的边界

`BPU-INT-055` 要求所有 256 个物理 bank/set 的五 alias、十个真实 MainBTB resident、
完整 S3 输出、四 way 实际分配及不同第五 tag 的 way 复用，并验证真实递增/高保持及
同步 SRAM 全载荷读回。它不声称所有四 way 的全部计数迁移均发生。

`BPU-INT-056` 要求 (0,0)、(1,0)、(2,31)、(3,63)、(0,56) 五个坐标；A 的真实
fall-through 等于 B，不安装后项 taken fallback。每个 alias 执行正向/最终不取/正向
三个阶段，要求八种目标计数迁移、真实 taken=0 和完整 S3/SRAM 结果。它不声称全部
256 坐标或全部四物理 way 的负向矩阵闭合。

两点登记使计划从 286 变为 288；旧正式功能结果仍为 279/286，不能因为登记或
collect-only 就增加 PASS。完整物理更新路径分母仍是 12288，不裁掉低 way 缺口。

## 本轮已经取得的证据

- 原合格回执固定的 14 个生产模块、7 个测试模块来源 SHA 均核对通过。
- 11 个模块仅移动导入/命名，算法 AST 不变；另三处只允许观测预算、场景命名、
  历史报告字段、无损序列化和延迟发布的明确变化。14 个模块的完整迁移 AST 门禁和
  await 顺序检查全部通过，未调用只接受旧源码纪元的 `native_gate`。
- 3263 项模型/契约回归实际通过；包含完整 bank/set、T1/T2、writebuffer、SRAM 关联、
  输入资格、trace IO、失败不发布和迁移反例。
- 四个跨 bank/set 正向、两个 final-NT 的真实生产测试由六个 worker 执行，实际 6 PASS。
  六份完整新观测重放及源码/旧证据身份最终检查已全部成功，迁移资格整体退出 0。
  独立标准库导出审查也退出 0，六份实际 FC 的 48 个数据故障均被拒绝；路径 bin
  分别为正向 8/8/8/6、final-NT 32/18，完整分母始终为 12288。
- 当前完整 collect-only 实际 10370 项，新 DUT 参数项恰好 261；四正式报告身份不变。
- 正式刷新前已归档完整旧 results 加源纪元/旧计划，共 3950 个成员、25352164627 字节。
  归档 1019124327 字节，逐成员内容与原文件 SHA 全部一致；无原文件删除。

## 完整刷新如何执行

控制器位于 `/tmp/bpu-current-hybrid-full-yNJUjc`，已在迁移资格实际退出 0 后启动。
当前 owner 2655665、串行 pytest 2655922、并行 controller 2655921 及八个 worker
均已核实存活；完整回归尚未终态，不能提前宣称以下合并完成：

1. 原套件及新增纯模型共 10109 项由正常串行 pytest 执行。
2. 新矩阵 261 项导入原生产函数，由八个独立 pytest worker 执行；DUT、raw、FC 和
   完整轨迹按 worker/node 隔离到唯一 run 目录。
3. 合并器逐项核对 setup/call/teardown、用例集合、feature/test 映射、worker 回执和
   原生/FC 身份。两部分的无交集并集必须恰好等于完整 10370 项收集；七个 strict
   XFAIL 身份不能丢失，XFAIL/异常不能被同功能点的 PASS 掩盖。
4. 仅合并本轮实际生成的 raw/FC，不读取隔离旧候选来增加正式行；原生行分母必须
   与旧正式各模块一致。全部完成后刷新 JSON/LCOV/HTML，并替换过期的 summary。

合并门禁已有 15 项反例/正例通过。准备、实际启动和终态分别以 launch、live、exit
回执为准，不能把已排队写成已通过。低于 80.5 GiB 停止接纳下一用例，保留所有证据。
即使刷新成功，也还需完整新动态审计，不能直接将整体目标标为 complete。

## 保留的未完成范围

所有四 way 的两种递减原因与高/低保持、真实同 cell reset 竞争、deep SC-used、
full dirty overwrite、真实 overlap、完整 FTQ，以及既有七项 strict XFAIL 对应的
六个 RTL 问题，均仍在原目标范围内。候选 3774 行、独立 ABTB 的 100% 和旧功能
覆盖均值 99.2058% 都不能代替这些需求。
