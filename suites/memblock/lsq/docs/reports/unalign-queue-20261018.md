# UnalignQueue：跨页第二地址、恢复与同槽复用UT

## 结论

**当前固定配置独立UT通过：41/41用例、40/40语义checked、44/44原始本体DA行。** 仅验证2项UnalignQueue，不代表ForwardModule/PSQ/StoreQueue或LSQ整体通过；Load分支开放缺陷完整保留。

真实目标来自开源 `XiangShan @ 893e1580b705d81f113c30c7a05734e09a08050e` 的 `NewStoreQueue.scala:1430-1515`，单文件原始RTL259行，SHA `a19982ca4a2f60abf3428d60e6a30d3658304b8001c868b5fbd91b5e0d90b63b`。原样Picker导出与原生实例化走钟PASS见 `results/builds/20261018T075508771717Z-unalign_queue/report.json`。

## 合同与参考边界

[用例前合同](../contracts/unalign-queue.md) 先定义11类可读行为，再实现40种情形。19个实际输入（除clock）均由fixture绑定并被动解码。参考使用UID、SQ程序顺序、页号和接受/恢复账本，不读内部allocated/指针作oracle；公开forward槽位由独立接受序号mod2和取消数量回退推导。

- 只有完整addrReadyPtr与请求SQ精确匹配才可接受，first/second flag均参与；同时accepted输入必须one-hot，但双valid不同SQ允许只有一路接受。
- 满池消费当拍不立即接新项，和EnterSbufferQueue的同拍复用不同；空池无直通。
- 仅存paddr高36位，head/forward输出低12位清零，不误比较无效payload。
- SQ恢复取消包含cutoff本身的年轻后缀；当拍head valid不组合屏蔽，但普通Deq消费者不会消费同拍被恢复取消的未提交head。真实committed/ready依据与域外拒绝均在合同中列明。
- 取消情形checked必须等**同一物理槽位**的新UID实际head消费；reset中断不冒充正常消费或取消后复用成功。

## 首轮—逐行缺口—补例—重跑

| 运行 | 结果 | 本体DA行 | 语义checked |
|---|---:|---:|---:|
| `unalign-initial-01` | 3 PASS | 37/44，84.09% | 11/40 |
| **`unalign-expanded-01`** | **41 PASS** | **44/44，100%** | **40/40** |

首轮7条缺口逐项归为已有功能缺少情况，没有遗漏新的整体功能：156～159的第二物理槽页号/SQ保存4条，182～184的redirect尾部回退3条。原始needs_review清单保留，`line-audit-mapped.json`另存映射；补双项/双槽、满池、取消0/1/2项并同槽新身份完成后闭合全部可达行，没有删分母。

其余语义补例包括完整SQ旗标不匹配、双valid路由、同页/异页、页号36位walking one/zero、12位页内offset清零、512次顺序跨四圈/双槽回绕、恢复在所有flag边界、连续恢复、消费幸存head与取消年轻tail同拍、取消时输入阻断、单/双在途活动reset、禁用payload噪声，以及种子88/20261018各1200拍合法随机和最终排空。静态非法域拒绝不当作DUT动态检测覆盖。

## 证据门禁与独立历史审计

`tools/verify_run.py unalign-expanded-01 --require-semantic-complete --require-line-complete` 已通过：committed manifest、41 PASS、1原生构建、2个完整功能组、146份快照及全部artifact/build哈希。`source-consistency.json`确认启动146份文件结束时仍SHA一致。

`tools/audit_unalign_trace.py unalign-expanded-01` 不导入领域模型，按公开输入历史独立重建顺序队列、SQ年龄、页号与forward可见性：

- **5947连续记录＝5683非reset完整检查＋264 reset**，成功例全部排空。
- **1967分配＝1726真实head消费＋237取消＋4 reset中止**，无重复消费或漏记。
- 331满池阻塞拍、360满池消费但未偷接新项的拍、448合法同拍消费/新分配、455恢复拍均逐拍检查。
- 42次幸存head消费/年轻tail取消同拍，351次SQ匹配输入被当拍redirect阻断。
- 每个取消的旧UID都保留同槽新UID实际消费的journal、SHA、tick见证；两个入口×两个公开物理slot的4组合各有实际完成证明。
- 全部256种完整SQ编码均真实消费；页号36位的walking one/zero全部位置均由实际输出比较证明。

审计器另冻结在 `results/unalign-expanded-01/evidence-auditors/`；源码快照、原始失败/缺口历史不改写。只证明固定配置的实际功能及插桩DA，不是任意参数、父模块或形式化穷尽证明。

## 重现

在 `memblock-hash/lsq/` 使用新run名：

```sh
python3 -B tools/run.py --name <新名> --workers 1 -- tests/unalign
python3 -B tools/coverage_audit.py <新名>
python3 -B tools/verify_run.py <新名> --require-semantic-complete --require-line-complete
python3 -B tools/audit_unalign_trace.py <新名>
```

下一独立模块ForwardModule需覆盖真实UnalignQueue forward页输入的合法性/年龄/valid域及VA别名历史回归；在后续父级使用真实UnalignQueue硬件，不以参考队列替代。
