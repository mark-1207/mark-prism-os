# PRISM-OS Mac 迁移方案

> 适用：从 Windows（D:\myproject\PRISM-OSv1）迁到 macOS
> 预计耗时：1.5-2 小时（含下载时间）
> 难度：中等，主要是 Windows 硬编码路径要改

---

## 0. 迁移前清单（先准备这些）

在 Mac 上一一确认：

- [ ] Mac 电脑（Apple Silicon / Intel 均可，Apple Silicon 跑 Python 更快）
- [ ] 4 个 API Key（见 `skills/prism-os/scripts/.env`）：
  - `KIMI_API_KEY`
  - `OPENROUTER_API_KEY`
  - `ZHIPU_API_KEY`
  - `NVIDIA_API_KEY`
- [ ] Obsidian 库备份（如果用 iCloud / OneDrive 同步，跳过这步）
- [ ] 决定 Mac 上项目根路径（建议 `~/Projects/PRISM-OSv1`，下文用此）

---

## 1. 系统环境准备

### 1.1 安装 Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Apple Silicon 装完会提示把 brew 加到 PATH，按提示执行：

```bash
(echo; echo 'eval "$(/opt/homebrew/bin/brew shellenv)"') >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 1.2 安装基础工具

```bash
brew install git python@3.11 node@20
```

> Python 3.11 是 PRISM-OS 当前目标版本，3.12+ 也兼容但需要重新跑测试
> Node 20 是 lark-cli 要求，≥18 即可

### 1.3 验证

```bash
git --version
python3.11 --version   # 应输出 Python 3.11.x
node --version         # 应输出 v20.x
```

---

## 2. 获取项目代码

```bash
mkdir -p ~/Projects
cd ~/Projects

# 方式 A：从远程仓库克隆（推荐）
git clone <你的仓库地址> PRISM-OSv1
cd PRISM-OSv1

# 方式 B：从 Windows 拷贝（U盘/网盘）
# 把整个 PRISM-OSv1 文件夹拷到 ~/Projects/，然后：
# cd ~/Projects/PRISM-OSv1
# git init && git remote add origin <你的仓库地址>
```

---

## 3. Python 环境

### 3.1 第三方包（只有 embedding.py 用）

```bash
cd ~/Projects/PRISM-OSv1
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install requests numpy
```

### 3.2 验证

```bash
python -c "import requests, numpy; print(f'requests={requests.__version__}, numpy={numpy.__version__}')"
```

应输出 `requests=2.x.x, numpy=1.x.x` 或更高。

### 3.3 装 pytest（运行测试用）

```bash
pip install pytest
```

---

## 4. Node 工具

### 4.1 lark-cli（飞书 CLI，全局安装）

```bash
npm install -g @larksuite/cli
lark-cli --version   # 验证
```

### 4.2 autocli 替代方案（重要）

**问题**：Windows 上的 `autocli.exe`（`D:\myproject\内容系统v1\contentforge\autocli.exe`）在 Mac 不能直接跑。

**方案 A**：从 contentforge 仓库重新编译 Mac 版（如有）

```bash
# 看 contentforge 是否有 Makefile / package.json scripts 支持 mac
cd <contentforge 路径>
cat package.json | grep -A 5 "scripts"
# 如果有 build:mac 或类似，跑它
```

**方案 B**：跳过 autocli，降级到 `wechat-article-extractor`（Node 脚本）

PRISM-OS 的 `content_generator.py` 已经是**三级降级**：
```
autocli → wechat-article-extractor → markitdown-web
```
autocli 不可用时自动 fallback 到下一级，无需手动改代码。

**方案 C**：暂不处理，等需要时再装

抓公众号文章功能暂不可用，PRISM-OS 核心流程（选题/标题/大纲）不受影响。

### 4.3 验证

```bash
which lark-cli
# /opt/homebrew/bin/lark-cli  （Apple Silicon）
# 或 /usr/local/bin/lark-cli   （Intel）
```

---

## 5. .env 配置

```bash
cd ~/Projects/PRISM-OSv1/skills/prism-os/scripts
cp .env .env.backup   # 备份

# 用编辑器打开，填入 4 个 API Key
nano .env
# 或
code .env
```

文件内容模板：

```bash
# PRISM-OS API Keys - Mac 迁移版
KIMI_API_KEY=<你的 key>
OPENROUTER_API_KEY=<你的 key>
ZHIPU_API_KEY=<你的 key>
NVIDIA_API_KEY=<你的 key>
```

> ⚠️ Mac 路径用 `/Users/mark/...` 或 `~/...`，**不要 Windows 风格的反斜杠**

---

## 6. 硬编码路径修复（重点）

PRISM-OS 有 8 处 Windows 硬编码路径需要改成 Mac 路径。

### 6.1 Obsidian 库路径（6 处）

文件：`skills/prism-os/scripts/content_generator.py`

需要改的行号：129, 582, 1303, 1457, 2024, 2142

```python
# 改前
vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")

# 改后（用你 Mac 上实际的 Obsidian 库路径）
vault_path = Path("/Users/mark/Documents/ObsidianVault")
```

**推荐：批量替换**（假设你的 Mac 路径是 `~/Documents/ObsidianVault`）：

```bash
cd ~/Projects/PRISM-OSv1
sed -i '' 's|D:\\软件\\obsidian笔记\\内容素材库|/Users/mark/Documents/ObsidianVault|g' \
  skills/prism-os/scripts/content_generator.py

# 验证替换
grep -n "ObsidianVault\|obsidian笔记" skills/prism-os/scripts/content_generator.py
```

### 6.2 autocli 路径（1 处）

文件：`skills/prism-os/scripts/content_generator.py` 第 216 行

```python
# 改前
AUTOCLI_PATH = r"D:\myproject\内容系统v1\contentforge\autocli.exe"

# 改后（如果方案 B/C：留空字符串或注释掉，触发降级）
AUTOCLI_PATH = ""  # Mac 上不直接用，触发 wechat-article-extractor 降级
```

> 或者如果你打算编译 Mac 版 autocli，放到 Mac 路径下，例如：
> `AUTOCLI_PATH = "/Users/mark/Projects/contentforge/autocli"`

### 6.3 wechat-article-extractor 路径（1 处）

文件：`skills/prism-os/scripts/content_generator.py` 第 279 行

```python
# 改前
extractor_path = Path(r"C:\Users\admin\.claude\skills\wechat-article-extractor\scripts\extract.js")

# 改后（Mac 上 Claude Code skills 路径）
extractor_path = Path("/Users/mark/.claude/skills/wechat-article-extractor/scripts/extract.js")
```

### 6.4 批量验证

```bash
cd ~/Projects/PRISM-OSv1
grep -rn "D:\\\\\|C:\\\\Users" skills/ 2>&1 | head -20
# 期望输出：无（除 .bat 文件和 .md 文档外）
```

### 6.5 rss-hunter 也有硬编码（补漏）

文件：`skills/rss-hunter/scripts/obsidian_writer.py` 第 19 行

```python
# 改前
DEFAULT_VAULT_PATH = r"D:\软件\obsidian笔记\内容素材库"

# 改后
DEFAULT_VAULT_PATH = "/Users/mark/Documents/ObsidianVault"
```

或用环境变量（更优雅）：

```python
import os
DEFAULT_VAULT_PATH = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/Users/mark/Documents/ObsidianVault"   # Mac 默认
)
```

### 6.6 marktap 抓取工具路径（rss-hunter 用）

文件：`skills/rss-hunter/SKILL.md:113` 提到 `D:\AI\marktap\marktap-desktop.bat`

- 这是一个独立的桌面抓取工具，**不在 PRISM-OS 仓库内**
- Mac 上要装 MarkTap 桌面版（如果有 Mac 版），或暂不用 rss-hunter 的 MarkTap 功能
- 文档里这一行改不改都行（不会影响代码运行）

### 6.7 文档里的路径（可改可不改）

以下 .md 文档里有 Windows 路径示例，**纯文档说明**，不影响代码运行：

- `skills/rss-hunter/MANUAL.md:158, 163, 186, 348`
- `skills/rss-hunter/SKILL.md:28, 107`
- `skills/prism-os/SKILL.md:99`
- `skills/prism-os/CHANGELOG.md:203`（历史记录，建议不改）

如果想让文档跨平台，改成：

```bash
# Windows
set OBSIDIAN_VAULT_PATH=D:\软件\obsidian笔记\内容素材库

# macOS / Linux
export OBSIDIAN_VAULT_PATH=~/Documents/ObsidianVault
```

**最低限度只改 6.1 + 6.2 + 6.3 + 6.5（4 处 Python 代码），其他可选。**

---

## 7. cron 任务迁移

### 7.1 Windows 版

`skills/prism-os/scripts/cron_assassin.bat` — Windows 计划任务

### 7.2 Mac 版：用 launchd

创建 `~/Library/LaunchAgents/com.prismos.assassin.plist`：

```bash
mkdir -p ~/Library/LaunchAgents
cat > ~/Library/LaunchAgents/com.prismos.assassin.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.prismos.assassin</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/mark/Projects/PRISM-OSv1/.venv/bin/python</string>
        <string>/Users/mark/Projects/PRISM-OSv1/skills/prism-os/scripts/assassin.py</string>
        <string>cron_check</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/mark/Projects/PRISM-OSv1/skills/prism-os/scripts</string>
    <key>StandardOutPath</key>
    <string>/Users/mark/Projects/PRISM-OSv1/.claude/logs/cron_assassin.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mark/Projects/PRISM-OSv1/.claude/logs/cron_assassin.err.log</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
EOF

# 加载（每天 9:00 跑）
launchctl load ~/Library/LaunchAgents/com.prismos.assassin.plist

# 验证
launchctl list | grep prismos
```

> ⚠️ 把所有 `/Users/mark/...` 改成你的 Mac 用户名

### 7.3 日志轮转

Mac launchd 不带轮转，需要自己写小脚本（可选）：

```bash
cat > ~/Projects/PRISM-OSv1/skills/prism-os/scripts/rotate_logs.sh <<'EOF'
#!/bin/bash
LOG_DIR="$HOME/Projects/PRISM-OSv1/.claude/logs"
MAX_SIZE=1048576
MAX_ROTATION=7

for log in "$LOG_DIR"/*.log; do
    [ -f "$log" ] || continue
    size=$(stat -f%z "$log")
    if [ "$size" -gt "$MAX_SIZE" ]; then
        for i in $(seq $((MAX_ROTATION-1)) -1 1); do
            [ -f "${log}.$i" ] && mv "${log}.$i" "${log}.$((i+1))"
        done
        mv "$log" "${log}.1"
    fi
done

# 删 7 天前的
find "$LOG_DIR" -name "*.log.*" -mtime +7 -delete
EOF
chmod +x ~/Projects/PRISM-OSv1/skills/prism-os/scripts/rotate_logs.sh
```

---

## 8. Claude Code 配置迁移

### 8.1 用户级配置

`~/.claude/settings.json` — 直接从 Windows 拷过来即可。  
**Mac 默认 UTF-8，不需要 Windows 那套：**

```json
"LC_ALL": "C.UTF-8",
"LANG": "C.UTF-8",
"PYTHONIOENCODING": "utf-8",
"PYTHONUTF8": "1"
```

**这 4 个可以删掉**（Mac 上是冗余的），但保留无害。删了更干净。

### 8.2 项目级配置

`~/.claude/projects/D--myproject/memory/` — 项目记忆

```bash
# 在 Mac 上恢复
mkdir -p ~/.claude/projects/your-project-slug/memory
# 把 MEMORY.md 和所有 .md 记忆文件拷过来
```

> 路径里的项目 slug 在 Mac 上会不同（`D--myproject` → 你 Mac 的目录结构），需要重新映射。  
> 或者直接先不拷记忆文件，等新会话里让 Claude 自己探索补全。

### 8.3 settings.local.json 白名单重写

Mac 路径示例：

```json
"allow": [
  "Bash(python3.11 *)",
  "Bash(node *)",
  "Bash(lark-cli *)",
  "Bash(npm install *)",
  "Bash(git *)",
  "Bash(brew *)"
]
```

> Windows 的 `/d/nodejs/...lark-cli.exe` 路径全部不要。

---

## 9. 编码问题（Mac 比 Windows 简单）

**Mac 默认 UTF-8**，没有 Windows 那个 GBK × Python 编码冲突。

- 不需要 `PYTHONIOENCODING` hack
- 不需要 `chcp 65001`
- 不需要 LC_ALL

**可以回滚 Windows 上的修复**（可选）：

```bash
# 移除 call_llm.py 头部的 reconfigure（无害但冗余）
cd ~/Projects/PRISM-OSv1
git diff skills/prism-os/scripts/call_llm.py | head
# 看了决定要不要还原
```

建议**保留**——双 UTF-8 兜底没有坏处。

---

## 10. 验证步骤

按顺序跑这些命令，确保迁移成功：

### 10.1 基础环境

```bash
cd ~/Projects/PRISM-OSv1
source .venv/bin/activate

# Python 解释器
python --version
# 应输出：Python 3.11.x

# 第三方包
python -c "import requests, numpy; print('OK')"

# Node
node --version
which lark-cli
```

### 10.2 项目完整性

```bash
# Git 状态
git status
# 期望：clean working tree（除了 .env 等被 .gitignore 排除的）

# Git 完整性
git fsck --no-progress 2>&1 | tail -5
# 期望：dangling blob 警告（正常，不影响使用）
```

### 10.3 单元测试

```bash
cd ~/Projects/PRISM-OSv1
source .venv/bin/activate
python -m pytest tests/ -v
# 期望：426 passed（按 MEMORY 记录）
```

### 10.4 健康检查

```bash
cd ~/Projects/PRISM-OSv1/skills/prism-os/scripts
python health_check.py
# 期望：status: ok（如有错说明 gateway 配置问题）
```

### 10.5 端到端测试

```bash
cd ~/Projects/PRISM-OSv1/skills/prism-os/scripts
GATEWAY_AUTH_KEY=test-secret \
GATEWAY_SCENE=reasoning \
OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
python prism_os.py run "测试：Mac 迁移是否成功？" --no-ext
```

期望输出：
- Phase 0 意图识别 → "opinion" 或 "article"
- Phase 1 苏格拉底网关 → entropy/hkr 分数
- Phase 2 棱镜引擎 → 候选标题
- Phase 4 CCOS 大纲（如选了标题）
- 整个流程不崩、不挂、输出完整中文

---

## 11. 已知问题与备选方案

| 问题 | 影响 | 解决方案 |
|------|------|----------|
| autocli.exe 不可用 | 公众号抓取走降级路径（慢 1-2s） | 编译 Mac 版 / 用 wechat-article-extractor 替代 |
| 项目 memory 路径变化 | 跨平台记忆可能不通用 | 在 Mac 上让 Claude 重新建立项目上下文 |
| bash 工具无 2 分钟超时 | 流程长反而更稳定 | 无需处理（Mac 上没这问题） |
| Windows `.bat` cron | 不能直接用 | 改 launchd plist（见 §7.2） |
| lark-cli 白名单路径 | Windows 风格路径失效 | 重写 settings.local.json（见 §8.3） |
| 第三方包缺失 | embedding 不可用 | `pip install requests numpy`（见 §3.1） |
| 编码问题 | Mac 不存在 | 无需处理（见 §9） |

---

## 12. 后续优化（迁移成功后做）

迁移成功稳定运行一周后，可以做：

1. **把硬编码路径改成配置化**：在 `content_generator.py` 顶部加一个 `CONFIG` dict，从 `.env` 或环境变量读路径
2. **加 CI**：用 GitHub Actions 跑 `pytest`，避免 Mac 引入新 bug
3. **补 requirements.txt**：当前没依赖文件，建议加：
   ```txt
   requests>=2.28
   numpy>=1.24
   pytest>=7.0
   ```
4. **加 .env.example**：在 git 里有模板文件，`.env` 仍 gitignore
5. **写 Makefile**：把常用命令（test / run / health / lint）做成 `make xxx`

---

## 13. 故障排查速查

| 现象 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: requests` | 没装第三方包 | `source .venv/bin/activate && pip install requests numpy` |
| `lark-cli: command not found` | 没装或没 PATH | `npm install -g @larksuite/cli`，新开终端 |
| 跑 run 后中文乱码 | 旧版 .env 在用 | 重新填 .env，删 Windows 反斜杠 |
| Obsidian 找不到 | 路径没改 | 重做 §6.1 |
| cron 没跑 | launchd 没加载 | `launchctl load ~/Library/LaunchAgents/com.prismos.assassin.plist` |
| pytest 全部失败 | Python 版本不对 | 用 `python3.11` 重建 venv |
| `UnicodeDecodeError: gbk` | ❌ 不应出现在 Mac 上 | 如出现说明 .env 路径错（用了 Windows 反斜杠） |

---

**最后：迁移完先跑 §10.5 端到端测试，看到完整中文输出且不挂，就算成功。**
