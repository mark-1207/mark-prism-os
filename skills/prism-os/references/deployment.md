# 部署清单

## 三种部署模式

### 1. 本地 CLI

最简模式。直接跑命令，无守护进程。

```bash
python scripts/prism_os.py run "<命题>"
```

### 2. HTTP listen 模式

守护进程模式，监听 HTTP 请求，第三方工具（Claude Code / 自建 Agent）可调用。

```bash
python scripts/prism_os.py listen
# 默认端口 7654
# interactive=False
# 默认路由 /prism-os/run
```

**接口约定**：

```http
POST /prism-os/run
Content-Type: application/json
{
  "thesis": "你的命题",
  "user_clarification": "可选",
  "skip_gateway": false,
  "platform": "wechat"
}
```

### 3. Windows 计划任务模式

**仅用于 Phase 6.0 数据闭环**（每日同步飞书多维表），不触发 `run`/`narrate`。

#### 安装

```powershell
# 管理员 PowerShell
cd D:\myproject\PRISM-OSv1\skills\prism-os
.\scripts\setup_scheduler.ps1
```

注册任务：
- 名称：`PRISM-OS Metrics Sync`
- 触发：每天 11:00
- 操作：跑 `scripts/metrics_sync_wrapper.bat`
- 含义：每天调 `metrics sync` + `metrics score` 两次

#### 卸载

```powershell
Unregister-ScheduledTask -TaskName "PRISM-OS Metrics Sync"
```

#### 验证

```bash
# 手动触发
scripts/metrics_sync_wrapper.bat

# 看日志
type logs\metrics_sync.log
```

## 配置文件清单

| 文件 | 用途 |
|------|------|
| `config/digital_twin.yaml` | 数字分身思维特征 |
| `config/feishu_config.yaml` | 飞书 base token + table id |
| `config/user_config.yaml` | 用户身份/受众/定位 |
| `config/ccos_settings.yaml` | CCOS Layer 0 追问开关 |
| `config/info_sources.yaml` | 认知裂缝监控信息源 |

## 环境要求

- Python 3.11+
- 依赖：`requests pyyaml numpy`（最小集）
- 可选：`pytest`（跑测试）
- 操作系统：Windows 10+ / macOS / Linux

## 健康检查

```bash
# 1. CLI 可用
python scripts/prism_os.py --help 2>&1 | head -3

# 2. 数据目录可写
touch data/test_write && rm data/test_write

# 3. 4 个 provider 至少一个通
python scripts/prism_os.py classify "测试" 2>&1 | head -10
```
