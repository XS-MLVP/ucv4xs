# 统一回归09：1882例1691 PASS/191 FAIL，精确重复门禁完成，整体NOT_PASS

**实际38个原生DUT、1882个节点：1691 PASS / 191 FAIL。** 运行结束后立即捕获
411份启动/结束源，全部一致。不是将门禁预期写成实测，也不是全LSQ验收。

```sh
python3 -B tools/run.py --name lsq-progress-regression-09 --workers 4 -- tests --tb=short
python3 -B tools/capture_end_sources.py lsq-progress-regression-09
python3 -B tools/coverage_audit.py lsq-progress-regression-09
python3 -B tools/audit_progress_run_v10.py lsq-progress-regression-09
```

原件位于`results/lsq-progress-regression-09/`；[v10证据](../../results/lsq-progress-regression-09/evidence-check-v10.json)
和[原DA清单](../../results/lsq-progress-regression-09/line-audit.json)均已实际产生。

## 已核验的具体证据

- 38 native build、76功能组，全部artifact/build/固定RTL/SHA核验。
- **1795份持久日志、346218条记录**的完整raw SHA多重集合与冻结基线精确相等。
- **1033个可用逐节点映射**精确相等；其余早期日志按完整多重集合核对。
- 基础87例没有持久逐拍JSON，只声明运行时检查/节点/结果/native/功能/源码证据。
- **191个普通FAIL主签名**在仅规范化进程地址后与基线相等，无skip/xfail。
- 每个DUT自己的原DA universe与命中集合等于其冻结基线，不跨叶子拼分子。

精确节点并集：其他36DUT来自`lsq-progress-regression-06`，LoadQueue199例来自
`lq-joint-impact-02`；Wrapper371例来自`lsq-expanded-16`的317例、`lsq-normal-cbo-03`
的34例、`lsq-serialized-cbo-01`的12例、`lsq-serialized-mixed-01`的8例。
Wrapper自身302 PASS/69 FAIL，LoadQueue187/12。

## 覆盖和生产者域不能混同

Wrapper本体114/114、闭包59595/59602；LoadQueue本体57/57、闭包50513/50520。
剩余窄证明不计命中、不删分母。Wrapper仅76/82 checked：SID复用、前拍release、
disabled strict和三个STRESS仍未checked；其他DUT失败/语义缺口详见v10原报告。

重复性通过不提高旧接口流的合法域：size3 CBO、仅QB而不串行的CBO，以及旧驱动
把RAR nuke转成C_NK、错拍/换lane S3和缺revoke的混合流，均保留原结果，不称完整
正常程序。v10沿用当时CBO包/许可门禁；完整LDU生产者拒绝依据以
[LDU-RAR纠正](lsq-ldu-rar-routing-20261019.md)及原UID-bound source-v3为准。
孤立正常串行CBO的实际WB错误/zero副作用反例仍由其独立定向证明。

## 与新增范围分界

正常LDU定向18例及新LDU混合8例不在09的411启动文件/1882节点中：前者15 PASS/3 FAIL，
后者2 PASS/6 FAIL，见[完整类型LDU混合报告](lsq-ldu-mixed-20261019.md)。须新目录扩大
统一回归，不能追溯写入09结果。合法联合容量/CBO分阶段、exact128合同/最小例、完整
随机及最终全请求审计仍必需。目标active，09完成的是精确回归门禁，不是整个目标。
