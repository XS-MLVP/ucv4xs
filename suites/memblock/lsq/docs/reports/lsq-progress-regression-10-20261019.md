# 统一回归10：1908例1708 PASS/200 FAIL，实际结束、重复性审计完成

**38个真实原生DUT，1908节点，1708 PASS / 200 FAIL，整体NOT_PASS。** 结束后捕获
430份启动源，全部一致；不是此前的门禁预期，也不将后续75例/26例追溯混入。

```sh
python3 -B tools/run.py --name lsq-progress-regression-10 --workers 4 -- tests --tb=short
python3 -B tools/capture_end_sources.py lsq-progress-regression-10
python3 -B tools/coverage_audit.py lsq-progress-regression-10
python3 -B tools/audit_progress_run_v11.py lsq-progress-regression-10
```

## 真实范围与核验

- 精确并集：回归09原1882节点＋LDU-RAR原18节点＋LDU混合原8种子，未删失败节点。
- [v11原证据](../../results/lsq-progress-regression-10/evidence-check-v11.json)核验
  **1821份日志/351451条公开记录**的完整raw多重集合、**1059个逐节点映射**；早期
  无nodeid日志不虚构节点映射，基础87例无持久逐拍JSON，保留运行时检查证据边界。
- 200个FAIL主签名与各自冻结基线相等，无skip/xfail；每个DUT原DA全集与命中集合
  独立相等，不跨子块拼分子。38 build/76功能组与产物SHA门禁完成。
- [本次原DA](../../results/lsq-progress-regression-10/line-audit.json)仍保留分母：
  Wrapper59595/59602、LoadQueue50513/50520；Wrapper76/82 checked，不能因接近满行
  而通过SID复用、前拍release、disabled strict或三个STRESS。

## 生产者域限制仍有效

该重复性审计不是正常LDU准入。后续S3源关系审计已拒绝旧LDU定向的默认size/
lastBeat及旧混合171次明确Replay伪地址更新；旧联合满池还缺原生S3/revoke及CBO
NoSpec/BlockBack。旧接口效应、UID、DA和普通FAIL真实保留，但不能称完整正常程序。

之后另跑的新26例见[S3纠正报告](lsq-ldu-s3-20261019.md)：17/9、458源、762次S3
源关系检查，全部实际输出和9个失败终点保持。新75端点见[exclusive报告](lsq-raw-exclusive-20261019.md)。
两批不在本次430启动文件/1908节点内。合法联合容量/CBO分阶段、完整随机/fair恢复、
未生成S4异常域和扩大全范围回归及最终请求→证据审计仍必需，目标保持active。
