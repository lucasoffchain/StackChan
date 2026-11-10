# 用 StackChan 监控 Grok Build

适用于本仓库对应的 M5Stack 官方 StackChan。电脑通过 BLE 发送状态，机器人停留在 **DANCE** 应用。原有五官和 RGB 控制可以直接使用现有固件；**Grok 球形角色与中文状态文字需要本次新增的固件功能**。运行时不需要连接 Wi-Fi 或启动云服务。

数据路径：Grok Build hooks → 本地状态文件 → Python/Bleak → StackChan 表情和 RGB。

## 平台与设备选择

电脑端使用跨平台的 Bleak 蓝牙库，启动器已包含 Windows 与 macOS/Linux 的文件锁及 Shell 命令处理。**目前完整实机联调只在 Windows 上完成，macOS 和 Linux 尚未实机验证。** 三个平台复用同一份机器人固件，更换电脑系统无需重新刷机。

Grok Build 和 BLE 监控程序应运行在同一台电脑、同一系统，使用同一个本地状态文件；当前不包含 WSL、容器或远程主机的状态与蓝牙转发。各平台命令见下方的 [Windows 快速开始](#windows-快速开始) 和 [macOS 与 Linux 快速开始](#macos-与-linux-快速开始)。

**如果只扫描到一台 StackChan，`monitor` 命令可以省略 `--address DEVICE_ID`，程序会自动扫描并连接。** 例如，macOS/Linux 可直接运行：

```bash
tools/bot-monitor/.venv/bin/python tools/bot-monitor/monitor.py monitor \
  --status-file tools/bot-monitor/status.json --skin grok
```

扫描到多台时，程序要求通过 `--address` 显式指定目标；扫描不到时会提示并重试。这里的自动选择只适用于 `monitor` 子命令，单次显示 `show` 和表情演示 `expressions` 仍需提供 `--address`。

## Grok 角色与中文状态

更新固件后，启动监控时添加 `--skin grok`：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py monitor --address 80:45:6B:4C:CC:36 --status-file tools/bot-monitor/status.json --skin grok
```

屏幕同时显示 `GROK BUILD`、按 Grok Bot 球形角色特征重绘的角色、中文状态。思考时左右看，执行时伸缩跳动，等待时显示问号，完成时短暂弹跳并显示勾号，报错时短暂摇动并显示感叹号，离线时压扁闭眼。动画每 50 ms 在机器人本地更新，BLE 只需发送状态和心跳。状态颜色也作用于文字和 LED。

`--skin grok --text en` 切换为英文。中文字体是 Noto Sans SC 的精简子集，包含八种固定状态及断线消息，**不支持任意中文长句**。字体来源和许可证保存在 `firmware/main/assets/fonts`。角色视觉参考与生产代码的原生 LVGL 渲染方式见 [预览说明](preview/README.md)。

单次显示（15 秒没有继续收到监控更新后，Grok 视图会自动变为断线）：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py show thinking --address 80:45:6B:4C:CC:36 --skin grok
```

恢复原有 StackChan 五官界面：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py show idle --address 80:45:6B:4C:CC:36 --skin default
```

新增表情 JSON 字段为 `{"monitor":{"skin":"grok","state":"thinking","text":"正在思考"}}`，与原有 eyes/mouth 字段共存。`skin=default` 隐藏监控视图。普通表情也可添加 `speech`（最多 192 字节）、`title`（最多 48 字节）和 `modifyLock`；旧固件会忽略这些新字段。固件编译使用仓库要求的 ESP-IDF 6.1，见 [固件构建说明](../../firmware/README.md)。

## Windows 快速开始

需要原生 Windows Python 3.9+、支持 BLE 的蓝牙适配器和已安装并可用的 `grok` 命令。蓝牙桥接应在原生 Windows 运行；此版本的启动器也要求 Grok 在同一系统运行，不包含 WSL 状态转发。

本机已通过 xAI 官方安装器安装 Grok Build 1.0.77，路径为 `C:\Users\Bobo\.grok\bin\grok.exe`，用户 PATH 已添加对应目录。安装后新开的终端可直接使用 `grok`。首次使用需要 `grok login --device-auth`，并在其提供的 xAI 官方页面完成授权。

如果 Windows 浏览器能访问登录服务、Grok 却直连超时，可让当前终端使用 Windows 已配置的代理。本机当前代理为 `127.0.0.1:7897`（只在该代理服务运行时使用）：

```powershell
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
$env:HTTP_PROXY = 'http://127.0.0.1:7897'
grok login --device-auth
```

这些设置仅影响当前终端及其子进程，没有修改系统代理。运行 Grok 启动器的终端也需使用可访问 xAI 服务的网络。

以下命令从仓库根目录执行。首次安装：

```powershell
python -m venv tools/bot-monitor/.venv
.\tools\bot-monitor\.venv\Scripts\python.exe -m pip install -r tools/bot-monitor/requirements.txt
```

1. 在电脑上开启蓝牙，在 StackChan 上打开 **DANCE** 并保持该应用运行。断开手机 App 对它的连接。
2. 扫描设备：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py scan
```

3. 先用演示模式验证表情和灯光。将地址替换为扫描输出的实际地址，按 Ctrl+C 结束：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py monitor --address AA:BB:CC:DD:EE:FF --demo
```

4. 在第一个终端启动 BLE 监控：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py monitor --address AA:BB:CC:DD:EE:FF --status-file tools/bot-monitor/status.json
```

如果只扫描到一台 StackChan，可以省略 `--address`，由程序自动扫描并连接。对应的 Grok 角色监控命令为：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py monitor --status-file tools/bot-monitor/status.json --skin grok
```

扫描到多台时，必须使用 `--address` 指定目标。

5. 在第二个终端，通过启动器打开 Grok：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/grok_bridge.py run -- grok
```

启动器保留 Grok 的交互终端，在**当前工作目录**创建独立的临时 `.grok/hooks/stackchan-monitor-<随机标识>.json`，退出后删除该文件。已有 hooks 文件不会被覆盖。Grok 的项目 hooks 需要项目信任：如果没有触发状态变化，请在 Grok 中运行 `/hooks` 检查加载情况，并按 Grok 的提示使用 `/hooks-trust` 信任你正在使用的项目，然后重新启动。未收到事件前显示 `unknown`，不会把仅启动进程判为成功。

要在其他项目中使用，先切换到目标项目，再用绝对路径启动本工具：

```powershell
Set-Location E:\your-project
& 'E:\my-repo\StackChan\tools\bot-monitor\.venv\Scripts\python.exe' 'E:\my-repo\StackChan\tools\bot-monitor\grok_bridge.py' run -- grok
```

状态文件默认仍位于工具目录。两个程序都可以通过 `--status-file` 指定同一个绝对路径。一次监控一个 Grok 主会话；同一状态文件不能被两个启动器同时使用。Windows 默认支持 Grok 的 PowerShell hooks，显式设置的 `GROK_SHELL=bash` 也支持；`cmd` shell 需要先切换为 `powershell`、`pwsh` 或 `bash`。

## macOS 与 Linux 快速开始

需要支持 BLE 的蓝牙适配器，以及已安装、登录且可正常使用的 `grok` 命令。建议使用 Python 3.11 或更新版本。StackChan 保持在 **DANCE**，并断开手机 App 或其他电脑对它的连接。

- **macOS**：开启蓝牙，按系统提示允许运行 Python 的终端或宿主应用使用蓝牙；若曾拒绝，可在系统设置的“隐私与安全性 → 蓝牙”中检查。扫描结果通常是设备 UUID，应使用当前 Mac 扫描出的标识，不能照搬 Windows 的 MAC 地址。
- **Linux**：需要安装 BlueZ 并运行蓝牙服务，开启蓝牙适配器，确保当前用户可以访问系统蓝牙 D-Bus。Ubuntu/Debian 可运行 `sudo apt install bluez python3-venv`；使用 systemd 的发行版可通过 `systemctl status bluetooth` 检查服务，按需运行 `sudo systemctl enable --now bluetooth`。若适配器被禁用，检查 `rfkill list bluetooth` 并按需解除禁用。其他发行版使用对应的软件包和服务管理方式。

以下命令适用于 Bash/Zsh，从仓库根目录执行。首次创建虚拟环境并安装依赖：

```bash
python3 -m venv tools/bot-monitor/.venv
tools/bot-monitor/.venv/bin/python -m pip install -r tools/bot-monitor/requirements.txt
```

每个系统单独创建虚拟环境，不要复制 Windows 的 `.venv` 到 macOS/Linux。首次使用 Grok 时，先运行 `grok login --device-auth`，按官方页面完成登录。

1. 扫描附近的 StackChan：

```bash
tools/bot-monitor/.venv/bin/python tools/bot-monitor/monitor.py scan
```

2. 在第一个终端启动 Grok 角色与中文状态监控。如果只扫描到一台设备，直接使用自动选择：

```bash
tools/bot-monitor/.venv/bin/python tools/bot-monitor/monitor.py monitor \
  --status-file tools/bot-monitor/status.json \
  --skin grok
```

有多台设备时，把 `DEVICE_ID` 替换为当前电脑扫描输出的实际标识：

```bash
tools/bot-monitor/.venv/bin/python tools/bot-monitor/monitor.py monitor \
  --address 'DEVICE_ID' \
  --status-file tools/bot-monitor/status.json \
  --skin grok
```

默认中文状态；添加 `--text en` 可改为英文。按 Ctrl+C 结束监控。

3. 在第二个终端切换到同一仓库根目录，通过启动器运行 Grok：

```bash
tools/bot-monitor/.venv/bin/python tools/bot-monitor/grok_bridge.py run -- grok
```

启动器的临时 hooks、项目信任和状态含义与 Windows 相同。如果 Grok 没有触发状态，使用 `/hooks` 检查加载情况，并按提示用 `/hooks-trust` 信任当前项目，再重新启动。

在其他项目中使用时，先进入目标项目，再用本工具的绝对路径启动。例如，替换下方路径为本机实际仓库位置：

```bash
cd /path/to/your-project
/path/to/StackChan/tools/bot-monitor/.venv/bin/python \
  /path/to/StackChan/tools/bot-monitor/grok_bridge.py run -- grok
```

启动器默认状态文件仍在 StackChan 仓库的 `tools/bot-monitor/status.json`；BLE 监控与启动器必须指向同一文件。需要自定义时，两者都传入相同的绝对路径 `--status-file /absolute/path/status.json`。

## 本次实机验证

新增 Grok 角色界面已使用 ESP-IDF 6.1 完整编译并刷入本机连接的 StackChan，写入哈希校验通过。用户已实机确认同时看到了球形角色、中文和动画。随后运行真实时间格式化函数修复：初始 5 项中 3 项失败，Grok 修复后 5 项全部通过，独立重跑也通过，测试文件未改动。真实 hooks 驱动的新界面 thinking、working、done、offline 均收到设备确认，详情见 [真实联调报告](LIVE_TEST.md)。

已安装并登录 Grok Build 1.0.77，在隔离示例目录完成了真实代码修复任务：初始 2 项测试失败，Grok 修复后 5 项全部通过，独立重跑也全部通过。真实 hooks 产生的 thinking、working、done、offline 均收到 StackChan GATT 写入确认，用户确认看到了黄灯、蓝灯、绿灯及退出变暗。详情见 [真实联调报告](LIVE_TEST.md)。

可单次发送一个状态验证设备，命令完成后会断开 BLE（显示保留）：

```powershell
.\tools\bot-monitor\.venv\Scripts\python.exe tools/bot-monitor/monitor.py show working --address 80:45:6B:4C:CC:36
```

## 状态含义

| Grok 事件 | 状态 | 灯色 |
| --- | --- | --- |
| 尚未收到有效事件 / 状态文件无效 | unknown | 暗灰 |
| SessionStart / StopCancelled | idle，待命或已中断 | 青色 |
| UserPromptSubmit / 最后一个 PostToolUse | thinking，正在推理或输出 | 黄色 |
| PreToolUse，仍有工具未结束 | working，正在调用工具 | 蓝色 |
| Notification: permission_prompt | waiting，等待授权 | 紫色 |
| Stop: end_turn，无后台工作 | done，本轮结束 | 绿色 |
| Stop: end_turn，仍有后台任务或定时任务 | waiting | 紫色 |
| StopFailure / PostToolUseFailure | error | 红色 |
| SessionEnd / 正常退出 / 心跳过期 | offline | 暗灰 |
| Grok 进程以非零代码退出 | error，随后心跳过期变为 offline | 红色 → 暗灰 |

`done` 表示 Grok 的本轮完成事件，不能证明代码测试通过或业务任务成功。`PostToolUse` 也可能包含命令非零退出等业务错误，当前不解析每个工具各自的结果结构。`thinking` 表示尚未收到工具执行或结束事件，无法区分模型内部推理与文字输出。

`Notification: idle_prompt` 在报错、中断之后也会触发，程序保留之前的错误/完成结果；仅对仍处于 thinking/working 的状态回退为 idle。带 `subagentType` 的子代理事件会被过滤；并行主会话工具按 `toolUseId` 计数，已经被新提示替代的旧提示事件会被忽略。

如果安装了**会阻止 Stop 的其他 hook**，本工具的 Stop 观察可能提前显示 done。此时使用 `grok_bridge.py run --no-stop-hook -- grok`，依赖 idle_prompt 回退到 idle；这版没有把其他 hooks 的最终决定当作可观测事件。

## 心跳与断线

启动器每 2 秒更新状态文件时间戳，因此长时间思考或运行工具不会因缺少 hooks 而超时。Grok 退出时写入 offline 或 error；启动器意外中断后，BLE 监控默认在 30 秒后把状态判为 offline。可用 `--stale-after` 修改超时秒数。

BLE 监控在状态变化时立即发送，每 5 秒发送一次保活；默认五官界面还会约每秒发送一帧动态表情，可用 `--static-face` 关闭。Grok 视图由固件自行播放动画。连接失败每 3 秒重试，重连后发送最新状态。使用带响应的 GATT 写入，按协商 MTU 选择包大小（MTU 未知时回退为 20 字节），大消息采用固件的 10 字节分包头。本机已实测协商 MTU 为 512。

**原有五官界面在电脑关闭、蓝牙断开或监控程序退出后会保留最后的表情和灯色。** 新 Grok 视图在 15 秒没有收到 `monitor` 更新后自行显示“连接已断开”并闭眼；该超时只作用于屏幕，RGB 灯会保留最后颜色。GATT 写入成功只确认设备接收，未提供界面渲染确认。

## 无硬件验证与其他程序接入

只预览 JSON，不使用蓝牙或 Bleak：

```powershell
python tools/bot-monitor/monitor.py monitor --demo --dry-run
```

其他程序可每隔几秒原子更新 `{"state":"working"}`。手动发布一次状态（30 秒后会过期）：

```powershell
python tools/bot-monitor/monitor.py publish tools/bot-monitor/status.json working
```

自动测试：

```powershell
python -m unittest discover -s tools/bot-monitor -v
```

真实联调时可使用 `grok_bridge.py run --event-log <文件路径> -- grok ...` 记录 hooks。日志仅包含事件名、时间、状态和是否变化，不记录提示、命令、工具结果或凭据；BLE 监控在状态变化的写入成功后输出 `BLE writes acknowledged`。

测试覆盖真实固件分包格式、UTF-8、状态文件异常与过期、GATT 写入顺序、Grok 事件映射、并行工具、迟到事件、hook stdin、进程心跳和临时 hooks 清理。进程测试使用模拟 CLI，不需要 Grok 登录，也不发起模型调用。

## 接口来源

- Grok Build：核对自 [xai-org/grok-build](https://github.com/xai-org/grok-build/tree/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8)，尤其是 [hooks 文档](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md) 和 `xai-grok-hooks/src/event.rs`。需要支持这些事件的 Grok 版本。
- 固件：`firmware/main/hal/utils/bleprph/bleprph.h` 定义服务与特征 UUID，`hal_ble.cpp` 定义分包，`apps/app_dance/app_dance.cpp` 接收表情和 RGB。
- 服务：`e2e5e5e0-1234-5678-1234-56789abcdef0`；表情：`e2e5e5e2-1234-5678-1234-56789abcdef0`；RGB：`e2e5e5e4-1234-5678-1234-56789abcdef0`。

如果能扫描但没有变化，先确认机器人仍在 DANCE，手机没有占用连接，固件支持上述 UUID，再分别运行演示模式和 Grok 的 `/hooks` 排查。当前只发送表情和 RGB，不发送舵机运动命令。
