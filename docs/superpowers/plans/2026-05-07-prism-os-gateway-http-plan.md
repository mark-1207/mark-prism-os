# PRISM-OS × Gateway HTTP 集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** gateway 启动 HTTP 服务（localhost:3000），模拟 OpenAI `/v1/chat/completions` 接口，PRISM-OS Python 端通过 `X-Gateway-Scene` header 路由到对应 scene

**Architecture:**
- `src/http-server.ts` — Node.js 原生 http 模块，实现 `/health` + `/v1/chat/completions`
- PRISM-OS 侧 `call_llm.py` 读取 `GATEWAY_SCENE` 环境变量，转为 `X-Gateway-Scene` header
- 认证通过 `Authorization: Bearer {GATEWAY_AUTH_KEY}` header

**Tech Stack:** Node.js 原生 `http`/`https` 模块（无 express），环境变量配置

---

## 文件清单

```
gateway/
├── src/
│   ├── http-server.ts          # 新建：HTTP 服务实现
│   ├── gateway.ts               # 已有：复用 chat() 核心
│   ├── scenes.ts                # 已有：SCENE_CONFIGS
│   ├── types.ts                 # 已有：类型定义
│   └── index.ts                 # 修改：导出 initHttpServer
├── dist/
│   └── http-server.js           # 构建产物
└── package.json                 # 修改：新增 start 脚本

PRISM-OSv1/skills/prism-os/
├── scripts/
│   ├── start-gateway.sh         # 新建：启动脚本
│   └── stop-gateway.sh          # 新建：停止脚本
├── config/
│   └── user_config.yaml         # 修改：llm_api.url 改 localhost
└── scripts/
    └── call_llm.py              # 修改：加上 X-Gateway-Scene header
```

---

## Task 1: Gateway HTTP Server 实现

**Files:**
- Create: `D:\myproject\gateway\src\http-server.ts`
- Modify: `D:\myproject\gateway\src\index.ts`
- Modify: `D:\myproject\gateway\package.json`

- [ ] **Step 1: 创建 src/http-server.ts**

```typescript
// D:\myproject\gateway\src\http-server.ts
import http from 'http';
import { Gateway } from './gateway.js';
import type { ChatOptions, ChatResult } from './types.js';

const PORT = parseInt(process.env.PORT || '3000');
const AUTH_KEY = process.env.GATEWAY_AUTH_KEY || '';
const REQUEST_TIMEOUT_MS = parseInt(process.env.GATEWAY_REQUEST_TIMEOUT_MS || '30000');
const VERSION = '0.1.0';

interface ChatRequest {
  model?: string;
  messages: Array<{ role: string; content: string }>;
  temperature?: number;
  max_tokens?: number;
}

function parseAuthHeader(req: http.IncomingMessage): string | null {
  const auth = req.headers['authorization'] || '';
  if (!auth.startsWith('Bearer ')) return null;
  return auth.slice(7);
}

function sendJson(res: http.ServerResponse, status: number, body: object): void {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function sendError(res: http.ServerResponse, status: number, message: string, type = 'gateway_error', code = 'gateway_error'): void {
  sendJson(res, status, { error: { message, type, code } });
}

// Initialize Gateway singleton
const gateway = new Gateway({
  openRouterApiKey: process.env.OPENROUTER_API_KEY || '',
  googleApiKey: process.env.GOOGLE_API_KEY,
  googleBaseUrl: process.env.GOOGLE_BASE_URL,
  maxRetries: 1,
  retryDelayMs: 2000,
  onError: (err, provider, scene) => {
    console.log(JSON.stringify({ level: 'error', provider, scene, message: err.message }));
  },
});

async function handleChatCompletion(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  // Read body
  const body = await new Promise<string>((resolve, reject) => {
    const chunks: string[] = [];
    req.on('data', (chunk: Buffer) => chunks.push(chunk.toString()));
    req.on('end', () => resolve(chunks.join('')));
    req.on('error', reject);
  });

  let parsed: ChatRequest;
  try {
    parsed = JSON.parse(body);
  } catch {
    return sendError(res, 400, 'Invalid JSON body');
  }

  // Validate X-Gateway-Scene
  const scene = req.headers['x-gateway-scene'] as string | undefined;
  if (!scene) {
    return sendError(res, 400, 'X-Gateway-Scene header required', 'validation_error', 'missing_scene_header');
  }

  // Validate messages
  if (!Array.isArray(parsed.messages) || parsed.messages.length === 0) {
    return sendError(res, 400, 'messages field required and non-empty', 'validation_error', 'invalid_messages');
  }

  // Build options
  const options: Partial<ChatOptions> = {
    messages: parsed.messages as any,
    temperature: parsed.temperature,
    maxTokens: parsed.max_tokens,
  };

  // Timeout wrapper
  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error('Gateway request timeout')), REQUEST_TIMEOUT_MS);
  });

  try {
    const result = await Promise.race([
      gateway.chat(scene as any, options),
      timeoutPromise,
    ]) as ChatResult;

    sendJson(res, 200, {
      id: `gateway-${Date.now()}`,
      model: parsed.model || scene,
      choices: [{
        message: { role: 'assistant', content: result.content },
        finish_reason: 'stop',
        index: 0,
      }],
      usage: {
        prompt_tokens: 0,  // gateway doesn't track token counts
        completion_tokens: 0,
        total_tokens: 0,
      },
    });
  } catch (err: any) {
    console.log(JSON.stringify({ level: 'error', scene, error: err.message }));
    sendError(res, 500, err.message || 'Internal gateway error');
  }
}

async function handleHealth(res: http.ServerResponse): Promise<void> {
  sendJson(res, 200, { status: 'ok', version: VERSION });
}

const server = http.createServer(async (req, res) => {
  const url = req.url || '';
  const method = req.method || '';

  // Auth check for all /v1/ paths
  if (url.startsWith('/v1/')) {
    const key = parseAuthHeader(req);
    if (!AUTH_KEY || key !== AUTH_KEY) {
      return sendError(res, 401, 'Unauthorized', 'auth_error');
    }
  }

  try {
    if (url === '/health' && method === 'GET') {
      await handleHealth(res);
    } else if (url === '/v1/chat/completions' && method === 'POST') {
      await handleChatCompletion(req, res);
    } else {
      sendError(res, 404, 'Not found');
    }
  } catch (err: any) {
    console.log(JSON.stringify({ level: 'error', url, error: err.message }));
    sendError(res, 500, 'Internal server error');
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(JSON.stringify({ level: 'info', message: `Gateway HTTP server running on port ${PORT}` }));
});
```

- [ ] **Step 2: 修改 src/index.ts，导出 initHttpServer**

```typescript
// D:\myproject\gateway\src\index.ts 追加
export { default as httpServer } from './http-server.js';
```

- [ ] **Step 3: 修改 package.json，新增 start 脚本**

```json
// D:\myproject\gateway\package.json — scripts 部分
{
  "scripts": {
    "build": "tsup --config tsup.config.ts",
    "dev": "tsup --config tsup.config.ts --watch",
    "start": "node dist/http-server.js"
  }
}
```

- [ ] **Step 4: 构建**

```bash
cd D:/myproject/gateway && npm run build
```

预期输出：`dist/http-server.js` 存在且无编译错误

- [ ] **Step 5: 单元测试 — HTTP 服务启动**

```bash
# 启动服务（后台）
GATEWAY_AUTH_KEY=test-secret OPENROUTER_API_KEY=$OPENROUTER_API_KEY node dist/http-server.js &
GATEWAY_PID=$!
sleep 2

# 测试 health
HEALTH=$(curl -s http://localhost:3000/health)
echo "$HEALTH"
# 期望: {"status":"ok","version":"0.1.0"}

# 测试无 auth — 期望 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/v1/chat/completions
# 期望: 401

# 停止
kill $GATEWAY_PID 2>/dev/null
```

- [ ] **Step 6: 单元测试 — scene 缺失返回 400**

```bash
# 启动
GATEWAY_AUTH_KEY=test-secret OPENROUTER_API_KEY=$OPENROUTER_API_KEY node dist/http-server.js &
PID=$!
sleep 2

# 无 X-Gateway-Scene header — 期望 400
curl -s http://localhost:3000/v1/chat/completions \
  -H "Authorization: Bearer test-secret" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}]}'
# 期望: {"error":{"message":"X-Gateway-Scene header required"...}}

kill $PID 2>/dev/null
```

- [ ] **Step 7: 单元测试 — 无效 scene 返回 400**

```bash
# 启动
GATEWAY_AUTH_KEY=test-secret OPENROUTER_API_KEY=$OPENROUTER_API_KEY node dist/http-server.js &
PID=$!
sleep 2

curl -s http://localhost:3000/v1/chat/completions \
  -H "Authorization: Bearer test-secret" \
  -H "X-Gateway-Scene: nonexistent" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}]}'
# 期望: {"error":{"message":"Unknown scene: nonexistent"...}}

kill $PID 2>/dev/null
```

- [ ] **Step 8: 提交**

```bash
cd D:/myproject/gateway
git add src/http-server.ts src/index.ts package.json dist/
git commit -m "feat(http): add HTTP server with OpenAI-compatible /v1/chat/completions endpoint"
```

---

## Task 2: PRISM-OS 集成

**Files:**
- Create: `D:\myproject\PRISM-OSv1\skills\prism-os\scripts\start-gateway.sh`
- Create: `D:\myproject\PRISM-OSv1\skills\prism-os\scripts\stop-gateway.sh`
- Modify: `D:\myproject\PRISM-OSv1\skills\prism-os\config\user_config.yaml`
- Modify: `D:\myproject\PRISM-OSv1\skills\prism-os\scripts\call_llm.py`

- [ ] **Step 1: 创建 scripts/start-gateway.sh**

```bash
#!/bin/bash
# D:\myproject\PRISM-OSv1\skills\prism-os\scripts\start-gateway.sh

set -e

GATEWAY_DIR="${GATEWAY_DIR:-D:/myproject/gateway}"
GATEWAY_PID_FILE="/tmp/gateway-prism-os.pid"
GATEWAY_AUTH_KEY="${GATEWAY_AUTH_KEY:-prism-os-secret}"

# Check if already running
if [ -f "$GATEWAY_PID_FILE" ] && kill -0 "$(cat "$GATEWAY_PID_FILE")" 2>/dev/null; then
  echo "Gateway already running (PID $(cat "$GATEWAY_PID_FILE"))"
  exit 0
fi

# Ensure dist exists
if [ ! -f "$GATEWAY_DIR/dist/http-server.js" ]; then
  echo "Error: gateway dist not found at $GATEWAY_DIR/dist/http-server.js"
  echo "Run: cd $GATEWAY_DIR && npm run build"
  exit 1
fi

# Start gateway
cd "$GATEWAY_DIR"
GATEWAY_AUTH_KEY="$GATEWAY_AUTH_KEY" \
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
node dist/http-server.js &
echo $! > "$GATEWAY_PID_FILE"
sleep 1

# Verify health
HEALTH=$(curl -s --fail http://localhost:3000/health 2>/dev/null || echo "")
if [ -z "$HEALTH" ]; then
  echo "Error: gateway failed to start"
  rm -f "$GATEWAY_PID_FILE"
  exit 1
fi

echo "Gateway started (PID $(cat "$GATEWAY_PID_FILE"))"
```

- [ ] **Step 2: 创建 scripts/stop-gateway.sh**

```bash
#!/bin/bash
# D:\myproject\PRISM-OSv1\skills\prism-os\scripts\stop-gateway.sh

GATEWAY_PID_FILE="/tmp/gateway-prism-os.pid"

if [ -f "$GATEWAY_PID_FILE" ]; then
  PID=$(cat "$GATEWAY_PID_FILE")
  if kill "$PID" 2>/dev/null; then
    echo "Gateway stopped (was PID $PID)"
  else
    echo "Gateway process not found"
  fi
  rm -f "$GATEWAY_PID_FILE"
else
  echo "Gateway PID file not found, assuming not running"
fi
```

- [ ] **Step 3: 修改 user_config.yaml**

```yaml
# D:\myproject\PRISM-OSv1\skills\prism-os\config\user_config.yaml
llm_api:
  url: "http://localhost:3000/v1/chat/completions"
  key: "${GATEWAY_AUTH_KEY}"
```

- [ ] **Step 4: 修改 scripts/call_llm.py — 加 X-Gateway-Scene header**

```python
# D:\myproject\PRISM-OSv1\skills\prism-os\scripts\call_llm.py
# 在 call_llm() 函数中，找 req 对象创建处，加上 header

# 在 load_config() 之后，约第 59 行附近，修改 request 创建部分：
# 找到这行：
#     req = urllib.request.Request(
#         config["llm_api_url"],
#         data=data,
#         headers={
#             "Content-Type": "application/json",
#             "Authorization": f"Bearer {config['llm_api_key']}"
#         },
#         method="POST"
#     )

# 改为（约第 59 行）：
import os as _os
_scene = _os.environ.get('GATEWAY_SCENE', '')
_headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {config['llm_api_key']}"
}
if _scene:
    _headers["X-Gateway-Scene"] = _scene

req = urllib.request.Request(
    config["llm_api_url"],
    data=data,
    headers=_headers,
    method="POST"
)
```

完整改动后的 call_llm 函数（约第 21-69 行）：

```python
def call_llm(prompt: str, model: str = "gpt-4", temperature: float = 0.7) -> Dict:
    config = load_config()

    if not config["llm_api_url"] or not config["llm_api_key"]:
        return {"content": None, "error": "请配置 LLM_API_URL 和 LLM_API_KEY 环境变量"}

    try:
        import urllib.request
        import urllib.error

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        data = json.dumps(payload).encode("utf-8")

        # Add X-Gateway-Scene header if GATEWAY_SCENE env is set
        import os as _os
        _headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['llm_api_key']}"
        }
        _scene = _os.environ.get('GATEWAY_SCENE', '')
        if _scene:
            _headers["X-Gateway-Scene"] = _scene

        req = urllib.request.Request(
            config["llm_api_url"],
            data=data,
            headers=_headers,
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"content": content, "error": None}

    except urllib.error.HTTPError as e:
        return {"content": None, "error": f"HTTP错误: {e.code} {e.reason}"}
    except urllib.error.URLError as e:
        return {"content": None, "error": f"网络错误: {e.reason}"}
    except Exception as e:
        return {"content": None, "error": f"未知错误: {str(e)}"}
```

- [ ] **Step 5: 集成测试 — gateway 启动 + call_llm.py 走 HTTP**

```bash
# 1. 构建 gateway（如果没有最新 dist）
cd D:/myproject/gateway && npm run build

# 2. 启动 gateway
cd D:/myproject/PRISM-OSv1/skills/prism-os
chmod +x scripts/start-gateway.sh scripts/stop-gateway.sh
./scripts/start-gateway.sh

# 3. 测试 health
curl -s http://localhost:3000/health
# 期望: {"status":"ok","version":"0.1.0"}

# 4. 测试 call_llm.py 带 GATEWAY_SCENE
GATEWAY_SCENE=reasoning \
GATEWAY_AUTH_KEY=prism-os-secret \
OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
python scripts/call_llm.py "1+1=?"
# 期望: {"content": "..."} 或类似响应（非 error）

# 5. 停止
./scripts/stop-gateway.sh
```

- [ ] **Step 6: 降级验证 — 制造 primary 失败，验证 fallback**

```bash
# 1. 启动 gateway（故意用错误 key 触发 primary 失败）
cd D:/myproject/PRISM-OSv1/skills/prism-os
OPENROUTER_API_KEY=bad-key ./scripts/start-gateway.sh

# 2. 测试 reasoning scene — primary 失败应切换到 fallback
GATEWAY_SCENE=reasoning GATEWAY_AUTH_KEY=prism-os-secret \
OPENROUTER_API_KEY=bad-key \
python scripts/call_llm.py "为什么天是蓝色的？"
# 期望: 仍然返回 content（fallback gemini 成功），不报错

# 3. 停止
./scripts/stop-gateway.sh
```

- [ ] **Step 7: 提交**

```bash
cd D:/myproject/PRISM-OSv1
git add skills/prism-os/scripts/start-gateway.sh \
       skills/prism-os/scripts/stop-gateway.sh \
       skills/prism-os/config/user_config.yaml \
       skills/prism-os/scripts/call_llm.py
git commit -m "feat(prism-os): integrate gateway HTTP server for scene-based LLM routing"
```

---

## Task 3: PRISM-OS Phase Scene 映射验证

- [ ] **Step 1: 验证 Phase 0-8 scene 映射（文档对照检查）**

对照 `docs/superpowers/specs/2026-05-07-prism-os-gateway-http-design.md` Section 6.3 的表格，检查 SKILL.md 各 Phase 是否存在相应调用

无需修改代码，只做文档对照确认：
- Phase 0：`reasoning`
- Phase 1：`reasoning`
- Phase 2：`writing-cn`
- Phase 3：`summary`
- Phase 4：`extraction`
- Phase 5：`reasoning`
- Phase 6：`quality`
- Phase 7：`quality`
- Phase 8：`reasoning`

---

## 验证清单

- [ ] `node dist/http-server.js` 启动成功
- [ ] `GET /health` 返回 `{"status":"ok","version":"0.1.0"}`
- [ ] 无 auth header → 401
- [ ] 无 `X-Gateway-Scene` → 400
- [ ] 无效 scene → 400
- [ ] 有效 scene → OpenAI 格式响应
- [ ] `python scripts/call_llm.py` + `GATEWAY_SCENE=reasoning` → 正常返回
- [ ] primary 失败 → fallback 自动切换
- [ ] `scripts/start-gateway.sh` / `stop-gateway.sh` 正常工作

---

**执行选项：**
**1. Subagent-Driven (recommended)** — 每个 Task 派一个 subagent 执行，Task 间我来 review
**2. Inline Execution** — 本 session 连续执行，批量处理完再 review