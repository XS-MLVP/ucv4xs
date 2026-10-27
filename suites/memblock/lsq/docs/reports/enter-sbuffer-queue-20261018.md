# EnterSbufferQueue：真实消费credit与两项保序缓冲UT

## 结论

**当前固定配置独立UT通过：26/26用例，34/34语义checked，78/78原始本体DA行。** 这不是DeqModule/StoreQueue/LsqWrapper通过，也不消除Load分支的开放缺陷。

真实目标为 `EnterSbufferQueue`，2项/2输入/2输出，单文件闭包298行，固定SHA `35e3124ddb6624ff53c510e69e3c95f0bbdfd1f076dac42a292555297925e2ca`。开源基线与工具锁沿用本工程，不修改原始RTL。原生build和实例化走钟PASS见 `results/builds/20261018T074443100290Z-enter_sbuffer_queue/report.json`。

## 语义合同与独立检查

[用例前合同](../contracts/enter-sbuffer-queue.md) 先定义9类行为及34种情况，再开发用例：已提交写请求按接受顺序排队；满队列的容量复用取决于同拍真实Sbuffer消费；入队并不产生SQ释放；保存的credit只随实际Sbuffer fire报告。

合法域有实际生产者/消费者依据：DeqModule valid前缀及Sbuffer ready前缀。输出lane1若未消费但lane0消费，下一拍可压紧到lane0；测试不误要求固定lane保持。输入1的credit已编译为常量true，full/freeCount等端口删除，不虚构驱动或覆盖。reset中止旧UID，不算消费；仅有效payload比较，不把未初始化entry作为规格。

独立参考为按输入fire建立的UID列表和原payload/credit，不读内部allocated或指针；全部公开输入由被动monitor重新解码。每个DriveStable/RisingEdge，包括fixture切换空拍，都检查ready、valid、empty、有效payload和credit。

## 首轮—逐行分类—补例—重跑

| 运行 | 结果 | 本体DA | 语义checked |
|---|---:|---:|---:|
| `enter-sbuffer-initial-01` | 2 PASS | 61/78，78.21% | 7/34 |
| **`enter-sbuffer-expanded-01`** | **26 PASS** | **78/78，100%** | **34/34** |

首轮17条缺口全部为既有功能缺少情况：原SV131～136和147～152为输入1到两个物理槽的保存，共12条；155～159为输入0到槽1的保存，共5条。`line-audit-mapped.json`逐条保留，未排除可达行。补双项输入、奇数尾位置、部分接受/压紧、全满背压和同拍单/双出入后全部命中。

还补齐不由行覆盖保证的语义：拆分两半同拍/分拍消费仅一次credit、旧credit与同拍新credit不同、CBO.zero式无credit写、头项消费后尾项移动与背压、单/双项及回绕活动reset、禁用payload噪声、128/16/48/50位walking one/zero、连续160拍双宽、两个种子88/20261018各1000拍合法前缀并公平排空。7个非法前缀/宽度/删除字段编码仅静态拒绝，不虚称DUT动态检测。

## 证据审计

`tools/verify_run.py enter-sbuffer-expanded-01 --require-semantic-complete --require-line-complete` 已通过，核验committed manifest、26 PASS、1个原生build、2个完整功能组、136份冻结源码以及全部artifact/build/SHA。`source-consistency.json`确认启动136份文件结束时仍全部一致。

`tools/audit_enter_sbuffer_trace.py enter-sbuffer-expanded-01` 不导入领域模型，以公开日志独立重建FIFO、容量和credit：

- **4582条连续观察 = 4408条非reset完整检查 + 174条reset**，无漏拍、错误或未排空成功例。
- **4256次接受 = 4252次Sbuffer实际消费 + 4次reset中止**，每个UID最多消费一次。
- 4252次写请求消费中 **3295次产生SQ credit，957次不产生**；后者不是遗漏消费。
- 1661次双消费、588个全满阻塞拍、2079次同拍消费/接受、708个输出背压拍均按公开历史检查。
- 128位data、16位mask、48位paddr和50位vaddr全部walking one/zero位置均由实际完成的输出证明；4个首次输入lane→实际输出lane组合有UID/tick/journal/SHA见证。
- 不使用内部entry或指针作oracle，不宣称任意参数或Sbuffer/DeqModule内部算法已验证。

重现命令（run名必须换新）：

```sh
python3 -B tools/run.py --name <新名> --workers 1 -- tests/enter_sbuffer
python3 -B tools/coverage_audit.py <新名>
python3 -B tools/verify_run.py <新名> --require-semantic-complete --require-line-complete
python3 -B tools/audit_enter_sbuffer_trace.py <新名>
```

下一独立Store叶子为UnalignQueue；所有后续父块保留真实EnterSbufferQueue，而不是以Python FIFO替代硬件。
