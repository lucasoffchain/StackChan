# Grok Build 与 StackChan 真实联调结果

已在本机完成真实 Grok Build 模型任务与 StackChan BLE 联动，用户确认看到了黄灯、蓝灯、短暂绿灯，任务退出后灯光变暗。

## Grok 角色与文字的新增验证（2026-11-11）

- 根据 [Grok Bot 官方应用页](https://play.google.com/store/apps/details?id=ai.x.grok.bot) 的球形角色和斜眼特征，用 LVGL 图元重绘角色，屏幕标题为实际监控对象 `GROK BUILD`。没有使用 xAI 的原始动画源码。
- 添加八种中文状态、明显的整体动作和状态符号，以及 15 秒无心跳后显示“连接已断开”的屏幕逻辑。中文使用带 OFL 许可证的 Noto Sans SC 字体子集。
- 与固件完全相同的 `GrokStatusView` 已用 LVGL 9.5.0 在 Windows 原生编译并渲染，覆盖八种状态、中文断线、重连、隐藏以及销毁后计时器运行。
- 屏幕预览：[状态总览](preview/grok-states.png)、[动画](preview/grok-demo.gif)。这两项是生产代码的主机渲染结果，并非实机截图。
- 桥接程序更新后的 23 项测试全部通过。
- USB 识别为 COM6、ESP32-S3，芯片 MAC `80:45:6b:4c:cc:34`；BLE 地址为同一设备的 `80:45:6B:4C:CC:36`。分区表与仓库一致。
- 原机 16 MB 闪存已完整备份到本机忽略目录 `.cache/stackchan-before-grok.bin`，未上传。SHA256：`b0c2e05f7991d4c8e70a3677f63a28109f178c6241250503bba0dcbf23b040d9`。
- 整机固件已使用 ESP-IDF 6.1 完整构建通过，应用镜像 3,805,136 字节，应用分区余量 27%。已通过 COM6 刷入 bootloader、分区表、OTA 初始数据、资源和应用镜像，全部写入后哈希校验通过。没有擦除 NVS 配置分区。
- DANCE 实机已连接，MTU 512。演示覆盖 thinking、working、waiting、done、error、offline、idle，并停发心跳 17 秒后恢复发送。全部状态写入收到 GATT 确认；用户明确确认“角色、中文和动画都看到了”。断线文字本身尚未单独取得用户目视确认。
- 新固件的真实任务：Grok 修复 `.cache/live-test/duration.py` 的时间格式化错误，初始 5 项测试中 3 项失败，修复后 5 项全部通过；独立重跑也通过。测试文件 SHA256 前后相同：`a1dbaedf7b7a076ce078d9ee02bcea9cdb0c8dfab932508a827c38160260080f`。
- 成功会话 `01a1c683-3381-7bb1-a0be-e8097de4a935`，4 个模型回合，`stopReason=end_turn`。真实任务期间 BLE 确认：01:30:52 思考、01:30:58 执行，后续多次思考／执行切换，01:31:26 完成、01:31:27 离线（本机时间）。
- 用户随后明确确认“看到了真实任务状态变化”，目视验证了真实 Grok 修复任务中角色与中文状态随“正在思考→正在执行→任务完成→已离线”切换。
- 首次尝试在 `search_replace` 要求编辑授权时被取消，真实 waiting 状态也收到 BLE 写入确认。给测试文件添加精确的 `Edit(...)` 规则后重试成功，没有使用全局自动授权或绕过权限。
- 新界面运行和真实任务期间，USB 日志没有出现 panic、abort、assert、重启或 JSON 解析失败。日志和完整任务输出只保存在已忽略的 `.cache` 内，临时 hooks 已清理。
- 测试用模型进程、USB 日志采集和 BLE 监控均已结束，没有安装后台服务。最后真实会话结束后显示 offline；停止监控后，Grok 视图按自身 15 秒超时显示断线。再次使用需保持 DANCE 并重新启动 BLE 监控与 Grok 启动器。

以下各节保留之前仅使用原有表情／RGB 协议的真实联调记录。

## 环境与安装

- 官方 Windows 稳定版：`grok 1.0.77 (50ca579fa996)`。
- 安装器来源：`https://x.ai/cli/install.ps1`，下载并检查后执行。
- 安装位置：`C:\Users\Bobo\.grok\bin\grok.exe`；用户 PATH 已添加 `C:\Users\Bobo\.grok\bin`。
- 已完成 xAI 官方账号授权，凭据由 Grok 自身保存在用户目录；本报告不包含凭据。
- 原生 Windows、Python 3.9、Bleak 1.1.1。
- 官方 StackChan，DANCE 应用，BLE 地址 `80:45:6B:4C:CC:36`。
- Grok 使用 Windows 已配置的本地代理 `http://127.0.0.1:7897`。仅为运行进程设置代理环境变量，没有修改系统代理。

## 真实任务

在 `.cache/live-test` 测试目录放置一个带折扣计算错误的 Python 函数及 5 项测试，让 Grok 实际读取代码、运行测试、修改 `pricing.py` 并重新测试。模型没有被要求生成机器人状态；状态全部由 CLI 的真实 hooks 产生。

- 初始结果：5 项测试中 2 项失败。
- 原始错误：将折扣百分比直接作为分减掉，2000 分打九折得到 1990；空订单打折得到负数。
- Grok 的修复：`(sum(prices) * (100 - discount_percent) + 50) // 100`，使用整数处理半分进位。
- Grok 运行后的结果：5 项测试全部通过。
- 独立复核：再次运行 `python.exe -m unittest -v`，5 项全部通过，测试文件没有改动。
- 真实会话：`01a1c635-a73b-71f2-9751-d550b79466af`。
- 最终 `stopReason`：`end_turn`，共 5 个模型回合。

## 状态链路证据

时间来自本机终端，以下为任务执行时的记录：

| 本地时间 | 真实事件 / 设备确认 |
| --- | --- |
| 00:06:08 | `SessionStart`，随后 `UserPromptSubmit` → thinking |
| 00:06:11 | BLE 确认写入 thinking |
| 00:06:23 | `PreToolUse` → working |
| 00:06:25 | BLE 确认写入 working |
| 00:06:27 | 工具结束 → thinking |
| 00:06:29 | BLE 确认写入 thinking |
| 00:07:09 | `Stop` → done |
| 00:07:12 | BLE 确认写入 done |
| 00:07:10 | `SessionEnd` → offline，监控发送完 done 后处理新状态 |
| 00:07:14 | BLE 确认写入 offline |

用户随后确认亲眼看到了相应的表情与灯光变化。

首次无交互尝试还触发了真实 `permission_prompt` → waiting 和 `StopCancelled` → idle。由于 headless 模式无法弹出授权，该次任务被取消。补充对 `Start-Sleep -Seconds 3` 和测试 Python 命令的精确允许规则后，第二次修复正常完成。waiting 事件非常短，该次没有确认机器人显示出紫灯，不作为紫灯的实机验证证据。

## 回归检查与边界

- 桥接程序的 18 项自动测试全部通过，包含 PowerShell hook 实际启动、事件日志不记录提示内容、BLE 分包、并行工具和退出清理。
- 临时 Grok hooks 已由启动器清理。
- 完整模型输出和生命周期日志保留在已忽略的 `.cache/live-test` 目录；生命周期文件 `events.jsonl` 不包含提示或工具结果。
- 真实验证覆盖思考、工具执行、完成和退出。没有把模型任务成功等同于所有状态分支均已实机测试。
- 当前固件在蓝牙链路自身断开时仍保留最后显示，不能独立检测电脑离线。
