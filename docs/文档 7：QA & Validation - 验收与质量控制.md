# 文档 7：QA & Validation - 验收与质量控制


## 一、质量保证策略

PRISM-OS 的质量保证分为三个层次：

1. **单元测试（Unit Test）**：验证单个模块的逻辑正确性。

2. **集成测试（Integration Test）**：验证模块间的协作是否正常。

3. **端到端测试（E2E Test）**：验证完整流程是否符合预期。

---

## 二、测试用例库

### 2.1 苏格拉底网关测试

#### 测试目标

验证意图熵值计算和拦截逻辑是否正确。

#### 测试用例

| 用例 ID | 输入 | 预期熵值 | 预期决策 | 说明 |
| --- | --- | --- | --- | --- |
| **TC-SG-001** | “我想做自媒体但不知道写什么” | < 1.5 | blocked | 纯情绪表达 |
| **TC-SG-002** | “AI 时代提问比执行更值钱” | 1.5-2.5 | clarify | 有命题但需澄清 |
| **TC-SG-003** | “为什么 GPT-4 让初级程序员失业率上升 30%？” | > 2.5 | pass | 完整命题 |
| **TC-SG-004** | “赋能降维打击破圈” | < 1.5 | blocked | 空洞词汇堆砌 |

#### 实现示例

```python
import pytest
from src.core.socratic_gateway import SocraticGateway
from src.adapters.mock_llm import MockLLMRouter

def test_socratic_gateway_blocks_vague_input():
    """测试：模糊输入应被拦截"""
    gateway = SocraticGateway(llm=MockLLMRouter())
    
    result = gateway.process("我想做自媒体但不知道写什么")
    
    assert result["decision"] == "blocked"
    assert result["entropy_score"] < 1.5

def test_socratic_gateway_passes_clear_thesis():
    """测试：清晰命题应放行"""
    gateway = SocraticGateway(llm=MockLLMRouter())
    
    result = gateway.process("为什么 GPT-4 让初级程序员失业率上升 30%？")
    
    assert result["decision"] == "pass"
    assert result["entropy_score"] > 2.5
```

---

### 2.2 棱镜引擎测试

#### 测试目标

验证四维标题生成的正交性和质量。

#### 测试用例

| 用例 ID | 输入命题 | 验证项 | 说明 |
| --- | --- | --- | --- |
| **TC-PE-001** | “AI 时代提问比执行更值钱” | 生成 4 个标题 | 基本功能 |
| **TC-PE-002** | 同上 | 任意两个标题的相似度 < 0.75 | 正交性校验 |
| **TC-PE-003** | 同上 | 标题长度在 15-25 字之间 | 长度约束 |
| **TC-PE-004** | 同上 | 不包含禁用词汇 | 词汇过滤 |

#### 实现示例

```python
from src.core.prism_engine import PrismEngine
from sklearn.metrics.pairwise import cosine_similarity

def test_prism_engine_generates_four_titles():
    """测试：应生成 4 个标题"""
    engine = PrismEngine(llm=MockLLMRouter(), embedding=MockEmbedding())
    
    result = engine.generate("AI 时代提问比执行更值钱", config={})
    
    assert len(result["candidates"]) == 4

def test_prism_engine_orthogonality():
    """测试：标题应正交（相似度 < 0.75）"""
    engine = PrismEngine(llm=MockLLMRouter(), embedding=MockEmbedding())
    
    result = engine.generate("AI 时代提问比执行更值钱", config={})
    titles = [c["title"] for c in result["candidates"]]
    
    vectors = [engine.embedding.embed(t) for t in titles]
    sim_matrix = cosine_similarity(vectors)
    
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            assert sim_matrix[i][j] < 0.75, f"标题 {i} 和 {j} 过于相似"

def test_prism_engine_respects_banned_words():
    """测试：应过滤禁用词汇"""
    config = {"banned_words": ["赋能", "破圈"]}
    engine = PrismEngine(llm=MockLLMRouter(), embedding=MockEmbedding())
    
    result = engine.generate("如何赋能团队", config=config)
    
    for candidate in result["candidates"]:
        for word in config["banned_words"]:
            assert word not in candidate["title"]
```

---

### 2.3 现实校验锚测试

#### 测试目标

验证新颖度评估的准确性。

#### 测试用例

| 用例 ID | 标题 | 预期竞争度 | 说明 |
| --- | --- | --- | --- |
| **TC-RA-001** | “为什么 AI 让程序员失业？” | 血海 | 高度饱和话题 |
| **TC-RA-002** | “为什么量子纠缠能解释意识？” | 蓝海 | 小众话题 |
| **TC-RA-003** | “为什么 ChatGPT 改变工作方式？” | 红海 | 有竞争但可做 |

#### 实现示例

```python
from src.adapters.serper_adapter import SerperAdapter

def test_reality_anchor_detects_red_ocean():
    """测试：应识别红海话题"""
    anchor = SerperAdapter(api_key="test_key")
    
    result = anchor.validate_novelty("为什么 AI 让程序员失业？", [])
    
    assert result["competition_level"] == "血海"
    assert result["duplicate_rate"] > 0.7

def test_reality_anchor_detects_blue_ocean():
    """测试：应识别蓝海话题"""
    anchor = SerperAdapter(api_key="test_key")
    
    result = anchor.validate_novelty("为什么量子纠缠能解释意识？", [])
    
    assert result["competition_level"] == "蓝海"
    assert result["duplicate_rate"] < 0.3
```

---

### 2.4 素材缺口分析测试

#### 测试目标

验证缺口分析的准确性。

#### 测试用例

| 用例 ID | 命题 | 现有素材 | 预期缺口分数 | 说明 |
| --- | --- | --- | --- | --- |
| **TC-GA-001** | “AI 对程序员的影响” | 包含相关数据 | < 0.3 | 素材充足 |
| **TC-GA-002** | “量子计算的商业应用” | 无相关素材 | > 0.8 | 素材严重不足 |

#### 实现示例

```python
from src.core.gap_analyzer import GapAnalyzer

def test_gap_analyzer_detects_sufficient_materials():
    """测试：应识别素材充足的情况"""
    analyzer = GapAnalyzer(llm=MockLLMRouter(), knowledge=MockKnowledgeGateway())
    
    result = analyzer.analyze("AI 对程序员的影响")
    
    assert result["gap_score"] < 0.3
    assert result["readiness"] > 0.7

def test_gap_analyzer_detects_insufficient_materials():
    """测试：应识别素材不足的情况"""
    analyzer = GapAnalyzer(llm=MockLLMRouter(), knowledge=MockKnowledgeGateway())
    
    result = analyzer.analyze("量子计算的商业应用")
    
    assert result["gap_score"] > 0.8
    assert len(result["missing_evidence"]) > 0
```

---

### 2.5 逻辑压力测试

#### 测试目标

验证逻辑谬误检测的准确性。

#### 测试用例

| 用例 ID | 标题 | 预期谬误类型 | 说明 |
| --- | --- | --- | --- |
| **TC-LA-001** | “为什么所有富豪都早起？” | 幸存者偏差 | 忽略失败案例 |
| **TC-LA-002** | “为什么聪明人都读书多？” | 因果倒置 | 混淆因果 |
| **TC-LA-003** | “AI 会让所有人失业” | 滑坡谬误 | 过度推论 |

#### 实现示例

```python
from src.core.logic_auditor import LogicAuditor

def test_logic_auditor_detects_survivorship_bias():
    """测试：应识别幸存者偏差"""
    auditor = LogicAuditor(llm=MockLLMRouter())
    
    result = auditor.stress_test("为什么所有富豪都早起？")
    
    assert result["has_fallacy"] == True
    assert result["fallacy_type"] == "幸存者偏差"

def test_logic_auditor_passes_valid_logic():
    """测试：应放行逻辑正确的标题"""
    auditor = LogicAuditor(llm=MockLLMRouter())
    
    result = auditor.stress_test("为什么部分程序员在 AI 时代更焦虑？")
    
    assert result["has_fallacy"] == False
```

---

## 三、集成测试

### 测试目标

验证模块间的协作是否正常。

### 测试场景

#### 场景 1：完整的 V1 流程

```python
def test_v1_full_workflow():
    """测试：V1 完整流程"""
    orchestrator = PRISMOrchestrator(
        knowledge=MockKnowledgeGateway(),
        reality=MockRealityAnchor(),
        llm=MockLLMRouter(),
        storage=MockStorage()
    )
    
    result = orchestrator.run_v1("AI 时代提问比执行更值钱")
    
    # 验证流程完整性
    assert "entropy_score" in result
    assert "candidates" in result
    assert len(result["candidates"]) == 4
    
    # 验证每个候选标题都有新颖度评分
    for candidate in result["candidates"]:
        assert "novelty_score" in candidate
    
    # 验证日志已写入
    logs = orchestrator.storage.load_logs()
    assert len(logs) > 0
```

#### 场景 2：V1.5 流程（含素材分析）

```python
def test_v1_5_full_workflow():
    """测试：V1.5 完整流程"""
    orchestrator = PRISMOrchestrator(...)
    
    result = orchestrator.run_v1_5("AI 对程序员的影响")
    
    # 验证缺口分析
    assert "gap_report" in result
    assert "readiness" in result["gap_report"]
    
    # 验证双端大纲
    assert "wechat_outline" in result
    assert "xiaohongshu_outline" in result
```

---

## 四、端到端测试

### 测试目标

验证完整的用户旅程。

### 测试场景

#### E2E-001：从模糊输入到最终选题

```python
def test_e2e_from_vague_to_final_topic():
    """测试：从模糊输入到最终选题的完整流程"""
    orchestrator = PRISMOrchestrator(...)
    
    # 第一次输入（模糊）
    result1 = orchestrator.run("我想写点关于 AI 的东西")
    assert result1["status"] == "blocked"
    
    # 第二次输入（澄清后）
    result2 = orchestrator.run("AI 时代提问比执行更值钱")
    assert result2["status"] == "clarify"
    
    # 第三次输入（完整命题）
    result3 = orchestrator.run("为什么 GPT-4 让初级程序员失业率上升 30%？")
    assert result3["status"] == "success"
    assert len(result3["candidates"]) == 4
```

---

## 五、性能测试

### 测试目标

验证系统在高负载下的表现。

### 测试指标

| 指标 | 目标值 | 测量方法 |
| --- | --- | --- |
| **单次选题生成时间** | < 30 秒 | 计时器 |
| **并发处理能力** | 10 个/分钟 | 压力测试 |
| **LLM API 调用次数** | < 5 次/选题 | 日志统计 |
| **成本** | < $0.5/选题 | 成本追踪 |

### 实现示例

```python
import time

def test_performance_single_topic_generation():
    """测试：单次选题生成时间"""
    orchestrator = PRISMOrchestrator(...)
    
    start_time = time.time()
    result = orchestrator.run_v1("AI 时代提问比执行更值钱")
    end_time = time.time()
    
    elapsed = end_time - start_time
    assert elapsed < 30, f"生成时间过长：{elapsed} 秒"

def test_performance_concurrent_requests():
    """测试：并发处理能力"""
    orchestrator = PRISMOrchestrator(...)
    
    import concurrent.futures
    
    inputs = ["命题1", "命题2", "命题3", "命题4", "命题5"]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(orchestrator.run_v1, inp) for inp in inputs]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert len(results) == 5
```

---

## 六、验收检查清单

### V1 验收标准

- [ ]  苏格拉底网关能正确拦截模糊输入（熵值 < 1.5）

- [ ]  棱镜引擎能生成 4 个正交标题（相似度 < 0.75）

- [ ]  现实校验锚能返回新颖度评分

- [ ]  所有数据写入 `topic_log.jsonl`

- [ ]  单次生成时间 < 30 秒

- [ ]  单元测试覆盖率 > 80%

### V1.5 验收标准

- [ ]  知识网关能从本地文件夹检索素材

- [ ]  素材缺口分析能输出 Gap Report

- [ ]  双端大纲生成能输出两套大纲

- [ ]  集成测试通过率 100%

### V2 & V3 验收标准

- [ ]  逻辑审计器能检测出至少 4 种谬误类型

- [ ]  刺客机制能自动扫描历史选题并生成反转

- [ ]  Prompt 自进化能根据用户行为修改系统指令

- [ ]  端到端测试通过率 100%

### V4 验收标准

- [ ]  RSS 监控能监控至少 5 个外部信息源

- [ ]  认知裂缝捕捉能主动推送选题预警

- [ ]  推送准确率 > 70%（人工评估）

---

## 七、质量度量指标

| 指标 | 计算方法 | 目标值 |
| --- | --- | --- |
| **代码覆盖率** | 测试覆盖的代码行数 / 总代码行数 | > 80% |
| **Bug 密度** | Bug 数量 / 1000 行代码 | < 5 |
| **平均修复时间** | Bug 修复时间的平均值 | < 24 小时 |
| **用户满意度** | 用户评分（1-5 分） | > 4.0 |

---

## 八、持续集成（CI）配置

### GitHub Actions 示例

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install poetry
        poetry install
    
    - name: Run tests
      run: |
        poetry run pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./coverage.xml
    
    - name: Lint
      run: |
        poetry run ruff check src/
        poetry run mypy src/
```

---

## 九、发布检查清单

### 发布前必检项

- [ ]  所有单元测试通过

- [ ]  所有集成测试通过

- [ ]  所有端到端测试通过

- [ ]  代码覆盖率 > 80%

- [ ]  无高优先级 Bug

- [ ]  文档已更新（README, CHANGELOG）

- [ ]  性能测试通过

- [ ]  安全扫描通过（无已知漏洞）

---

## 十、总结

PRISM-OS 的质量保证体系覆盖了从单元测试到端到端测试的全流程。通过严格的验收标准和持续集成，确保系统在每个版本迭代中都保持高质量。

**关键成功因素：**

1. **自动化测试**：减少人工测试成本。

2. **Mock 对象**：隔离外部依赖，提高测试速度。

3. **持续集成**：每次提交自动运行测试。

4. **质量度量**：用数据驱动质量改进。

---

## 附录：Mock 对象库

```python
# src/tests/mocks.py

class MockLLMRouter:
    """Mock LLM 路由器"""
    def call(self, model, prompt, **kwargs):
        # 返回预设的 JSON 响应
        return '{"entropy_score": 2.5, "decision": "pass"}'

class MockKnowledgeGateway:
    """Mock 知识网关"""
    def fetch_context(self, query, limit=10, filters=None):
        return [{"source": "mock.md", "content": "Mock content"}]

class MockRealityAnchor:
    """Mock 现实校验锚"""
    def validate_novelty(self, title, keywords, search_depth=10):
        return {"novelty_score": 0.85, "competition_level": "蓝海"}

class MockStorage:
    """Mock 存储"""
    def __init__(self):
        self.logs = []
    
    def save_log(self, entry):
        self.logs.append(entry)
    
    def load_logs(self):
        return self.logs
```

---

**开发全家桶生成完毕。7 个核心文档已就绪，可直接交付给 Claude Code 或 Cursor 进行开发。**