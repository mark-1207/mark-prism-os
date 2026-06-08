# 文档 4：Adapter Contract - 接口适配协议


## 一、适配器设计原则

Adapter（适配器）模式的核心目标是**解耦逻辑层与外部依赖**。所有外部服务（LLM、搜索引擎、知识库、存储）必须通过统一接口访问，确保：

1. **可替换性**：更换服务提供商不影响核心逻辑。

2. **可测试性**：可以用 Mock 对象替代真实服务进行单元测试。

3. **成本可控**：通过适配器层统一监控和限流。

---

## 二、适配器接口规范

### 2.1 IKnowledgeGateway（知识网关适配器）

#### 接口定义

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class IKnowledgeGateway(ABC):
    
    @abstractmethod
    def fetch_context(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        从知识库检索相关素材。
        
        Args:
            query: 检索关键词或命题
            limit: 返回结果数量上限
            filters: 可选过滤条件，如 {"type": "article", "date_after": "2024-01-01"}
            
        Returns:
            [
                {
                    "source": "文件路径或 URL",
                    "title": "素材标题",
                    "content": "素材正文片段（前 500 字）",
                    "relevance_score": 0.85,
                    "metadata": {"author": "...", "date": "..."}
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
                "readiness": 0.35  # 素材就绪度（1 - gap_score）
            }
        """
        pass
```

#### 实现示例 1:LocalMarkdownGateway

```python
import os
from pathlib import Path
from typing import List, Dict
import chromadb

class LocalMarkdownGateway(IKnowledgeGateway):
    """
    从本地 Markdown 文件夹检索素材。
    """
    
    def __init__(self, folder_path: str, embedding_model):
        self.folder = Path(folder_path)
        self.embedding = embedding_model
        self.db = chromadb.Client()
        self.collection = self.db.create_collection("local_knowledge")
        self._index_files()
    
    def _index_files(self):
        """
        索引所有 Markdown 文件。
        """
        for md_file in self.folder.rglob("*.md"):
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.collection.add(
                    documents=[content[:500]],  # 只索引前 500 字
                    metadatas=[{"source": str(md_file)}],
                    ids=[str(md_file)]
                )
    
    def fetch_context(self, query: str, limit: int = 10, filters=None) -> List[Dict]:
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        return [
            {
                "source": results["metadatas"][0][i]["source"],
                "title": Path(results["metadatas"][0][i]["source"]).stem,
                "content": results["documents"][0][i],
                "relevance_score": 1 - results["distances"][0][i]
            }
            for i in range(len(results["ids"][0]))
        ]
    
    def analyze_gap(self, thesis: str, context: List[Dict]) -> Dict:
        # 调用 LLM 进行缺口分析（参考文档 3 的算法 4）
        pass
```

#### 实现示例 2:YouMindGateway

```python
class YouMindGateway(IKnowledgeGateway):
    """
    从 YouMind 平台检索素材。
    """
    
    def __init__(self, api_client):
        self.client = api_client
    
    def fetch_context(self, query: str, limit: int = 10, filters=None) -> List[Dict]:
        # 调用 YouMind 的 searchBoards API
        response = self.client.search(query=query, scope="library", limit=limit)
        
        return [
            {
                "source": item["url"],
                "title": item["title"],
                "content": item["excerpt"],
                "relevance_score": item["score"],
                "metadata": {"type": item["type"]}
            }
            for item in response["results"]
        ]
    
    def analyze_gap(self, thesis: str, context: List[Dict]) -> Dict:
        # 同上
        pass
```

---

### 2.2 IRealityAnchor（现实校验适配器）

#### 接口定义

```python
class IRealityAnchor(ABC):
    
    @abstractmethod
    def validate_novelty(
        self,
        title: str,
        keywords: List[str],
        search_depth: int = 10
    ) -> Dict:
        """
        校验选题的新颖度。
        
        Args:
            title: 待检验的标题
            keywords: 核心关键词列表
            search_depth: 搜索结果数量
            
        Returns:
            {
                "duplicate_rate": 0.15,  # 查重率（0-1）
                "competition_level": "蓝海",  # 蓝海/红海/血海
                "top_results": [
                    {"title": "相似标题1", "url": "...", "similarity": 0.82},
                    ...
                ],
                "novelty_score": 0.85  # 新颖度评分（1 - duplicate_rate）
            }
        """
        pass
```

#### 实现示例：SerperAdapter

```python
import requests

class SerperAdapter(IRealityAnchor):
    """
    使用 Serper API 进行搜索校验。
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://google.serper.dev/search"
    
    def validate_novelty(self, title: str, keywords: List[str], search_depth: int = 10) -> Dict:
        # 1. 构建搜索查询
        query = " ".join(keywords) if keywords else title
        
        # 2. 调用 Serper API
        response = requests.post(
            self.base_url,
            headers={"X-API-KEY": self.api_key},
            json={"q": query, "num": search_depth}
        )
        results = response.json().get("organic", [])
        
        # 3. 计算相似度
        similarities = []
        for result in results:
            sim = self._calculate_similarity(title, result["title"])
            similarities.append({
                "title": result["title"],
                "url": result["link"],
                "similarity": sim
            })
        
        # 4. 计算查重率
        duplicate_rate = max([s["similarity"] for s in similarities]) if similarities else 0
        
        # 5. 判断竞争度
        if duplicate_rate < 0.3:
            competition = "蓝海"
        elif duplicate_rate < 0.7:
            competition = "红海"
        else:
            competition = "血海"
        
        return {
            "duplicate_rate": duplicate_rate,
            "competition_level": competition,
            "top_results": similarities[:5],
            "novelty_score": 1 - duplicate_rate
        }
    
    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """
        使用 Embedding 计算标题相似度。
        """
        vec1 = embedding_model.embed(title1)
        vec2 = embedding_model.embed(title2)
        return cosine_similarity([vec1], [vec2])[0][0]
```

---

### 2.3 ILLMRouter（模型路由适配器）

#### 接口定义

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
    def call(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> str:
        """
        调用 LLM 并返回生成结果。
        """
        pass
```

#### 实现示例：AnthropicRouter

```python
from anthropic import Anthropic

class AnthropicRouter(ILLMRouter):
    """
    使用 Anthropic API 进行模型调用。
    """
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.cost_tracker = {}  # 成本追踪
    
    def route(self, task_type: str, context_length: int) -> str:
        """
        成本编排策略。
        """
        if task_type == "gateway":
            return "claude-3-5-haiku-20241022"  # 低成本
        elif task_type == "generation":
            return "claude-3-5-sonnet-20241022"  # 平衡
        elif task_type == "audit":
            return "claude-opus-4-20250514"  # 高推理
        else:
            return "claude-3-5-sonnet-20241022"
    
    def call(self, model: str, prompt: str, max_tokens: int = 4096, temperature: float = 1.0) -> str:
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 记录成本
        self._track_cost(model, response.usage)
        
        return response.content[0].text
    
    def _track_cost(self, model: str, usage):
        """
        追踪 API 调用成本。
        """
        if model not in self.cost_tracker:
            self.cost_tracker[model] = {"input_tokens": 0, "output_tokens": 0}
        
        self.cost_tracker[model]["input_tokens"] += usage.input_tokens
        self.cost_tracker[model]["output_tokens"] += usage.output_tokens
```

---

### 2.4 IStorage（持久化存储适配器）

#### 接口定义

```python
class IStorage(ABC):
    
    @abstractmethod
    def save_log(self, entry: Dict) -> None:
        """
        追加写入选题日志。
        """
        pass
    
    @abstractmethod
    def load_config(self) -> Dict:
        """
        读取用户配置。
        """
        pass
    
    @abstractmethod
    def update_config(self, config: Dict) -> None:
        """
        更新用户配置。
        """
        pass
    
    @abstractmethod
    def update_fingerprint(self, word: str, vector: List[float], preference: int) -> None:
        """
        更新词汇指纹库。
        """
        pass
    
    @abstractmethod
    def query_fingerprint(self, word: str) -> Optional[Dict]:
        """
        查询词汇偏好。
        """
        pass
```

#### 实现示例：LocalFileStorage

```python
import json
import yaml
from pathlib import Path

class LocalFileStorage(IStorage):
    """
    使用本地文件系统存储数据。
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.config_file = self.data_dir / "user_config.yaml"
        self.log_file = self.data_dir / "topic_log.jsonl"
        self.fingerprint_file = self.data_dir / "vocab_fingerprint.json"
    
    def save_log(self, entry: Dict) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "
")
    
    def load_config(self) -> Dict:
        if not self.config_file.exists():
            return self._create_default_config()
        
        with open(self.config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def update_config(self, config: Dict) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
    
    def update_fingerprint(self, word: str, vector: List[float], preference: int) -> None:
        fingerprints = self._load_fingerprints()
        fingerprints[word] = {"vector": vector, "preference": preference}
        
        with open(self.fingerprint_file, "w", encoding="utf-8") as f:
            json.dump(fingerprints, f, ensure_ascii=False)
    
    def query_fingerprint(self, word: str) -> Optional[Dict]:
        fingerprints = self._load_fingerprints()
        return fingerprints.get(word)
    
    def _load_fingerprints(self) -> Dict:
        if not self.fingerprint_file.exists():
            return {}
        
        with open(self.fingerprint_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _create_default_config(self) -> Dict:
        default = {
            "identity": {"role": "揭秘者", "mission": "揭开社会共识与现实之间的裂缝"},
            "audience": {"age_range": [25, 40], "pain_points": []},
            "north_star": {"cognitive_gap_weight": 0.5, "readiness_weight": 0.3, "novelty_weight": 0.2},
            "banned_words": [],
            "dimension_weights": {"reversal": 1.0, "micro_scene": 1.0, "systemic_flaw": 1.0, "bridge": 1.0}
        }
        self.update_config(default)
        return default
```

---

## 三、依赖注入容器

使用依赖注入容器统一管理适配器实例：

```python
class DIContainer:
    """
    依赖注入容器。
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self._instances = {}
    
    def get_knowledge_gateway(self) -> IKnowledgeGateway:
        if "knowledge_gateway" not in self._instances:
            gateway_type = self.config.get("knowledge_gateway_type", "local")
            
            if gateway_type == "local":
                self._instances["knowledge_gateway"] = LocalMarkdownGateway(
                    folder_path=self.config["local_folder"],
                    embedding_model=self.get_embedding_model()
                )
            elif gateway_type == "youmind":
                self._instances["knowledge_gateway"] = YouMindGateway(
                    api_client=self.get_youmind_client()
                )
        
        return self._instances["knowledge_gateway"]
    
    def get_reality_anchor(self) -> IRealityAnchor:
        if "reality_anchor" not in self._instances:
            self._instances["reality_anchor"] = SerperAdapter(
                api_key=self.config["serper_api_key"]
            )
        
        return self._instances["reality_anchor"]
    
    def get_llm_router(self) -> ILLMRouter:
        if "llm_router" not in self._instances:
            self._instances["llm_router"] = AnthropicRouter(
                api_key=self.config["anthropic_api_key"]
            )
        
        return self._instances["llm_router"]
    
    def get_storage(self) -> IStorage:
        if "storage" not in self._instances:
            self._instances["storage"] = LocalFileStorage(
                data_dir=self.config["data_dir"]
            )
        
        return self._instances["storage"]
```

---

## 四、测试策略

### Mock 适配器示例

```python
class MockKnowledgeGateway(IKnowledgeGateway):
    """
    用于单元测试的 Mock 对象。
    """
    
    def fetch_context(self, query: str, limit: int = 10, filters=None) -> List[Dict]:
        return [
            {
                "source": "mock_source.md",
                "title": "Mock Material",
                "content": "This is mock content for testing.",
                "relevance_score": 0.9
            }
        ]
    
    def analyze_gap(self, thesis: str, context: List[Dict]) -> Dict:
        return {
            "gap_score": 0.5,
            "missing_evidence": ["Mock Evidence"],
            "readiness": 0.5
        }
```

---

## 五、下一步

参考 **文档 5：Prompt Library - 深度指令库**，了解每个模块的具体 Prompt 实现。