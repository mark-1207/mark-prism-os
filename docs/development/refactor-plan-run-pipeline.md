# run_prism_os 重构方案

> 状态：方案阶段，不开发
> 创建：2026-06-05
> 前置条件：P1 GAP 修复完成（4 个 commit），P2 待做

---

## 1. 问题现状

### 1.1 函数膨胀

`run_prism_os` 从最初 ~200 行膨胀到 600+ 行，承载 11 个 Phase 的全部逻辑：

```
run_prism_os()
├── Phase 0: classify_intent
├── Phase 1: socratic_gateway + 7 类追问 + HKR 评分
├── Phase 1.5: backup_check
├── Phase 2: prism_engine + 标题选择循环
├── Phase 3: reality_anchor
├── Phase 3.5: digital_twin_filter
├── Phase 4.5: cognitive_outline + CCOS 审核循环
├── Phase 4.6: gap_analysis + 决策点 3 循环  ← GAP-5 新增
├── Phase 5: logic_pressure
├── Phase 6: storage.append_log
└── narrate 接力 ← GAP-2 新增
```

### 1.2 补丁式开发

每次 GAP 修复都是"往函数里塞代码"：

| GAP | 改动方式 | 副作用 |
|-----|---------|--------|
| GAP-1 | argv 循环加 elif | 正常 |
| GAP-3+4 | 决策点加 helper 调用 | 正常 |
| GAP-2 | 函数末尾加 try/except | 函数更长 |
| GAP-5 | 函数中间插入 20 行 gap 逻辑 | 函数更长 |

### 1.8 测试靠 mock

当前测试 100% mock，通过 ≠ 真实能跑：

- mock 掉了所有 LLM 调用
- mock 掉了 stdin 交互
- mock 掉了文件 I/O
- 没有真正的端到端测试

---

## 2. 目标架构

### 2.1 Pipeline 模式

```python
class PrismPipeline:
    """PRISM-OS 流水线：每个 Phase 是独立步骤"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.state = PipelineState()

    def run(self, thesis: str) -> PipelineResult:
        """执行完整流水线"""
        self.state.thesis = thesis

        for phase in self.phases():
            if not phase.should_run(self.state):
                continue
            result = phase.execute(self.state)
            self.state.update(phase.name, result)

            if result.status == "rejected":
                return PipelineResult(status="rejected", phase=phase.name)

        return PipelineResult(status="success", state=self.state)

    def phases(self) -> List[Phase]:
        """返回有序 Phase 列表"""
        return [
            IntentPhase(),
            GatewayPhase(),
            BackupCheckPhase(),
            PrismPhase(),
            RealityPhase(),
            TwinPhase(),
            CCOSPhase(),
            GapPhase(),
            LogicPhase(),
            StoragePhase(),
            NarratePhase(),
        ]
```

### 2.2 Phase 接口

```python
class Phase(ABC):
    """Phase 基类"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def should_run(self, state: PipelineState) -> bool:
        """判断是否需要执行（根据 config 和 state）"""

    @abstractmethod
    def execute(self, state: PipelineState) -> PhaseResult:
        """执行 Phase，返回结果"""
```

### 2.3 PipelineState

```python
@dataclass
class PipelineState:
    thesis: str = ""
    platform: str = "both"
    interactive: bool = True
    # Phase 输出
    intent: Optional[dict] = None
    gateway: Optional[dict] = None
    candidates: List[dict] = field(default_factory=list)
    selected_title: Optional[str] = None
    ccos_outline: Optional[dict] = None
    gap_analysis: Optional[dict] = None
    # 决策记录
    decisions: Dict[str, str] = field(default_factory=dict)
```

### 2.4 PipelineConfig

```python
@dataclass
class PipelineConfig:
    platform: str = "both"
    interactive: bool = True
    skip_gateway: bool = False
    skip_ccos_review: bool = False
    include_narrate: bool = True
    # ... 其他 flag
```

---

## 3. 拆分策略

### 3.1 Phase 拆分

| Phase | 提取来源 | 新文件 | 估计行数 |
|-------|---------|--------|---------|
| IntentPhase | L70-94 classify_intent | phases/intent.py | 30 |
| GatewayPhase | L274-340 socratic_gateway | phases/gateway.py | 70 |
| BackupCheckPhase | L342-350 check_related_backups | phases/backup.py | 15 |
| PrismPhase | L351-470 prism_engine + 选择 | phases/prism.py | 120 |
| RealityPhase | L472-480 reality_anchor | phases/reality.py | 15 |
| TwinPhase | L482-510 digital_twin_filter | phases/twin.py | 30 |
| CCOSPhase | L512-542 cognitive_outline + 审核 | phases/ccos.py | 80 |
| GapPhase | L543-565 gap_analysis + 决策 | phases/gap.py | 60 |
| LogicPhase | L567-580 logic_pressure | phases/logic.py | 20 |
| StoragePhase | L582-600 storage.append_log | phases/storage.py | 25 |
| NarratePhase | _run_narrate | phases/narrate.py | 40 |

### 3.2 run_prism_os 简化

重构后 `run_prism_os` 变成：

```python
def run_prism_os(user_input: str, **kwargs) -> dict:
    """PRISM-OS 完整工作流程"""
    config = PipelineConfig(**kwargs)
    pipeline = PrismPipeline(config)
    result = pipeline.run(user_input)
    return result.to_dict()
```

约 10 行。

### 3.3 CLI 保持不变

`main()` 函数的 argv 解析保持不变，只是调用 `run_prism_os` 的方式从"直接调用"变成"通过 pipeline 调用"。

---

## 4. 迁移路径

### 4.1 渐进式迁移（推荐）

```
阶段 1: 创建 Pipeline 骨架 + Phase 基类
阶段 2: 逐个 Phase 提取（从最简单的开始）
阶段 3: run_prism_os 改为调用 Pipeline
阶段 4: 删除旧代码
```

每个阶段独立 commit，可回滚。

### 4.2 测试策略

- 每个 Phase 有独立单元测试（mock LLM）
- Pipeline 有集成测试（mock Phase）
- 端到端测试用真实 LLM（可选，需要 API key）

### 4.3 向后兼容

- `run_prism_os` 函数签名不变
- CLI 命令不变
- 输出格式不变

---

## 5. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Phase 边界切错 | 逻辑丢失 | 逐个 Phase 提取 + 测试 |
| 状态传递遗漏 | Phase 间数据丢失 | PipelineState 统一管理 |
| 测试覆盖不足 | 回归 | 先写测试再重构 |
| 重构期间新 GAP | 代码冲突 | 重构完成前不修新 GAP |

---

## 6. 工时估算

| 阶段 | 工时 | 说明 |
|------|------|------|
| 阶段 1: 骨架 | 30 min | Phase 基类 + PipelineState + PipelineConfig |
| 阶段 2: 提取 Phase | 2-3h | 11 个 Phase，平均 15 min/个 |
| 阶段 3: 集成 | 30 min | run_prism_os 改调 Pipeline |
| 阶段 4: 清理 | 30 min | 删除旧代码 + 全量测试 |
| **总计** | **3.5-4h** | |

---

## 7. 决策点

1. **何时重构？** P2 完成后？还是现在？
2. **Phase 拆分粒度？** 11 个 Phase 还是合并一些（如 Reality+Twin）？
3. **是否保留旧代码？** 重构后保留旧 run_prism_os 一段时间？

---

## 8. 结论

当前 `run_prism_os` 的问题不是"GAP 太多"，而是"架构太胖"。每次 GAP 修复都是打补丁，补丁越多函数越长，函数越长越难维护，越难维护越容易出新问题。

根治方案：拆成 Pipeline + Phase，每个 Phase 独立、可测试、可替换。

**建议**：P2 完成后启动重构，重构期间不修新 GAP。
