# 统一回归11：2036节点实际结束，NOT_PASS

## 真实结果与范围

`results/lsq-progress-regression-11/`完整运行`tests`，38个独立DUT，2036例：
**1821 PASS / 215 FAIL**。这不是门禁预期或后台启动状态；实际pytest/committed manifest、
结束源检查及`evidence-check-v12.json`已经核对。480启动/结束文件一致，原53开源RTL未改。

精确并集为回归10原1908 + exclusive75 + S3纠正26 + 联合/串行27，没有按失败筛选。
本轮后来新增的S4-02/03、plain01和诊断策略重跑不追溯混入2036范围。

## 实际独立门禁

- 1949份原始日志、410932条实际记录与四个原生基线的raw多重集合相等。
- 1118份日志有精确nodeid映射；其余早期记录不伪造nodeid。87基础例原fixture无持久raw。
- 全部215个普通FAIL的主要签名保持；没有xfail、skip或删掉原随机类型/种子。
- 38DUT各自原DA集合/命中与真实基线执行并集相等，不能按pytest目录漏算sq_endpoint
  中的RAW/Replay/Wrapper日志，也不把其他DUT的行命中挪作本DUT分子。
- 76功能组完整；Wrapper仍76/82 checked，SID、previous RAR、disabled Replay和三STRESS
  未验收。已通过叶子、body行满或局部正条件不构成父级或整体验收。

v12本次实测exit0只证明重复性/证据门禁，不将215个功能失败变成PASS。后续S4 fullva、
配置关闭的准确DCache错误、普通LD hyper/TL-D来源与ROB头精确trap的源准入限制继续
生效，旧接口输出/UID/DA是真实执行，但不能追溯称完整正常LDU程序。

## 用户纠正后的存储

逐拍JSON原来是LSQ自写fixture无条件开启，不是框架强制。本次完整轨迹审计已经完成；
后续普通回归默认仅小摘要，全量JSON和wave只显式、有限调试。统一11作为选定主基线
压缩按需复核；多数旧重复运行的全量日志与可重建wave/中间coverage实际删除，仅保留
源、JUnit/FAIL、命令、原DA报告和清理索引，不承诺保留全部旧路径或所有原件。

当前保留/删除状态看各目录`storage-index-v1.json`与`retired-intermediates-v1.json`。
需要重新执行旧审计时，对压缩主基线使用`tools/lsq_evidence_archive_v1.py audit`临时展开；
已退休中间原件只能按冻结源复现或映射到已验证的主基线，不能假称仍可直接读旧路径。

整体目标保持active：完整随机失败、S4合法异常/ROB头恢复、其他128与local-only旧响应
以及最终从请求到逐层功能/用例/实际检查/DA分类/补例/边界的完整审计仍未完成。
