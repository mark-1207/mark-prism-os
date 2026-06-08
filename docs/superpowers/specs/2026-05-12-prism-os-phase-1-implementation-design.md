# PRISM-OS Phase 1 实现设计

**日期：** 2026-05-12
**范围：** Embedding 配置化 · 飞书读写 · 定时触发 · 选标题确认机制

---

## 1. Embedding 独立模块

### 目标
新建 `skills/prism-os/scripts/embedding.py`，提供独立的 Embedding 生成和相似度计算能力，供正交性校验（Phase 2）和刺客机制（Phase 7）调用。

### 环境变量

| 变量 | 来源 | 用途 |
|------|------|------|
| `ZHIPU_API_KEY` | 已在全局环境变量中设置 | 智谱 Embedding API Key |
| `ZHIPU_EMBEDDING_MODEL` | `embedding-2`（默认） | 模型名 |

> **注意**：API Key 通过 `os.getenv("ZHIPU_API_KEY")` 读取，代码中不硬编码。

### 核心接口

```python
def embed(text: str, model: str = None) -> List[float]:
    """
    生成文本向量
    流程：检查缓存 → 有则返回 → 无则调智谱API → 写入缓存 → 返回向量
    """

def get_similarity(text_a: str, text_b: str) -> float:
    """
    计算两个标题的相似度
    公式：0.4 × Jaccard + 0.6 × Cosine(向量)
    Jaccard 基于分词集合，Cosine 基于 Embedding 向量
    """

def clear_cache():
    """清空所有缓存（仅调试用）"""
```

### 缓存策略

- **存储位置：** `data/embedding_cache.json`
- **索引方式：** `md5(text)` → 向量列表
- **更新策略：** 只增不减（永不失效）
- **损坏恢复：** JSON 解析失败时，自动备份损坏文件（`embedding_cache.json.bak`）并重建空缓存
- **格式：**
  ```json
  {
    "version": 1,
    "cache": {
      "md5hash": [0.123, -0.456, ...]
    }
  }
  ```

### Cosine 相似度实现

```python
import numpy as np

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """计算两个向量的 Cosine 相似度"""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### 健壮性处理

- **API 超时：** 30s 超时，超时返回 `None`，调用方自行处理降级
- **API 错误码：** 捕获 HTTP 错误，返回 `None` + 错误信息
- **缓存 miss：** 返回 `None`，调用方降级到纯 Jaccard

---

## 2. 飞书读写（lark-cli）

### 目标
实现 `assassin.py` 中的 `read_viral_library()` 和 `update_feishu_viral()`，基于 lark-cli subprocess 调用，解析结构化输出。

### 前置验证

首次运行时，通过 `subprocess.run(["lark-cli", "--version"])` 验证 lark-cli 是否在 PATH 中。验证失败时打印明确错误信息并退出（`sys.exit(1)`）。

### 表 ID 常量

```python
FEISHU_TABLE_ID = "tblOoR71Q3DSa33t"
FEISHU_APP_TOKEN = "QVz9byNH0auzRis9KeDcUoe3nZf"  # 示例 token（待用户确认）
```

### 读取：`read_viral_library()`

```bash
lark-cli feishu bitable record list \
  --app-token <FEISHU_APP_TOKEN> \
  --table-id <FEISHU_TABLE_ID> \
  --page-size 100
```

**解析逻辑：**
- 捕获 stdout，尝试 JSON parse
- 如果不是 JSON（老版本纯文本），用正则提取关键字段
- 返回 `List[Dict]`，每条记录包含：`title`, `date`, `views`, `likes`, `direction`

**容错：**
- 指定 `encoding="utf-8", errors="replace"`
- 解析失败时打印警告，返回空列表

### 写入：`update_feishu_viral(viral_title, reversal_info)`

**写入字段：**

| 字段 | 来源 |
|------|------|
| 是否已反转 | `reversal_info["reversed"]` → select: "是" / "否" |
| 反转策略 | `reversal_info["reversal_strategy"]` → select |

```bash
lark-cli feishu bitable record update \
  --app-token <FEISHU_APP_TOKEN> \
  --table-id <FEISHU_TABLE_ID> \
  --record-id <record_id> \
  --field "是否已反转=是" \
  --field "反转策略=<strategy>"
```

**逻辑：**
1. 先读出所有记录，按标题匹配 `viral_title`
2. 找到对应 `record_id`
3. 执行 update 命令
4. **验证写入**：读取更新后的记录，确认字段已更新
5. 超时/失败时打印警告，**不抛异常**，返回 `False`

**写入确认：** 写入后返回成功/失败状态，调用方打印明确提示。

---

## 3. 补救机制：confirm 命令

### 目标
PRISM-OS 输出候选标题后，用户选择一个标题并确认，系统自动写入选题信息到飞书「爆款选题库」，为刺客机制提供数据来源。

### 命令接口

```bash
python prism_os.py confirm "<用户选择的标题>"
```

### 写入字段

| 字段 | 来源 | 类型 |
|------|------|------|
| 标题 | 用户传入 | text |
| 发布日期 | confirm 执行时时间 | datetime |
| 命题逻辑 | 从 `topic_log.yaml` 最后一条读取 `thesis`，文件不存在时写入"（未记录）" | text |
| 核心论点 | 从 `topic_log.yaml` 最后一条读取 `gateway.thesis`，文件不存在或格式异常时写入"（未记录）" | text |
| 内容方向 | 从 dimension 映射（见下表） | select |
| 备注 | 空 | text |

**不写入的字段（用户在飞书界面手动补充）：**
- 互动量、阅读量（需外部数据）
- 是否已反转、反转策略（刺客机制后续写入）

### 实现位置
`prism_os.py` 新增 `confirm_title()` 函数，调用 lark-cli 写入。

### 内容方向映射

| dimension | 飞书 select 选项 |
|-----------|------------------|
| `reversal` | 逆向拆解 |
| `micro_scene` | 微观切片 |
| `systemic_flaw` | 系统归因 |
| `bridge` | 认知脚手架 |

### 输入校验

用户传入标题时：
- 去除首尾空白字符
- 限制最大长度 200 字符，超长截断
- 标题不能为空，否则打印错误提示并退出

---

## 4. 定时触发

### 目标
每天晚上 22:00 自动检查刺客触发条件，生成反转标题并推送通知。

### Cron 配置

```
0 22 * * * python /path/to/prism_engine/scripts/assassin.py cron_check >> /path/to/logs/cron_assassin.log 2>&1
```

### `assassin.py cron_check` 逻辑

```
1. read_viral_library() → 获取飞书架所有记录
2. 检查数据量是否 >= 20
   - < 20：打印 "数据不足（{n}/20），跳过刺客检查"，退出
3. 读取 topic_log.yaml 最近 N 条命题
4. 对每条命题调用刺客反转逻辑
5. 生成反转标题后：
   - 输出到 stdout（方便 cron 日志捕获）
   - 可选：写入 notification 文件
6. 更新飞书架「是否已反转」状态
```

### 推送通知形式

通知写入 `data/notifications/YYYY-MM-DD_assassin.json`：

```json
{
  "date": "2026-05-12",
  "triggers": [
    {
      "original_title": "35岁产品经理被裁",
      "reversal_title": "35岁不是被裁的原因，是被留下的原因",
      "strategy": "前提质疑"
    }
  ]
}
```

用户次日查看文件或在 PRISM-OS 运行时查看。

---

## 5. 实施顺序

| 顺序 | 任务 | 依赖 |
|------|------|------|
| 1 | Embedding 独立模块 (`embedding.py`) | 无 |
| 2 | 飞书读取实现 (`read_viral_library`) | lark-cli 路径验证 |
| 3 | 飞书写入实现 (`update_feishu_viral`) | lark-cli 路径验证 |
| 4 | PRISM-OS confirm 命令 | 步骤 3 飞书写入完成后才能开发 |
| 5 | 定时触发 cron 配置 | 1-4 完成 |
| 6 | 集成测试（完整流程） | 1-5 |

---

## 6. 测试验证

每个任务完成后执行验证：

| 任务 | 验证命令 | 预期结果 |
|------|---------|---------|
| Embedding 模块 | `python embedding.py embed "测试标题"` | 返回 1024 维向量 |
| 飞书读取 | `python assassin.py read` | 返回历史记录列表 |
| 飞书写入 | `python assassin.py write "<title>" <strategy>` | 记录是否已反转字段更新 |
| Confirm 命令 | `python prism_os.py confirm "测试标题"` | 飞书架新增一条记录 |
| 定时触发 | 手动 `python assassin.py cron_check` | 输出通知 JSON |
