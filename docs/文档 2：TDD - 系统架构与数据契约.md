# 文档 2：TDD - 系统架构与数据契约


## 一、架构设计哲学

PRISM-OS 采用 **Adapter（适配器）模式** 实现逻辑主权与环境解耦。核心原则：

1. **逻辑层不依赖具体实现**：所有外部调用通过接口契约（Interface Contract）隔离。

2. **数据持久化优先**：每次操作必须写入结构化日志，确保系统具备“记忆”。

3. **成本编排**：根据任务复杂度动态分配模型资源（Haiku 用于网关，Sonnet 用于生成，Opus 用于审计）。

---

## 二、系统分层架构

```plaintext
┌─────────────────────────────────────────────────┐
│            User Interface Layer                 │
│   (CLI / Web UI / API Gateway)                  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│          Orchestration Layer                    │
│   (Workflow Engine + Task Router)               │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│            Core Logic Layer                     │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Socratic     │  │ Prism        │            │
│  │ Gateway      │  │ Engine       │            │
│  └──────────────┘  └──────────────┘            │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Logic        │  │ Gap          │            │
│  │ Auditor      │  │ Analyzer     │            │
│  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│           Adapter Layer                         │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Knowledge    │  │ Reality      │            │
│  │ Gateway      │  │ Anchor       │            │
│  └──────────────┘  └──────────────┘            │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ LLM          │  │ Storage      │            │
│  │ Router       │  │ Manager      │            │
│  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         External Services                       │
│  (Anthropic API / Serper / Local Files)         │
└─────────────────────────────────────────────────┘
```

---

## 三、核心接口契约（Interface Contracts）

### 1. IKnowledgeGateway（知识网关）

**职责：** 从外部数据源检索素材并计算匹配度。

```python
from abc import ABC, abstractmethod
from typing import List, Dict

class IKnowledgeGateway(ABC):
    
    @abstractmethod
    def fetch_context(self, query: str, limit: int = 10) -> List[Dict]:
        """
        从知识库检索相关素材。
        
        Args:
            query: 检索关键词或命题
            limit: 返回结果数量上限
            
        Returns:
            [
                {
                    "source": "文件路径或 URL",
                    "title": "素材标题",
                    "content": "素材正文片段",
                    "relevance_score": 0.85
                },
                ...
            ]
        """
        pass
    
    @abstractmethod
    def analyze_gap(self, thesis: str, context: List[Dict]) -> Dict:
        """
        计算命题与现有素材的缺口。
        
        Args:
            thesis: 用户命题
            context: fetch_context 返回的素材列表
            
        Returns:
            {
                "gap_score": 0.65,  # 0-1，越高表示缺口越大
                "missing_evidence": ["需要的数据类型1", "需要的案例2"],
                "readiness": 0.35  # 素材就绪度
            }
        """
        pass
```

**实现示例：**

- `LocalMarkdownGateway`：扫描本地 Markdown 文件夹，使用 Embedding 进行语义检索。

- `YouMindGateway`：调用 YouMind 的 `searchBoards` API.

- `NotionGateway`：通过 Notion API 检索数据库。

---

### 2. IRealityAnchor（现实校验锚）

**职责：** 调用搜索引擎验证选题的新颖度与竞争度。

```python
class IRealityAnchor(ABC):
    
    @abstractmethod
    def validate_novelty(self, title: str, keywords: List[str]) -> Dict:
        """
        校验选题的新颖度。
        
        Args:
            title: 待检验的标题
            keywords: 核心关键词列表
            
        Returns:
            {
                "duplicate_rate": 0.15,  # 查重率
                "competition_level": "蓝海",  # 蓝海/红海/血海
                "top_results": [
                    {"title": "相似标题1", "url": "..."},
                    ...
                ],
                "novelty_score": 0.85  # 新颖度评分
            }
        """
        pass
```

**实现示例：**

- `SerperAdapter`：调用 Serper API 进行搜索。

- `GoogleSearchAdapter`：使用 Google Custom Search API.

---

### 3. ILLMRouter（模型路由器）

**职责：** 根据任务复杂度分配合适的 LLM 模型。

```python
class ILLMRouter(ABC):
    
    @abstractmethod
    def route(self, task_type: str, context_length: int) -> str:
        """
        返回适合的模型名称。
        
        Args:
            task_type: "gateway" | "generation" | "audit"
            context_length: 上下文 token 数量
            
        Returns:
            模型标识符，如 "claude-3-5-haiku-20241022"
        """
        pass
    
    @abstractmethod
    def call(self, model: str, prompt: str, max_tokens: int = 4096) -> str:
        """
        调用 LLM 并返回生成结果。
        """
        pass
```

**成本编排策略：**

- **网关拦截（Gateway）：** 使用 Haiku（低成本、快速响应）。

- **标题生成（Generation）：** 使用 Sonnet（平衡质量与成本）。

- **逻辑审计（Audit）：** 使用 Opus（最高推理能力）。

---

### 4. IStorage（持久化存储）

**职责：** 管理配置、日志和词汇指纹库。

```python
class IStorage(ABC):
    
    @abstractmethod
    def save_log(self, entry: Dict) -> None:
        """
        追加写入选题日志。
        
        Args:
            entry: {
                "timestamp": "2026-04-22T15:14:00Z",
                "thesis": "用户命题",
                "candidates": [...],
                "selected": {...},
                "gap_report": {...}
            }
        """
        pass
    
    @abstractmethod
    def load_config(self) -> Dict:
        """
        读取用户配置（受众画像、厌恶词、北极星权重）。
        """
        pass
    
    @abstractmethod
    def update_fingerprint(self, word: str, vector: List[float], preference: int) -> None:
        """
        更新词汇指纹库。
        
        Args:
            word: 词汇
            vector: Embedding 向量
            preference: 偏好值（-1: 厌恶, 0: 中性, 1: 偏好）
        """
        pass
```

---

## 四、数据结构规范（Data Schema）

### 1. `user_config.yaml`

```yaml
# 用户配置文件
identity:
  role: "揭秘者"
  mission: "揭开社会共识与现实之间的裂缝"

audience:
  age_range: [25, 40]
  pain_points:
    - "被主流叙事欺骗"
    - "缺乏深度思考工具"
  
north_star:
  cognitive_gap_weight: 0.5
  readiness_weight: 0.3
  novelty_weight: 0.2

banned_words:
  - "赋能"
  - "降维打击"
  - "破圈"

dimension_weights:
  reversal: 1.0
  micro_scene: 1.0
  systemic_flaw: 1.0
  bridge: 1.0
```

---

### 2. `topic_log.jsonl`

每行一个 JSON 对象，记录完整的选题流程：

```json
{
  "timestamp": "2026-04-22T15:14:00Z",
  "thesis": "AI 时代最大的不公平：它把'会提问'的人变成超人，把'会执行'的人变成垃圾",
  "entropy_score": 2.8,
  "candidates": [
    {
      "dimension": "reversal",
      "title": "为什么 AI 让'提问'比'执行'更值钱？",
      "novelty_score": 0.87,
      "gap_score": 0.42
    },
    ...
  ],
  "selected": {
    "dimension": "reversal",
    "title": "为什么 AI 让'提问'比'执行'更值钱？",
    "final_edit": "AI 时代的残酷真相：为什么会提问的人年薪百万，会执行的人被淘汰？"
  },
  "gap_report": {
    "missing_evidence": ["AI 对不同岗位的冲击数据", "提问能力的量化指标"],
    "readiness": 0.58
  },
  "search_results": [
    {"title": "...", "url": "...", "duplicate_score": 0.12}
  ]
}
```

---

### 3. `vocab_fingerprint.db`（SQLite 示例）

```sql
CREATE TABLE vocabulary (
    word TEXT PRIMARY KEY,
    embedding BLOB,  -- 存储 Embedding 向量（序列化）
    preference INTEGER,  -- -1: 厌恶, 0: 中性, 1: 偏好
    frequency INTEGER,  -- 使用频次
    last_used TIMESTAMP
);

CREATE INDEX idx_preference ON vocabulary(preference);
```

---

## 五、依赖注入示例（Dependency Injection）

使用依赖注入确保逻辑层与具体实现解耦：

```python
class PRISMOrchestrator:
    def __init__(
        self,
        knowledge_gateway: IKnowledgeGateway,
        reality_anchor: IRealityAnchor,
        llm_router: ILLMRouter,
        storage: IStorage
    ):
        self.knowledge = knowledge_gateway
        self.reality = reality_anchor
        self.llm = llm_router
        self.storage = storage
    
    def run_v1(self, user_input: str) -> Dict:
        # 1. 苏格拉底网关
        entropy = self._calculate_entropy(user_input)
        if entropy < 1.5:
            return {"status": "blocked", "message": "请明确你的命题"}
        
        # 2. 棱镜引擎
        candidates = self._generate_candidates(user_input)
        
        # 3. 现实校验
        for c in candidates:
            c["novelty"] = self.reality.validate_novelty(c["title"], [])
        
        # 4. 持久化
        self.storage.save_log({
            "thesis": user_input,
            "candidates": candidates,
            "timestamp": datetime.now().isoformat()
        })
        
        return {"status": "success", "candidates": candidates}
```

---

## 六、技术栈建议

| 层级 | 技术选型 |
| --- | --- |
| **语言** | Python 3.11+ |
| **LLM SDK** | Anthropic Python SDK |
| **向量检索** | FAISS / ChromaDB |
| **搜索 API** | Serper / SerpAPI |
| **存储** | SQLite（本地）/ PostgreSQL（生产） |
| **配置管理** | YAML + Pydantic |
| **日志** | structlog（结构化日志） |
| **测试** | pytest + hypothesis（属性测试） |

---

## 七、关键设计决策

1. **为什么选择 Adapter 模式？**\
   确保系统可以无缝切换数据源（YouMind → 本地文件 → Notion），而不修改核心逻辑。

2. **为什么使用 JSONL 而非数据库存储日志？**\
   简化部署，便于版本控制和数据迁移。生产环境可升级为 PostgreSQL。

3. **为什么需要成本编排？**\
   避免在低价值任务（如意图拦截）上浪费高成本模型调用。

---

## 八、下一步

参考 **文档 3：Core Logic - 核心算法规格书**，了解熵值计算、正交校验等数学化逻辑的实现细节。