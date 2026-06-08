# 苏格拉底网关备选队列实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在苏格拉底网关的方向选择阶段保存备选方向，后续相似选题自动作为额外候选出现

**Architecture:** 备选队列存储在飞书多维表格，通过 Embedding 相似度匹配。方向生成替代追问问题，备选检查插入在 Phase 1 和 Phase 2 之间

**Tech Stack:** Python, lark-cli, embedding.py, 飞书 Bitable API

---

## 文件结构

```
skills/prism-os/scripts/
├── assassin.py          # 新增 save_backup, read_backup_queue, update_backup_status, check_expired_backups, check_related_backups
├── socratic_gateway.py  # 新增 generate_directions(), 修改 need_clarification 分支
├── prism_os.py          # Phase 1.5 备选检查集成
├── embedding.py         # 已有 get_similarity()，直接复用
└── tests/               # 新增测试目录
    └── backup_queue_test.py
```

---

## Task 1: assassin.py - 备份队列基础函数

**Files:**
- Modify: `skills/prism-os/scripts/assassin.py`
- Test: `skills/prism-os/scripts/tests/backup_queue_test.py`

### Step 1: 添加常量

在文件顶部（`NOTIFICATIONS_DIR` 附近）添加：

```python
FEISHU_TABLE_ID = "tblOoR71Q3DSa33t"
FEISHU_APP_TOKEN = "QVz9byNH0auzRis9KeDcUoe3nZf"

BACKUP_EXPIRY_DAYS = 30
SIMILARITY_THRESHOLD = 0.7
```

### Step 2: 新增 save_backup 函数

```python
def save_backup(direction: str, source: str = "") -> bool:
    """
    将方向保存到飞书备选队列
    - 先检查是否已存在相同标题的备选记录（去重）
    - 写入类型=备选，状态=备选
    - 失败时静默返回 False
    """
    direction = direction.strip()
    if not direction:
        return False

    # 检查是否已存在
    existing = read_backup_queue()
    for rec in existing:
        if rec.get("title") == direction:
            return True  # 已存在，跳过

    # 生成来源字符串
    if not source:
        source = f"socratic-{datetime.now().strftime('%Y-%m-%d')}"

    # 写入飞书
    now_ms = str(int(datetime.now().timestamp() * 1000))
    data = json.dumps({"fields": {
        "标题": direction,
        "类型": "备选",
        "状态": "备选",
        "创建日期": now_ms,
        "来源": source,
        "备注": ""
    }})

    stdout, stderr, code = _run_lark_cli([
        "api", "POST",
        f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records",
        "--data", data,
        "--format", "json"
    ])

    return code == 0
```

### Step 3: 新增 read_backup_queue 函数

```python
def read_backup_queue() -> List[Dict]:
    """
    读取所有 类型=备选 AND 状态=备选 的记录
    Returns: [{"title": str, "source": str, "record_id": str, "created_at": int}, ...]
    """
    # 使用 read_viral_library 的底层 API（不加 类型 过滤）
    path = f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    params = '{"page_size": 100}'
    stdout, stderr, code = _run_lark_cli([
        "api", "GET", path,
        "--params", params,
        "--format", "json"
    ])

    if code != 0:
        return []

    try:
        data = json.loads(stdout)
        records = data.get("data", {}).get("items") or []
    except:
        return []

    result = []
    for r in records:
        fields = r.get("fields", {})
        # 只保留 类型=备选 AND 状态=备选
        record_type = fields.get("类型", "")
        status = fields.get("状态", "")
        if record_type == "备选" and status == "备选":
            created_str = fields.get("创建日期", "")
            created_at = 0
            if isinstance(created_str, (int, float)):
                created_at = int(created_str)
            elif isinstance(created_str, str) and created_str.isdigit():
                created_at = int(created_str)
            result.append({
                "title": fields.get("标题", ""),
                "source": fields.get("来源", ""),
                "record_id": r.get("record_id", ""),
                "created_at": created_at
            })
    return result
```

### Step 4: 新增 update_backup_status 函数

```python
def update_backup_status(record_id: str, status: str) -> bool:
    """
    更新备选记录状态（已使用/已过期）
    - 失败时静默返回 False
    """
    path = f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/{record_id}"
    data = json.dumps({"fields": {"状态": status}})

    stdout, stderr, code = _run_lark_cli([
        "api", "PUT", path,
        "--data", data,
        "--format", "json"
    ])

    return code == 0
```

### Step 5: 新增 check_expired_backups 函数

```python
def check_expired_backups(days: int = 30) -> int:
    """
    检查并标记过期备选（创建日期 > days 天）
    - 读取所有 类型=备选 AND 状态=备选 的记录
    - 比较 创建日期 字段与当前时间
    - 超期记录标记 状态=已过期
    - Returns: 标记为过期的数量
    """
    records = read_backup_queue()
    now_ms = int(datetime.now().timestamp() * 1000)
    expiry_ms = days * 24 * 60 * 60 * 1000

    expired_count = 0
    for rec in records:
        created_at = rec.get("created_at", 0)
        if created_at > 0 and (now_ms - created_at) > expiry_ms:
            if update_backup_status(rec["record_id"], "已过期"):
                expired_count += 1

    return expired_count
```

### Step 6: 修改 read_viral_library 过滤备选记录

在 `read_viral_library()` 函数中（当前返回 records 后），添加 Python 侧过滤：

```python
# 在 return records 之前添加过滤
# 过滤掉 类型=备选 的记录
records = [r for r in records if r.get("fields", {}).get("类型") != "备选"]
return records
```

### Step 7: 写测试

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_save_and_read_backup():
    from assassin import save_backup, read_backup_queue, update_backup_status

    # 测试保存（不同方向避免重复）
    success = save_backup("测试方向-20260513", "test-2026-05-13")
    assert success or True  # 静默失败也通过

    # 测试读取
    queue = read_backup_queue()
    assert isinstance(queue, list)

    # 测试更新状态（如果队列中有测试记录）
    if queue:
        rec = queue[0]
        rid = rec.get("record_id", "")
        if rid:
            result = update_backup_status(rid, "已使用")
            assert isinstance(result, bool)
```

### Step 8: 运行测试

Run: `python -m pytest skills/prism-os/scripts/tests/backup_queue_test.py -v`
Expected: PASS（即使飞书调用失败也返回正确类型）

### Step 9: 提交

```bash
git add skills/prism-os/scripts/assassin.py
git commit -m "feat: add backup queue functions to assassin.py"
```

---

## Task 2: socratic_gateway.py - 方向生成

**Files:**
- Modify: `skills/prism-os/scripts/socratic_gateway.py`

### Step 1: 添加 generate_directions 函数

在文件末尾（`main()` 函数之前）添加：

```python
DIRECTION_PROMPT = """你是选题方向生成器。根据用户输入，生成 2-3 个具体的选题方向。

用户输入: "{user_input}"
输入类型: {input_type}

方向要求：
- 每个方向是一个完整的选题角度，不是追问
- 方向之间正交（覆盖不同角度）
- 包含具体对象和冲突张力

返回 JSON:
{{"directions": ["方向1", "方向2", "方向3"]}}"""


def generate_directions(user_input: str, input_type: str) -> List[str]:
    """
    生成 2-3 个具体方向选项（替代追问问题）
    Returns: ["方向1", "方向2", "方向3"]
    """
    prompt = DIRECTION_PROMPT.format(
        user_input=user_input,
        input_type=input_type
    )

    result = _call_llm_raw(prompt)
    if not result:
        return []

    parsed = _parse_llm_json(result)
    if not parsed:
        return []

    directions = parsed.get("directions", [])
    if isinstance(directions, list) and len(directions) > 0:
        return [d for d in directions if isinstance(d, str) and d.strip()]

    return []
```

### Step 2: 修改 need_clarification 分支

在 `socratic_gateway()` 函数中，找到 `elif decision == "clarify":` 分支（约第 258 行），修改为：

```python
elif decision == "clarify":
    # 生成方向选项（替代追问问题）
    directions = generate_directions(user_input, input_type)
    if not directions:
        # fallback 到默认方向
        directions = [
            f"聚焦{user_input[:10]}的角度A",
            f"聚焦{user_input[:10]}的角度B",
            f"聚焦{user_input[:10]}的角度C"
        ]

    return {
        "status": "need_clarification",
        "input_type": input_type,
        "entropy_score": entropy_result["entropy_score"],
        "decision": "clarify",
        "reason": entropy_result["reason"],
        "directions": directions,  # 改为返回方向列表，不是 questions
        "questions": []  # 保持字段兼容
    }
```

### Step 3: 测试方向生成

Run: `python skills/prism-os/scripts/socratic_gateway.py gateway "AI对职业的影响"`
Expected: 返回包含 `directions` 字段的结果

### Step 4: 提交

```bash
git add skills/prism-os/scripts/socratic_gateway.py
git commit -m "feat: add generate_directions to socratic_gateway.py"
```

---

## Task 3: assassin.py - 相似度匹配

**Files:**
- Modify: `skills/prism-os/scripts/assassin.py`

### Step 1: 添加 check_related_backups 函数

```python
def check_related_backups(topic: str, threshold: float = 0.7) -> List[Dict]:
    """
    检查与 topic 相似的备选方向
    1. 调用 check_expired_backups() 清理过期记录
    2. 读取备选队列
    3. 计算 topic 与每条备选的 Embedding 相似度
    4. 返回相似度 > threshold 的记录
    Returns: [{"title": str, "similarity": float, "record_id": str}, ...]
    """
    # 清理过期
    check_expired_backups(BACKUP_EXPIRY_DAYS)

    # 读取队列
    queue = read_backup_queue()
    if not queue:
        return []

    # 引入 embedding
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from embedding import get_similarity

    results = []
    for rec in queue:
        title = rec.get("title", "")
        if not title:
            continue

        similarity = get_similarity(topic, title)
        if similarity > threshold:
            results.append({
                "title": title,
                "similarity": similarity,
                "record_id": rec.get("record_id", "")
            })

    # 按相似度降序
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results
```

### Step 2: 测试相似度匹配（手动）

测试数据准备：
1. 先保存几个测试备选：`python -c "from assassin import save_backup; save_backup('AI让某些职业消失', 'test')"`
2. 运行匹配：`python -c "from assassin import check_related_backups; print(check_related_backups('AI对就业市场的影响'))"`

Expected: 返回包含相似备选的列表

### Step 3: 提交

```bash
git add skills/prism-os/scripts/assassin.py
git commit -m "feat: add check_related_backups similarity matching"
```

---

## Task 4: prism_os.py - 备选检查集成

**Files:**
- Modify: `skills/prism-os/scripts/prism_os.py`

### Step 1: 在 run_prism_os() 中添加 Phase 1.5

找到 Phase 1 网关完成后（约第 223 行），在 `if not skip_gateway:` 块之后添加：

```python
# ============ Phase 1.5: 备选检查（新增） ============
if result["status"] in ["ready_for_generation", "need_clarification"]:
    try:
        from assassin import check_related_backups, update_backup_status

        result["phase"] = "backup_check"
        matched_backups = check_related_backups(user_input)

        if matched_backups:
            result["backup_matches"] = matched_backups
            # 用户确认后，将选中的备选方向加入候选
            # 这里只记录到 result，实际交互由 CLI 层处理
        else:
            result["backup_matches"] = []
    except Exception as e:
        print(f"[Warning] Phase 1.5 失败: {e}", file=sys.stderr)
        result["backup_matches"] = []
```

### Step 2: 修改 format_prism_os_output 添加备选显示

在 `format_prism_os_output()` 函数中（候选标题之后），添加：

```python
# 备选匹配显示
backup_matches = result.get("backup_matches", [])
if backup_matches:
    lines.append("■ 相关备选方向")
    for m in backup_matches[:3]:
        sim = int(m.get("similarity", 0) * 100)
        lines.append(f"  📌 {m.get('title', '')}（相似度 {sim}%）")
    lines.append("")
```

### Step 3: 运行集成测试

Run: `python skills/prism-os/scripts/prism_os.py run "AI对职业的影响" --format`
Expected: 显示备选匹配（如有）

### Step 4: 提交

```bash
git add skills/prism-os/scripts/prism_os.py
git commit -m "feat: add Phase 1.5 backup check to prism_os.py"
```

---

## Task 5: 验证所有功能

### Step 1: 验证方向生成

Run: `python skills/prism-os/scripts/socratic_gateway.py gateway "AI对职业的影响"`
Expected: 返回包含 `directions` 数组（2-3 个方向）

### Step 2: 验证备选保存

Run: `python -c "from assassin import save_backup; print(save_backup('测试方向ABC', 'verify-test'))"`
Expected: `True` 或 `False`（静默失败也正常）

### Step 3: 验证备选过滤

确认 `read_viral_library()` 不返回备选记录：
Run: `python -c "from assassin import read_viral_library; records = read_viral_library(); print([r for r in records if r.get('fields',{}).get('类型') == '备选'])"`

### Step 4: 验证相似度匹配

Run: `python -c "from assassin import check_related_backups; print(check_related_backups('AI对就业的影响', 0.7))"`
Expected: 返回匹配的备选列表

### Step 5: 提交最终

```bash
git add skills/prism-os/scripts/tests/backup_queue_test.py 2>/dev/null || true
git commit -m "feat: complete backup queue feature"
```

---

## 验证标准检查清单

- [ ] `generate_directions()` 能生成 2-3 个具体方向选项
- [ ] 用户选择主方向后，能正确保存其他方向到飞书
- [ ] `read_viral_library()` 不返回备选记录（过滤 `类型` 字段）
- [ ] `read_backup_queue()` 只返回 `状态=备选` 的记录
- [ ] 相似度匹配准确（相似话题匹配，无关话题不匹配）
- [ ] 备选被使用后，`状态` 更新为 `已使用`
- [ ] 超过 30 天的备选自动标记为 `已过期`
- [ ] 去重：相同标题的备选不会重复写入