# 苏格拉底网关备选队列设计

## 目标

在苏格拉底网关（Phase 1）的方向选择阶段，允许用户将未选中的方向保存到"备选队列"，后续处理相似选题时自动作为额外候选出现。

## 前置依赖

当前 `socratic_gateway.py` 的 `need_clarification` 路径只返回追问问题（如"你想表达的核心观点是什么？"），没有方向选项。本特性需要先实现**方向生成**功能。

## 交互流程

### Step 1: 方向生成（新增）

当 `decision == "clarify"` 时，不再返回追问问题，而是生成 2-3 个具体方向选项：

```
请选择一个更精确的方向：
1️⃣AI让某些职业消失
2️⃣AI时代新职业机会
3️⃣职业选择方法论转变（认知升级）

你的选择: 3
```

### Step 2: 备选保存（新增）

选择主方向后，提示是否保存其他方向：

```
是否要将其他方向加入备选队列？
(输入编号，逗号分隔，如 1,2 或回车跳过): 1,2

✓ 已将2个方向加入备选队列
```

**边界情况**：如果用户选择所有方向（如输入 `1,2,3`），跳过备选提示。

## 存储设计

### 飞书多维表格

复用爆款选题库同一张表，通过 `类型` 字段区分记录：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 类型 | 单选 | `爆款` / `备选`（区分记录类型） |
| 标题 | 文本 | 方向描述文本 |
| 状态 | 单选 | `备选` / `已使用` / `已过期`（仅备选记录使用） |
| 来源 | 文本 | 格式：`socratic-{YYYY-MM-DD}-{用户输入摘要}` |
| 备注 | 文本 | 原始用户输入 |

### 数据结构

```json
{
  "fields": {
    "标题": "AI让某些职业消失",
    "类型": "备选",
    "状态": "备选",
    "创建日期": 1747152000000,
    "来源": "socratic-2026-05-13-AI对职业",
    "备注": "用户输入：AI对职业的影响"
  }
}
```

- `创建日期`：Unix 时间戳（毫秒），用于过期判断
- `来源`：格式 `socratic-{YYYY-MM-DD}-{用户输入前10字符}`

### 与现有代码的兼容

`read_viral_library()` 需要过滤 `类型` 字段：
- **过滤方式**：Python 侧过滤（不修改 lark-cli API 调用）
- 读取全部记录后，过滤掉 `类型=备选` 的记录
- 保留 `类型=爆款` 或 `类型` 字段不存在的记录（兼容旧数据）
- 备选记录不会混入刺客机制

`read_backup_queue()` 同样使用 Python 侧过滤：
- 读取全部记录后，只保留 `类型=备选 AND 状态=备选` 的记录

## 相似度匹配

### 匹配流程

当用户输入新选题时（在 Phase 1 通过后、Phase 2 开始前）：

1. 调用 `check_expired_backups()` 标记过期备选（>30天）
2. 从飞书读取所有 `类型=备选 AND 状态=备选` 的记录
3. 计算新选题与每条备选的 Embedding 相似度（`0.4 × Jaccard + 0.6 × Cosine`）
4. 相似度 > 阈值（默认 0.7）的备选方向作为额外候选呈现
5. 用户确认后，将选中的备选方向加入本次候选列表，并标记 `状态=已使用`

### 呈现格式

```
检测到2个相关备选方向：
  📌 AI让某些职业消失（相似度 0.82）
  📌 AI时代新职业机会（相似度 0.75）

是否将它们加入本次候选？(y/n):
```

### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| SIMILARITY_THRESHOLD | 0.7 | 相似度阈值，可配置 |
| BACKUP_EXPIRY_DAYS | 30 | 备选有效期，超期自动标记"已过期" |
| MAX_BACKUP_RECORDS | 100 | 飞书 API 单页限制，超过则截断 |

## 实现要点

### 文件改动

- `scripts/socratic_gateway.py` — 添加 `generate_directions()` 方向生成，修改 `socratic_gateway()` 返回方向选项
- `scripts/assassin.py` — 新增 `save_backup()`、`read_backup_queue()`、`update_backup_status()`、`check_expired_backups()`，修改 `read_viral_library()` 过滤 `类型` 字段
- `scripts/embedding.py` — 已有 `get_similarity()`，直接复用
- `scripts/prism_os.py` — 在 Phase 1 和 Phase 2 之间插入备选检查逻辑

### 新增函数

```python
# socratic_gateway.py
def generate_directions(user_input: str, input_type: str) -> List[str]:
    """
    生成 2-3 个具体方向选项（替代追问问题）
    Returns: ["方向1", "方向2", "方向3"]
    """

DIRECTION_PROMPT = """你是选题方向生成器。根据用户输入，生成 2-3 个具体的选题方向。

用户输入: "{user_input}"
输入类型: {input_type}

方向要求：
- 每个方向是一个完整的选题角度，不是追问
- 方向之间正交（覆盖不同角度）
- 包含具体对象和冲突张力

返回 JSON:
{{"directions": ["方向1", "方向2", "方向3"]}}"""

# assassin.py
def save_backup(direction: str, source: str = "") -> bool:
    """
    将方向保存到飞书备选队列
    - 先检查是否已存在相同标题的备选记录（去重）
    - 写入类型=备选，状态=备选
    - 失败时静默返回 False
    """

def read_backup_queue() -> List[Dict]:
    """
    读取所有 类型=备选 AND 状态=备选 的记录
    Returns: [{"title": str, "source": str, "record_id": str}, ...]
    """

def update_backup_status(record_id: str, status: str) -> bool:
    """
    更新备选记录状态（已使用/已过期）
    - 失败时静默返回 False
    """

def check_related_backups(topic: str, threshold: float = 0.7) -> List[Dict]:
    """
    检查与 topic 相似的备选方向
    1. 调用 check_expired_backups() 清理过期记录
    2. 读取备选队列
    3. 计算 topic 与每条备选的 Embedding 相似度
    4. 返回相似度 > threshold 的记录
    Returns: [{"title": str, "similarity": float, "record_id": str}, ...]
    """

def check_expired_backups(days: int = 30) -> int:
    """
    检查并标记过期备选（创建日期 > days 天）
    - 读取所有 类型=备选 AND 状态=备选 的记录
    - 比较 创建日期 字段与当前时间
    - 超期记录标记 状态=已过期
    - Returns: 标记为过期的数量
    """
```

### 流程集成（`prism_os.py`）

```
Phase 0: 意图识别
Phase 1: 苏格拉底网关
  ├── 决策=blocked → 返回
  ├── 决策=clarify → 生成方向选项 → 用户选择 → 保存备选
  └── 决策=pass → 继续
Phase 1.5: 备选检查（新增）
  ├── check_related_backups(用户输入)
  ├── 有匹配 → 提示用户是否加入
  └── 无匹配 → 跳过
Phase 2: 棱镜引擎（使用合并后的候选列表）
Phase 3+: 后续流程
```

## 错误处理

Phase 1.5（备选检查）遵循 `prism_os.py` 现有模式：
- 使用 `try/except` 包裹
- 失败时 `print(f"[Warning] Phase 1.5 失败: {e}", file=sys.stderr)`
- 继续执行 Phase 2，不中断流程

`save_backup()` 和 `read_backup_queue()` 静默失败（返回 `False` / `[]`），与 `read_viral_library()` 一致。

## 记录上限

`MAX_BACKUP_RECORDS = 100` 是有意限制：
- 飞书 API 单页返回 100 条，不实现分页
- 超过 100 条时，只处理最新的 100 条
- 实际使用中备选队列不太可能超过此限制

## 验证标准

1. `generate_directions()` 能生成 2-3 个具体方向选项
2. 用户选择主方向后，能正确保存其他方向到飞书
3. `read_viral_library()` 不返回备选记录（过滤 `类型` 字段）
4. `read_backup_queue()` 只返回 `状态=备选` 的记录
5. 相似度匹配准确（相似话题匹配，无关话题不匹配）
6. 备选被使用后，`状态` 更新为 `已使用`
7. 超过 30 天的备选自动标记为 `已过期`
8. 去重：相同标题的备选不会重复写入
