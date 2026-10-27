# S4精确恢复的真实代际与miss后异常（逐行缺口补例前）

02实际72 PASS，345原UID闭环，但自身26994/59602与01相同，仍有32608行。已逐行
绑定原source/line/SHA和理由字典；Replay16249、VLQ4274、RAW2460、RAR1856、VSQ1809
等主要是已有身份/回收/重放功能缺slot/lane/flags/代际情形，不是把所有未命中笼统
判不可达。整个head-trap和Cache job关系遗漏与这些具体保存情形分开。

## S4P-EPOCH

保留原72节点，另三例各连续360个真实程序，不reset、不预置指针。每程序仍较老
Store+blocker Load+S4目标+年轻victim；所有Store真正Sbuffer消费/SQ释放、所有Load
完成或真实头部trap取消、每取消槽新UID正常完成，外部Cache job归零后才进入下一代。

360个Store遍历64物理槽与完整256编码；每程序实际推进3个LQ，完成120及240个程序
后各增加一个真实aligned filler Load，改变3步进余数，使目标真实遍历全部120物理
LQ槽/240编码。filler也须S0→S3与实际deq，不只是改计数。最终SQ360/LQ1082，ROB
绝对序从8到3610多次跨640；不声称覆盖所有640个ROB码的所有功能。

每个程序使用不同目标VA/PA页，避免在无声明SFENCE下对同一VA页切换PF权限。跨页
tail也有独立、不连续且不同于其他程序的PA；映射是S0前给定的外部TLB输入，检查
器独立核页内偏移、同页连续性和实际S1 PA，不冒称native TLB/DCache/ROB执行。

## S4P-MISS-FAULT

再补head Cache miss/tail AF（同页跨Cache line/跨页）和head miss/tail PF（仅跨页）
三关系×3lane=9例。相比原head nack/tail fault，它有真实外部head Cache job；须
先实际refill3、原grant/slot反馈，再保留tail异常产生WB/ROB头trap，不能把miss从
输入清掉就当数据已回来。三长流也包含这些关系。

## 紧凑但可核对的证据

独立checker新增程序请求窗口first/last tick及逐请求+2连续性，明确fixture boot和
首dispatch前无事务自主idle不在其窗口，由核心fixture检查。按每原UID保存终态和
同槽完成见证/Cache job计数，而非逐拍输入输出；Native摘要仍给完整流SHA。长流每
例只写一次终态JSON，默认0 JSONL/0wave。先核新增原UID与源关系，再核自身DA新增/
旧命中丢失并重分类剩行；不借旧53098或59595、不用小定向代替完整八类型随机。
