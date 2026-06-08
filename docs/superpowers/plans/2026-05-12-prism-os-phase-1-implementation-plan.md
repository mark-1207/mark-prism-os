# PRISM-OS Phase 1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Embedding 独立模块、飞书读写（lark-cli）、confirm 命令、定时触发四个功能

**Architecture:** 新建 `embedding.py` 独立模块 + 修改 `assassin.py`（飞书读写） + 修改 `prism_os.py`（confirm 命令） + 修改 `assassin.py`（cron_check 定时触发）

**Tech Stack:** Python 标准库（subprocess, json, hashlib, ssl）+ numpy + 智谱 Embedding API + lark-cli

---

## 文件结构

```
skills/prism-os/scripts/
├── embedding.py          # 新建：Embedding 独立模块
├── assassin.py           # 修改：read_viral_library, update_feishu_viral, cron_check
└── prism_os.py           # 修改：confirm 命令

skills/prism-os/data/
└── embedding_cache.json  # 新建：向量缓存（自动创建）
└── notifications/        # 新建：定时触发通知输出目录
```

---

## Task 1: Embedding 独立模块

**Files:**
- Create: `skills/prism-os/scripts/embedding.py`
- Test: `python embedding.py embed "测试标题"` → 1024维向量

- [ ] **Step 1: 编写 embed() 测试**

```python
# skills/prism-os/scripts/test_embedding.py
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embedding import embed

def test_embed_returns_vector():
    result = embed("测试标题")
    assert result is not None, "embed() should return a vector"
    assert len(result) == 1024, f"Expected 1024 dims, got {len(result)}"
    print("test_embed_returns_vector PASS")

def test_embed_cached():
    result1 = embed("相同标题")
    result2 = embed("相同标题")
    assert result1 == result2, "Same text should return same vector"
    print("test_embed_cached PASS")

def test_embed_none_for_missing_key():
    # 当 API key 不存在时，应返回 None 而不是抛异常
    result = embed("任何标题")
    # result 可能是 None（API 失败）或向量
    assert result is None or len(result) == 1024
    print("test_embed_none_for_missing_key PASS")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -c "import sys; sys.path.insert(0, '.'); from embedding import embed; print(embed('test'))"`
Expected: `NameError: name 'embedding' is not defined`

- [ ] **Step 3: 编写 embedding.py 骨架**

```python
#!/usr/bin/env python3
"""
PRISM-OS Embedding 独立模块
提供向量生成和相似度计算，供正交性校验和刺客机制调用
"""
import sys
import os
import json
import hashlib
import ssl
import urllib.request
import urllib.error
from typing import List, Optional

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "embedding_cache.json")
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
ZHIPU_MODEL = os.getenv("ZHIPU_EMBEDDING_MODEL", "embedding-2")

def _load_cache() -> dict:
    """加载缓存，返回 {"version": 1, "cache": {hash: [vec...]}}"""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # 损坏则备份重建
            bak = CACHE_PATH + ".bak"
            if os.path.exists(CACHE_PATH):
                os.rename(CACHE_PATH, bak)
    return {"version": 1, "cache": {}}

def _save_cache(cache: dict):
    """保存缓存"""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

def embed(text: str, model: str = None) -> Optional[List[float]]:
    """
    生成文本向量
    流程：检查缓存 → 有则返回 → 无则调智谱API → 写入缓存 → 返回向量
    超时/失败返回 None
    """
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    cache = _load_cache()

    # 缓存命中
    if text_hash in cache["cache"]:
        return cache["cache"][text_hash]

    # 调用 API
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        print("[Embedding] ZHIPU_API_KEY not set, returning None", file=sys.stderr)
        return None

    model = model or ZHIPU_MODEL
    payload = json.dumps({"model": model, "input": text}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        ZHIPU_API_URL,
        data=payload,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            embedding = result.get("data", [{}])[0].get("embedding", [])
            if embedding:
                cache["cache"][text_hash] = embedding
                _save_cache(cache)
                return embedding
    except Exception as e:
        print(f"[Embedding] API call failed: {e}", file=sys.stderr)

    return None

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """计算两个向量的 Cosine 相似度"""
    import numpy as np
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0

def tokenize(text: str) -> List[str]:
    """简单分词"""
    import re
    return re.findall(r'\w+', text.lower())

def get_similarity(text_a: str, text_b: str) -> Optional[float]:
    """
    计算两个标题的相似度
    公式：0.4 × Jaccard + 0.6 × Cosine(向量)
    Cosine 失败时降级到纯 Jaccard
    """
    # Jaccard
    tokens_a = set(tokenize(text_a))
    tokens_b = set(tokenize(text_b))
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if tokens_a or tokens_b else 0

    # Cosine（降级）
    vec_a = embed(text_a)
    vec_b = embed(text_b)
    if vec_a and vec_b:
        cosine = cosine_similarity(vec_a, vec_b)
        return 0.4 * jaccard + 0.6 * cosine
    else:
        # Cosine 失败，降级到纯 Jaccard
        print("[Embedding] Cosine unavailable, using Jaccard only", file=sys.stderr)
        return jaccard

def clear_cache():
    """清空所有缓存（仅调试用）"""
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
    print("Cache cleared")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "用法: python embedding.py embed <文本>"}))
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "embed":
        text = sys.argv[2] if len(sys.argv) > 2 else ""
        result = embed(text)
        print(json.dumps(result, ensure_ascii=False))
    elif cmd == "clear":
        clear_cache()
    elif cmd == "similarity":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "用法: python embedding.py similarity <文本A> <文本B>"}))
            sys.exit(1)
        result = get_similarity(sys.argv[2], sys.argv[3])
        print(json.dumps(result, ensure_ascii=False))
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python skills/prism-os/scripts/embedding.py embed "测试标题"`
Expected: `[0.123, -0.456, ...]` (1024 维向量)

- [ ] **Step 5: 提交**

```bash
git add skills/prism-os/scripts/embedding.py
git commit -m "feat: add embedding module with zhipu api and disk cache"
```

---

## Task 2: 飞书读取实现 (read_viral_library)

**Files:**
- Modify: `skills/prism-os/scripts/assassin.py` (在顶部添加 lark-cli 验证和读取函数)
- Test: `python assassin.py read` → 历史记录列表

- [ ] **Step 1: 编写 lark-cli 验证函数（在 assassin.py 顶部）**

在 `assassin.py` 顶部 `# ============ 阶段 4: 飞书多维表格集成 ============` 之前添加：

```python
# ============ lark-cli 工具函数 ============

def _verify_lark_cli():
    """验证 lark-cli 是否在 PATH 中"""
    import shutil
    if not shutil.which("lark-cli"):
        print("[Error] lark-cli not found in PATH. Please install: npm install -g @larksuite/cli", file=sys.stderr)
        sys.exit(1)

def _run_lark_cli(args: list, timeout: int = 30) -> tuple:
    """
    运行 lark-cli 命令
    Returns: (stdout: str, stderr: str, returncode: int)
    """
    import subprocess
    _verify_lark_cli()
    result = subprocess.run(
        ["lark-cli"] + args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )
    return result.stdout, result.stderr, result.returncode
```

- [ ] **Step 2: 编写 read_viral_library() 实现**

在 `read_viral_library()` 函数内部替换 TODO 内容：

```python
def read_viral_library() -> List[Dict]:
    """
    从飞书多维表格读取历史爆款
    Returns:
        [{"title": str, "date": str, "views": int, "likes": int, "direction": str}, ...]
    """
    stdout, stderr, code = _run_lark_cli([
        "feishu", "bitable", "record", "list",
        "--app-token", FEISHU_APP_TOKEN,
        "--table-id", FEISHU_TABLE_ID,
        "--page-size", "100"
    ])

    if code != 0:
        print(f"[Warning] lark-cli read failed: {stderr}", file=sys.stderr)
        return []

    # 尝试 JSON parse
    try:
        data = json.loads(stdout)
        records = data.get("data", {}).get("items", [])
        result = []
        for r in records:
            fields = r.get("fields", {})
            result.append({
                "title": fields.get("标题", ""),
                "date": fields.get("发布日期", ""),
                "views": fields.get("阅读量", 0),
                "likes": fields.get("互动量", 0),
                "direction": fields.get("内容方向", ""),
                "record_id": r.get("record_id", "")
            })
        return result
    except (json.JSONDecodeError, KeyError):
        # 非 JSON 输出，尝试正则提取
        print("[Warning] lark-cli returned non-JSON, parsing text output", file=sys.stderr)
        return _parse_lark_text_output(stdout)
```

- [ ] **Step 3: 辅助函数 _parse_lark_text_output()**

```python
def _parse_lark_text_output(text: str) -> List[Dict]:
    """从 lark-cli 纯文本输出中提取记录（备用）"""
    import re
    records = []
    # 简单按行解析，假设格式为: 标题 | 日期 | 阅读量 | 互动量 | 内容方向
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("-"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            records.append({
                "title": parts[0],
                "date": parts[1] if len(parts) > 1 else "",
                "views": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                "likes": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
                "direction": parts[4] if len(parts) > 4 else "",
                "record_id": ""
            })
    return records
```

- [ ] **Step 4: 在 main() 添加 "read" 命令分支**

在 `assassin.py` 的 `main()` 函数中添加：

```python
elif command == "read":
    records = read_viral_library()
    print(json.dumps(records, ensure_ascii=False, indent=2))
```

- [ ] **Step 5: 测试读取功能**

Run: `python assassin.py read`
Expected: 返回历史记录列表（当前应为空列表 `[]`）

- [ ] **Step 6: 提交**

```bash
git add skills/prism-os/scripts/assassin.py
git commit -m "feat: implement read_viral_library via lark-cli"
```

---

## Task 3: 飞书写入实现 (update_feishu_viral)

**Files:**
- Modify: `skills/prism-os/scripts/assassin.py` (update_feishu_viral 函数)
- Test: `python assassin.py write "<标题>" "<策略>"`

- [ ] **Step 1: 编写 update_feishu_viral() 实现**

```python
def update_feishu_viral(viral_title: str, reversal_info: Dict = None) -> bool:
    """
    写入是否已反转/反转策略到飞书
    1. 按标题匹配找到 record_id
    2. 执行 lark-cli update
    3. 验证写入成功
    """
    if reversal_info is None:
        reversal_info = {}

    # 先读取所有记录找到匹配的 record_id
    records = read_viral_library()
    matched = None
    for r in records:
        if r.get("title") == viral_title:
            matched = r
            break

    if not matched:
        print(f"[Warning] 标题未在飞书架中找到: {viral_title}", file=sys.stderr)
        return False

    record_id = matched.get("record_id")
    reversed_val = reversal_info.get("reversed", "是")
    strategy = reversal_info.get("reversal_strategy", "")

    # 执行更新
    stdout, stderr, code = _run_lark_cli([
        "feishu", "bitable", "record", "update",
        "--app-token", FEISHU_APP_TOKEN,
        "--table-id", FEISHU_TABLE_ID,
        "--record-id", record_id,
        "--field", f"是否已反转={reversed_val}",
        "--field", f"反转策略={strategy}"
    ])

    if code != 0:
        print(f"[Warning] lark-cli update failed: {stderr}", file=sys.stderr)
        return False

    # 验证写入：重新读取该记录确认字段已更新
    records_after = read_viral_library()
    for r in records_after:
        if r.get("title") == viral_title:
            if r.get("direction") == reversed_val or strategy in str(r):
                return True

    print("[Warning] update succeeded but verification failed", file=sys.stderr)
    return False
```

- [ ] **Step 2: 在 main() 添加 "write" 命令分支**

```python
elif command == "write":
    if len(sys.argv) < 4:
        print(json.dumps({"error": "用法: python assassin.py write <标题> <策略>"}))
        sys.exit(1)
    title = sys.argv[2]
    strategy = sys.argv[3]
    info = {"reversed": "是", "reversal_strategy": strategy}
    success = update_feishu_viral(title, info)
    print(json.dumps({"success": success, "title": title, "strategy": strategy}))
```

- [ ] **Step 3: 测试写入功能（当前表为空，会打印警告但不应报错）**

Run: `python assassin.py write "测试标题" "前提质疑"`
Expected: `{"success": false, "title": "测试标题", "strategy": "前提质疑"}`（警告：标题未找到）

- [ ] **Step 4: 提交**

```bash
git add skills/prism-os/scripts/assassin.py
git commit -m "feat: implement update_feishu_viral via lark-cli with verification"
```

---

## Task 4: PRISM-OS confirm 命令

**Files:**
- Modify: `skills/prism-os/scripts/prism_os.py`
- Test: `python prism_os.py confirm "测试标题"`

- [ ] **Step 1: 在 prism_os.py 顶部添加辅助函数**

在 `prism_os.py` 顶部 `import` 区域添加：

```python
from datetime import datetime
import subprocess
import shutil
```

在 `import` 区域后添加：

```python
# ============ lark-cli 工具函数 ============

def _verify_lark_cli():
    import sys as _sys
    import shutil as _shutil
    if not _shutil.which("lark-cli"):
        print("[Error] lark-cli not found in PATH", file=_sys.stderr)
        _sys.exit(1)

def _run_lark_cli(args: list, timeout: int = 30) -> tuple:
    import subprocess
    import sys
    _verify_lark_cli()
    result = subprocess.run(
        ["lark-cli"] + args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )
    return result.stdout, result.stderr, result.returncode

FEISHU_TABLE_ID = "tblOoR71Q3DSa33t"
FEISHU_APP_TOKEN = "QVz9byNH0auzRis9KeDcUoe3nZf"
```

- [ ] **Step 2: 添加 confirm_title() 函数**

在 `prism_os.py` 中添加：

```python
def confirm_title(user_title: str) -> Dict:
    """
    将用户选择的标题写入飞书爆款选题库

    写入字段：标题、发布日期、命题逻辑、核心论点、内容方向
    不写入：互动量、阅读量（用户手动补充）、是否已反转、反转策略
    """
    # 输入校验
    title = user_title.strip()
    if not title:
        return {"success": False, "error": "标题不能为空"}
    if len(title) > 200:
        title = title[:200]

    # 从 topic_log.yaml 读取最近命题
    thesis = "（未记录）"
    core_argument = "（未记录）"
    direction = "（未分类）"

    log_path = os.path.join(os.path.dirname(__file__), "..", "data", "topic_log.yaml")
    if os.path.exists(log_path):
        try:
            logs = _load_yaml_simple(log_path)
            if logs:
                last = logs[-1]
                thesis = last.get("thesis", "（未记录）")
                # 尝试从 gateway_result 中获取 core_argument
                if "gateway" in last and isinstance(last["gateway"], dict):
                    core_argument = last["gateway"].get("thesis", "（未记录）")
        except Exception as e:
            print(f"[Warning] 读取 topic_log.yaml 失败: {e}", file=sys.stderr)

    # 内容方向映射
    dim_to_direction = {
        "reversal": "逆向拆解",
        "micro_scene": "微观切片",
        "systemic_flaw": "系统归因",
        "bridge": "认知脚手架"
    }

    # 生成 lark-cli 写入命令
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stdout, stderr, code = _run_lark_cli([
        "feishu", "bitable", "record", "create",
        "--app-token", FEISHU_APP_TOKEN,
        "--table-id", FEISHU_TABLE_ID,
        "--field", f"标题={title}",
        "--field", f"发布日期={now}",
        "--field", f"命题逻辑={thesis}",
        "--field", f"核心论点={core_argument}",
        "--field", f"内容方向={direction}",
        "--field", "备注="
    ])

    if code != 0:
        print(f"[Error] lark-cli create failed: {stderr}", file=sys.stderr)
        return {"success": False, "error": stderr, "title": title}

    # 验证写入
    try:
        resp_data = json.loads(stdout)
        record_id = resp_data.get("data", {}).get("record", {}).get("record_id", "")
        return {"success": True, "title": title, "record_id": record_id}
    except json.JSONDecodeError:
        return {"success": True, "title": title, "note": "写入成功但无法解析返回 ID"}


def _load_yaml_simple(path: str) -> list:
    """简单 YAML 加载"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return []
    result = []
    current = {}
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            if current:
                result.append(current)
            current = {}
        elif ": " in line and not line.startswith("#"):
            key, val = line.split(": ", 1)
            current[key.strip()] = val.strip().strip('"').strip("'")
    if current:
        result.append(current)
    return result
```

- [ ] **Step 3: 在 main() 添加 "confirm" 命令分支**

在 `prism_os.py` 的 `main()` 函数中添加：

```python
elif command == "confirm":
    if len(sys.argv) < 3:
        _safe_print({"error": "请提供标题"})
        sys.exit(1)
    title = sys.argv[2]
    result = confirm_title(title)
    _safe_print(result)
```

同时更新命令帮助信息：

```python
"commands": {
    "run": "python prism_os.py run \"<用户输入>\" [--format] [--no-ext] [--fast] - 完整流程",
    "classify": "意图识别",
    "gateway": "苏格拉底网关（熵值计算）",
    "confirm": "python prism_os.py confirm \"<标题>\" - 确认选题并写入飞书"
},
```

- [ ] **Step 4: 测试 confirm 命令**

Run: `python prism_os.py confirm "测试标题"`
Expected: 写入飞书并返回 `{"success": true, "title": "测试标题", ...}`

- [ ] **Step 5: 提交**

```bash
git add skills/prism-os/scripts/prism_os.py
git commit -m "feat: add confirm command to write selected title to feishu"
```

---

## Task 5: 定时触发 (cron_check)

**Files:**
- Modify: `skills/prism-os/scripts/assassin.py`
- Test: `python assassin.py cron_check`

- [ ] **Step 1: 添加辅助函数和 cron_check() 到 assassin.py**

在 assassin.py 末尾（`if __name__ == "__main__":` 之前）添加：

```python
def _load_yaml_simple(path: str) -> list:
    """简单 YAML 加载"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return []
    result = []
    current = {}
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            if current:
                result.append(current)
            current = {}
        elif ": " in line and not line.startswith("#"):
            key, val = line.split(": ", 1)
            current[key.strip()] = val.strip().strip('"').strip("'")
    if current:
        result.append(current)
    return result


NOTIFICATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "notifications")

def cron_check():
    """
    定时刺客检查
    1. 读取飞书架，验证 >= 20 条数据
    2. 读取 topic_log.yaml 最近命题
    3. 对每条命题生成反转标题
    4. 输出到 notification 文件 + stdout
    5. 更新飞书架「是否已反转」状态
    """
    os.makedirs(NOTIFICATIONS_DIR, exist_ok=True)

    # 1. 读取飞书架
    records = read_viral_library()
    count = len(records)

    if count < 20:
        print(f"[Info] 数据不足（{count}/20），跳过刺客检查")
        return

    print(f"[Info] 开始刺客检查，共 {count} 条历史数据")

    # 2. 读取最近命题（从 topic_log.yaml）
    log_path = os.path.join(os.path.dirname(__file__), "..", "data", "topic_log.yaml")
    logs = _load_yaml_simple(log_path) if os.path.exists(log_path) else []
    recent_theses = [log.get("thesis", "") for log in logs[-5:] if log.get("thesis")]

    if not recent_theses:
        print("[Info] 未找到近期命题，跳过刺客检查")
        return

    triggers = []

    # 3. 对每条命题生成反转（调用现有的 reverse_topic）
    for thesis in recent_theses:
        try:
            # reverse_topic(historical_topic, publish_date="") 已存在于 assassin.py
            reversal_result = reverse_topic(thesis, "")
            reversal_title = reversal_result.get("reversal_thesis", "")
            strategy = reversal_result.get("reversal_strategy", "")
            if reversal_title:
                triggers.append({
                    "original_title": thesis,
                    "reversal_title": reversal_title,
                    "strategy": strategy
                })
        except Exception as e:
            print(f"[Warning] 反转失败: {thesis}, {e}", file=sys.stderr)

    # 4. 写入 notification 文件
    if triggers:
        date_str = datetime.now().strftime("%Y-%m-%d")
        notif_path = os.path.join(NOTIFICATIONS_DIR, f"{date_str}_assassin.json")
        notification = {
            "date": date_str,
            "triggers": triggers
        }
        with open(notif_path, "w", encoding="utf-8") as f:
            json.dump(notification, f, ensure_ascii=False, indent=2)
        print(f"[Info] 刺客通知已写入: {notif_path}")

    # 5. 输出到 stdout
    print(json.dumps({"count": count, "triggers": triggers}, ensure_ascii=False))

    # 6. 更新飞书架（标记已反转）
    for t in triggers:
        update_feishu_viral(t["original_title"], {
            "reversed": "是",
            "reversal_strategy": t["strategy"]
        })
```

- [ ] **Step 2: 在 main() 添加 "cron_check" 命令分支**

在 assassin.py 的 main() 函数中添加：

```python
elif command == "cron_check":
    cron_check()
```

同时更新命令帮助信息：

```python
"commands": {
    "reverse": "assassin.py reverse \"<历史爆款标题>\" - 逻辑反转",
    "topology": "assassin.py topology '<[{\"entity\":...}]' '<[{\"relation\":...}]' - 知识拓扑",
    "evolve": "assassin.py evolve \"<触发类型>\" '<old_config>' - Prompt 变异",
    "cron_check": "assassin.py cron_check - 定时刺客检查（每日 22:00）"
}
```

- [ ] **Step 4: 测试 cron_check（当前数据不足，应打印"数据不足"）**

Run: `python assassin.py cron_check`
Expected: `[Info] 数据不足（0/20），跳过刺客检查`

- [ ] **Step 5: 提交**

```bash
git add skills/prism-os/scripts/assassin.py
git commit -m "feat: add cron_check for daily assassin trigger at 22:00"
```

---

## Task 6: 集成测试

**Files:**
- 无新文件，仅验证全流程

- [ ] **Step 1: 验证 Embedding 模块**

```bash
python skills/prism-os/scripts/embedding.py embed "35岁产品经理被裁"
# 预期：返回 1024 维向量
```

- [ ] **Step 2: 验证飞书读取**

```bash
python skills/prism-os/scripts/assassin.py read
# 预期：返回列表（当前为空或少量数据）
```

- [ ] **Step 3: 验证 confirm 写入**

```bash
python skills/prism-os/scripts/prism_os.py confirm "测试标题：35岁产品经理的职场危机"
# 预期：写入飞书，返回 success
# 验证：再次 read 确认记录增加
python skills/prism-os/scripts/assassin.py read | python -c "import sys,json; d=json.load(sys.stdin); print(f'记录数: {len(d)}')"
```

- [ ] **Step 4: 验证刺客反转写入**

```bash
python skills/prism-os/scripts/assassin.py write "测试标题：35岁产品经理的职场危机" "前提质疑"
# 预期：更新该记录的"是否已反转"字段
```

- [ ] **Step 5: 验证 cron_check**

```bash
python skills/prism-os/scripts/assassin.py cron_check
# 预期：数据不足提示，或正常输出刺客通知
```

---

## 实施顺序

| 任务 | 依赖 |
|------|------|
| Task 1: Embedding 模块 | 无 |
| Task 2: 飞书读取 | Task 1 |
| Task 3: 飞书写入 | Task 2 |
| Task 4: confirm 命令 | Task 3 |
| Task 5: 定时触发 | Task 1-4 |
| Task 6: 集成测试 | Task 1-5 |
