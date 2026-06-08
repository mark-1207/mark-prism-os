# PRISM-OS Phase 4.5 CCOS v2.0 开发计划

> 版本：1.0 | 日期：2026-05-18 | 状态：待开发

---

## 一、需求概述

将 CCOS v2.0（动态大纲skill.md）作为 Phase 4.5 接入 PRISM-OS，实现"认知推进流"式动态大纲生成，替代旧版目录式大纲。

---

## 二、文件变更清单

### 新增文件

| 文件路径 | 用途 | 优先级 |
|---|---|---|
| `skills/prism-os/scripts/cognitive_outline.py` | Phase 4.5 CCOS v2.0 主模块 | P0 |
| `skills/prism-os/data/ccos_settings.yaml` | CCOS 配置（阈值、难度系数等） | P1 |

### 修改文件

| 文件路径 | 调整内容 | 优先级 |
|---|---|---|
| `skills/prism-os/scripts/gap_analysis.py` | 拆分：移除 `generate_outlines()`，保留 `analyze_gap()` + `calculate_readiness()` 为 Phase 4.6 | P0 |
| `skills/prism-os/scripts/prism_os.py` | Phase 4 入口改为 CCOS；新增 Layer 0 用户交互节点；调整 Phase 4.5/4.6 顺序；14项输出写入 storage | P0 |
| `skills/prism-os/scripts/storage.py` | 新增 `append_ccos_log()`：14项输出结构写入 topic_log.yaml | P1 |
| `skills/prism-os/scripts/cognitive_crack.py` | 整合 Layer 7 作者性注入（复用数字分身） | P1 |
| `skills/prism-os/SKILL.md` | 更新 Phase 4.5 描述，移除旧版 generate_outlines | P0 |

### 待删除文件（Phase 4.5 上线稳定后 2 周执行）

| 文件路径 | 说明 |
|---|---|
| `gap_analysis.py` 中 `generate_outlines()` 函数体 | 保留函数名和 CLI 入口（调试用 `--legacy` flag） |

---

## 三、cognitive_outline.py 详细开发任务

### 3.1 辅助层

#### T-1：LLM 调用基础函数
- `_call_llm_raw(prompt)` — 调用 call_llm，返回原始文本
- `_parse_llm_json(text)` — 从 LLM 输出解析 JSON（含 code block 提取）
- `_safe_print(obj)` — Windows GBK 安全输出

#### T-2：平台差异化配置
- `_get_platform_hints(platform)` — 返回公众号/小红书/两者的 prompt 差异化配置
- `_get_dimension_hints(dimension)` — 返回 reversal/micro_scene/systemic_flaw/bridge 的结构推荐

#### T-3：作者性数据加载
- `_load_authorial_identity()` — 从数字分身加载 thinking_pattern/dimension_weights/style_keywords，注入 Layer 7

---

### 3.2 Layer 0：认知对齐（人机协同）

#### T-4：七类追问生成
- `generate_alignment_questions(topic, platform)` — 根据选题类型和平台生成七类追问列表
  - 公众号侧重：立场追问 + 反直觉追问 + 边界追问
  - 小红书侧重：案例追问 + 情绪追问 + 用户画像追问
  - 输出：7 个追问对象 `{"类型": "", "内容": "", "可选方向": [...]}` 的列表

#### T-5：用户回答解析
- `parse_user_alignment_response(questions, user_input)` — 解析用户对七类追问的回答
  - 支持：直接回答 / 选择方向让 AI 展开 / 跳过
  - 输出：收敛后的 `{"方向": "", "立场": "", "情绪": "", "案例": "", "读者画像": "", "边界": ""}`

#### T-6：认知对齐主函数
- `cognitive_alignment_layer0(topic, platform, user_input)` — Layer 0 完整流程
  - 调用 T-4 生成追问 → CLI 打印选项 → 解析用户输入 → 调用 T-5 收敛 → 输出收敛结果

**CLI 交互协议**：
```
系统输出七类追问（带选项编号）
用户输入：直接回答 / 选项编号(1-7) / skip(跳过全部)
系统根据回答更新：认知冲突描述 + 内容立场 + 选定方向
```

---

### 3.3 Layer 1：内容意图识别

#### T-7：内容目标识别
- `recognize_content_goal(topic, alignment_result)` — 识别 8 类内容目标
  - 输出：`{"内容目标": "认知升级", "置信度": 0.85}`

#### T-8：用户动机识别
- `recognize_user_motivation(topic, alignment_result)` — 基于 Layer 0 交互结果推断用户阅读动机
  - 输出：`{"用户动机": "焦虑", "二级动机": ["好奇", "想解决问题"]}`

---

### 3.4 Layer 2：选题解析

#### T-9：选题类型识别
- `classify_topic_type(topic)` — 识别 5 类选题类型（趋势型/方法型/观点型/情绪型/行业型）
  - 输出：`{"类型": "观点型", "置信度": 0.8}`

#### T-10：核心问题提取
- `extract_core_problem(topic)` — 提取"核心问题链"
  - 示例：AI让内容生产更容易 → 内容同质化 → 普通人如何建立优势？
  - 输出：`{"核心问题": "...", "问题链": ["...", "...", "..."]}`

#### T-11：认知张力提取
- `extract_cognitive_tension(topic)` — 提取"大众以为 vs 现实是"认知冲突
  - 输出：`{"认知张力": {"大众以为": "...", "现实是": "..."}}`

#### T-12：潜在方向推演
- `infer_potential_directions(topic)` — 推演 2-4 个潜在方向供用户选择
  - 输出：`[{"方向": "机会方向", "描述": "..."}, {"方向": "焦虑方向", "描述": "..."}, ...]`

---

### 3.5 Layer 3：结构决策

#### T-13：主结构选择
- `select_main_structure(topic_type, alignment_result)` — 根据选题类型和用户立场推荐主结构
  - 认知升级型（观点型/趋势型）/ 问题拆解型（方法型）/ 故事驱动型（情绪型）/ 信息重构型（行业型）
  - 输出：`{"主结构": "认知升级型", "推进方式": ["冲突推进", "递进推进"]}`

#### T-14：推进方式决策
- `decide_progression_method(structure, topic)` — 决定 6 种推进方式中的一种或组合
  - 冲突推进 / 递进推进 / 案例推进 / 对比推进 / 拆解推进 / 情绪推进

---

### 3.6 Layer 4：认知模块编排

#### T-15：模块列表定义
- 定义 HOOK / CASE / EXPLAIN / MODEL / COUNTER / EVIDENCE / ACTION / BOUNDARY 共 8 个模块的元数据

#### T-16：认知模块流生成
- `generate_cognitive_module_flow(topic, structure, authorial_identity, platform)` — 生成认知模块流
  - 输入：选题 + 主结构 + 作者性设定 + 平台
  - 规则：HOOK 必有，ACTION 实操类必有，MODEL 至少 1 个，COUNTER/BOUNDARY 建议有
  - 输出：模块流列表 `[{"模块": "HOOK", "内容摘要": "...", "功能": "制造停留"}, ...]`

---

### 3.7 Layer 5+6：信息密度 + Anti-AI（内嵌）

不独立函数，内嵌在 T-18 的 prompt 中。

**信息密度规则（强制）**：
- 每段必须有信息增量
- 禁止同义反复 / 空洞总结 / 正确废话 / 情绪堆砌
- 强制：真实细节 / 微观行为 / 时间感 / 决策过程 / 心理变化

**Anti-AI 规则（强制）**：
- 禁止：模板感 / 套话 / 平均化表达 / AI式升华 / 空洞口号
- 强制：观点化表达 / 人类思考感（犹豫/推演/局部经验/不确定性）

---

### 3.8 Layer 7：作者性注入

#### T-17：作者性要素整合
- `inject_authorial_identity(thinking_pattern, dimension_weights, style_keywords)` — 整合数字分身数据为 CCOS prompt 注入格式
  - 输出：`{"认知倾向": "", "表达气质": "", "价值倾向": "", "长期母题": ""}`

---

### 3.9 Layer 8：内容势能设计

#### T-18：势能曲线生成
- `generate_narrative_energy(topic, module_flow, platform)` — 生成势能曲线
  - 张力控制：何时抛冲突/给答案/反转
  - 认知落差：先 A 后 B 的设计
  - 节奏变化：抽象→案例→模型→情绪→观点 循环
  - 情绪曲线：预设每段情绪走向
  - 认知奖励点：每隔一段的新观点/新模型/新视角
  - 输出：`{"张力变化": [...], "情绪曲线": [...], "认知落差设计": "..."}`

---

### 3.10 CCOS 主函数

#### T-19：14项动态认知大纲生成
- `cognitive_outline_workflow(topic, dimension, platform, alignment_result)` — Phase 4.5 完整流程
  - 顺序调用 T-7/T-8/T-9/T-10/T-11/T-12/T-13/T-14/T-16/T-17/T-18
  - 输出 14 项 JSON（见下方格式）

#### T-20：双平台分别生成
- `generate_dual_platform_outline(topic, dimension)` — 同时生成公众号+小红书两套 14 项大纲
  - 输出：`{"wechat_cognitive_outline": {...14项...}, "xiaohongshu_cognitive_outline": {...14项...}}`

---

### 3.11 14项输出格式

```json
{
  "内容目标": "string",
  "用户动机": "string",
  "核心认知冲突": "string",
  "内容立场": "string",
  "作者性设定": {
    "认知倾向": "string",
    "表达气质": "string",
    "价值倾向": "string",
    "长期母题": "string"
  },
  "主结构": "string",
  "推进方式": "string",
  "认知模块流": [
    {"模块": "HOOK", "内容": "string", "功能": "string"}
  ],
  "势能曲线": {
    "张力变化": ["string"],
    "情绪曲线": ["string"],
    "认知落差设计": "string"
  },
  "案例插入点": ["string"],
  "信息密度要求": "string",
  "语言风格": "string",
  "Anti-AI要求": "string",
  "最终动态认知大纲": "string"
}
```

---

### 3.12 CLI 入口

```
python cognitive_outline.py outline "<标题>" "<dimension>" "<平台>"
python cognitive_outline.py dual "<标题>" "<dimension>"
python cognitive_outline.py alignment "<标题>" "<平台>"   # 仅测试 Layer 0
python cognitive_outline.py legacy "<标题>"                # 调试用，输出旧版格式
```

---

## 四、gap_analysis.py 拆分任务（Phase 4.6）

### T-21：移除 generate_outlines()
- 删除 `generate_outlines()` 函数体
- 保留函数名和 CLI 入口，增加 `--legacy` flag 输出说明
- `gap_analysis()` 函数改为导出 `analyze_gap()` 和 `calculate_readiness()`，不再调用 `generate_outlines()`

### T-22：Evidence chain 格式调整
- 调整 `analyze_gap()` prompt，使其输出的 `evidence_chain` 包含论点级（不是素材级）
- 新增字段：`thesis_summary` — LLM 总结的选题核心论点，供 Phase 4.6 调用

---

## 五、prism_os.py 调整任务

### T-23：Phase 4 入口重构
- 新增 `run_phase_4_5()` 函数，接入 CCOS
- 用户交互节点：在 Phase 3.5 之后，询问用户选择标题（从候选列表中选择）
- 询问用户选择 dimension（4 选 1）
- 询问用户选择平台（公众号/小红书/两者）

### T-24：Phase 4.6 Gap Analysis 接入
- 在 CCOS 完成后，调用 `analyze_gap()` 做素材就绪度分析
- 根据阈值（< 0.3 中断，0.3-0.6 警告，>= 0.6 通过）输出结果

### T-25：输出格式化更新
- 更新 `format_prism_os_output()`，支持 14 项 CCOS 输出格式
- 保留旧版格式兼容（Phase 4.5 未启用时）

### T-26：Storage 整合
- 新增 `append_ccos_log()` 调用，将 14 项输出写入 topic_log.yaml

---

## 六、storage.py 调整任务

### T-27：新字段写入
- `append_ccos_log(ccos_result)` — 将 14 项输出以新字段结构写入 topic_log.yaml
- 格式：
```yaml
ccos_outline:
  content_goal: ...
  user_motivation: ...
  cognitive_conflict: ...
  content_stance: ...
  authorial_identity: {...}
  main_structure: ...
  progression_method: ...
  cognitive_module_flow: [...]
  narrative_energy: {...}
  case_insert_points: [...]
  info_density: ...
  language_style: ...
  anti_ai_requirements: ...
  final_outline: ...
```

---

## 七、cognitive_crack.py 调整任务

### T-28：Layer 7 作者性数据对接
- `get_authorial_identity_for_ccos()` — 从 `learn_thinking_pattern()` 和 `digital_twin_filter()` 获取数据
- 返回格式符合 Layer 7 注入要求

---

## 八、SKILL.md 更新任务

### T-29：文档更新
- Phase 4.5：CCOS v2.0 动态大纲（新增 Layer 0-8 说明）
- Phase 4.6：Gap Analysis（保留，阈值判定逻辑更新）
- 移除旧版 `generate_outlines()` 描述
- 更新命令示例：`python prism_os.py run "<输入>" --format`

---

## 九、测试任务

### T-30：单元测试
- `test_cognitive_outline.py`：覆盖各 Layer 纯函数逻辑（分类/解析/决策）
- Layer 0 追问生成测试（mock LLM）
- 14 项 JSON 格式验证测试
- 双平台输出结构测试

### T-31：端到端测试
- 完整流程：用户输入 → Phase 0-3 → 用户选择 → CCOS → Gap Analysis → 输出
- Layer 0 交互跳过测试
- Gap Analysis 低就绪度中断测试

---

## 十、开发依赖关系

```
T-0: ccos_settings.yaml（配置，前置依赖）
    ↓
T-1, T-2, T-3 (基础)
    ↓
T-7, T-8, T-9, T-10, T-11, T-12 (Layer 1-2)
    ↓
T-13, T-14 (Layer 3)
    ↓
T-17 (Layer 7 准备) + T-16 (Layer 4) + T-18 (Layer 8)
    ↓
T-4, T-5, T-6 (Layer 0，用户交互)
    ↓
T-19, T-20 (主函数)
    ↓
T-22 (gap_analysis 调整)
    ↓
T-23, T-24, T-25, T-26 (prism_os.py 接入)
    ↓
T-27 (storage 写入)
    ↓
T-28 (cognitive_crack 整合)
    ↓
T-29 (SKILL.md 更新)
    ↓
T-30, T-31 (测试)
```

---

## 十一、验收标准

| 检查项 | 标准 |
|---|---|
| Layer 0 七类追问输出 | 7 项完整，可选跳过 |
| 14 项 JSON 格式 | 结构正确，所有字段非空 |
| 双平台输出 | 两套 14 项独立存在 |
| Gap Analysis 阈值 | < 0.3 中断，0.3-0.6 警告，>= 0.6 通过 |
| storage 写入 | topic_log.yaml 包含 ccos_outline 字段 |
| Layer 7 作者性 | thinking_pattern 正确注入 |
| 旧版 generate_outlines | 不输出，不作为 fallback |
| 单元测试 | 全部通过 |