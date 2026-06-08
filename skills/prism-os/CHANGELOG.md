# PRISM-OS 更新日志

## 版本历史

---

### v1.3.1 (2026-06-03)

**状态**：Phase 6.1 完成

#### Phase 6.1 — Calibration 接入 narrate（v1.3.1）

**核心**：把 Phase 6.0 生成的 `feedback_calibration.yaml` 真正接入 `narrate` 步骤，让生成时自动用历史表现的策略。

**新增**：
- `compute_calibration_boost(calibration, platform, strategy)` — 根据历史表现为策略加分
  - 样本 <3 → boost=0（冷启动不调整）
  - 1 个策略有数据时用全局 baseline 5%
  - 多策略时用平台平均作 baseline
  - 样本 ≥10 → boost ×1.5
  - boost 封顶 ±5.0
- `evaluate_narrative_strategy()` 新增参数：`calibration`、`platform`
  - 原有评分 + calibration boost
  - 返回新增字段：`calibration_applied`、`calibration_boosts`
- `narrative_generation_workflow()` / `interactive_narrative_workflow()` 新增参数：`calibration`
- `prism_os.py narrate` 自动加载本地 calibration，无需新参数

**核心公式**：
```
boost = (avg_engagement - baseline) × 10 × sample_boost
sample_boost = 1.5 if sample_size ≥ 10 else 1.0
```

**测试**：
- 11 个新测试（test_narrate_calibration.py）
- 覆盖：boost 计算边界 / 样本量阈值 / 封顶 / 策略选择影响 / 回归
- 全部通过

---

### v1.3.0 (2026-06-03)

**状态**：Phase 6.0 MVP 已完成

#### Phase 6.0 — 模板优选（数据反馈闭环 MVP）

**核心**：把"生成→发布"补成完整飞轮。从 PRISM-OS 内部数据 + 飞书多维表格真实表现，反哺到生成策略选择。

**新增**：
- **飞书多维表格集成**：
  - `config/feishu_config.yaml`（base_token / table_id / field_ids / view_ids）
  - `scripts/feishu_bitable.py` — 飞书 Open API 封装（鉴权/CRUD/upsert/batch）
- **数据同步**：
  - `scripts/metrics_sync.py` — 增量拉取飞书表，写入本地 snapshot（幂等/行校验/缺失容忍）
  - `data/metrics_snapshot.yaml` — 本地副本
  - `data/metrics_sync_state.json` — 增量同步状态
- **模板优选（反哺机制 B）**：
  - `scripts/template_scorer.py` — 按「平台 × 叙事策略」/「平台 × CCOS 模块组合」统计真实表现
  - `data/feedback_calibration.yaml` — 反哺配置
- **CLI 集成**：
  - `prism_os.py metrics sync` — 从飞书同步到本地
  - `prism_os.py metrics status` — 查看反哺状态
  - `prism_os.py metrics list` — 列出 snapshot
  - `prism_os.py metrics score` — 运行模板优选

**飞书表**（在用户已有 base 中创建）：
- Base: `QVz9byNH0auzRis9KeDcUoe3nZf`
- 表: `tbliXecencoSdnaB`（「内容表现」）
- 21 个字段（16 基础 + 5 公式）+ 3 个视图
- URL: https://my.feishu.cn/base/QVz9byNH0auzRis9KeDcUoe3nZf?table=tbliXecencoSdnaB&view=vewhWxYEie

**字段设计**（21 列）：
- 10 个 PRISM-OS 自动生成（文章ID/标题/平台/发布时间/原始命题/叙事策略/字数/预测HKR/预测质量分/CCOS模块/时间点）
- 5 个用户填（阅读/转发/收藏/点赞/评论）
- 5 个公式自动算（互动率/点赞率/收藏率/转发率/评论率）
- 1 个时间点维度（t_plus_1d / t_plus_7d / t_plus_30d）

**关键约定**：
- 3 个时间点：T+1d / T+7d / T+30d（每篇 3 行）
- 缺失容忍：用户漏填某时间点不影响其他行
- 冷启动：<3 篇不推荐任何策略
- 幂等同步：基于「文章ID + 时间点」唯一键

#### Phase 6.1 — HKR 校准（v1.3.1，30+ 篇后）

- `scripts/calibration_engine.py` — 用真实互动率反推 H/K/R 哪个维度真预测有用
- 触发条件：样本 ≥30 篇 + 距上次校准 >7 天

#### 测试

- 36 个单元测试 + 4 个 E2E 测试，全部通过
- 覆盖：飞书 API mock、增量同步幂等、模板优选冷启动、平台分组、E2E 全链路

---

### v1.2.0 (2026-06-02)

**状态**：已被 v1.3.1 取代

#### 新增

- **`run` 命令决策点 + 交互式开关**（Commit 1）：
  - `run_prism_os` 新增 `interactive: bool = True` 参数
  - Phase 3.5 → Phase 4.5 之间插入用户决策点：展示候选标题列表，等用户输入数字选择
  - `interactive=True` 时阻塞等用户选（默认选 1 = 第一个候选）
  - `interactive=False` 时不阻塞（如 HTTP server）
  - `include_phase_4_8=False` 时不阻塞
  - stdin 不可用时降级到第一个候选
  - 选中的候选用于 CCOS 大纲生成（不是默认第一个）

- **调用方适配**（Commit 2）：
  - `run` 命令加 `--no-interactive` 标志（默认 interactive=True）
  - `--from-queue` 自动非交互（用户已选过）
  - HTTP server 调用 `run_prism_os` 时强制 `interactive=False`（无 stdin）
  - 短触发默认 `interactive=True`（用户场景）

- **单命令健康检查**（Commit 3）：
  - `prism` / `gap` / `ccos` / `narrate` 单独调用时 stderr 打印建议
  - "建议通过 `python prism_os.py run "<命题>"` 走完整流程（Phase 0-7）"
  - `--suppress-warning` 标志可关闭提示
  - 不污染 stdout JSON 输出

- **`run` 命令 `--skip-gateway` 标志**（Commit 5）：
  - 跳过 Phase 1 苏格拉底网关（调试用）
  - help 文本加 `--skip-gateway <text>` 说明

- **`run` 命令 `--clarification` 标志**（Commit 6）：
  - 接收网关追问的澄清答案（避免 need_clarification 阻塞）
  - socratic_gateway 加 `user_clarification: Optional[str]` 参数
  - 合并到 user_input 后重新评估 entropy + HKR

- **CCOS 大纲人工审核决策点**（Commit 8）：
  - Phase 4.5 → Phase 4.6 之间插入用户审核点（CCOS 大纲生成后）
  - 新增 `ccos_review: bool = True` 参数到 `run_prism_os`
  - 新增 `_format_ccos_review()` 展示：模块名 + 功能 + 篇幅（让用户理解"为何是这个模块用这个"）
  - 用户选择：[c] 继续 / [r] 重新生成 / [q] 退出（[e] 手动编辑暂不实现）
  - 新增 CLI 标志 `--no-ccos-review` 跳过审核
  - `test_ccos_review.py`：7 个测试覆盖参数存在 / 阻塞行为 / 展示格式 / CLI 解析

#### 修复

- **熵值/HKR 规则过严 bug**（Commit 7）：
  - bug：合理命题（含 clarifications）打分过低，entropy=0.6、HKR=0.1、combined=0.3，无法 pass gateway
  - 修复：扩展 object/conflict/fact/h/k/r 各类关键词集合
  - object_clarity：增加年龄+职业、危机类、求职类关键词
  - conflict_tension：增加裁员/转型/错配等职场危机词
  - fact_support：增加行动/方法/原因/步骤类关键词
  - hkr_h：增加如何/怎么/怎样疑问词
  - hkr_k：增加思路/提升/适应/核心/问题/转型等方法论词
  - hkr_r：增加 35岁/大龄/中年/裁员/被裁等共同经历词

#### 更新

- SKILL.md 新增 `run` 命令规范入口章节（Commit 4）
- CLAUDE.md（项目根目录）置顶 4 个屡次犯的错误（错误 1: 直接调单步命令 / 错误 2: 审计前没核实代码 / 错误 3: 替用户定义"想写什么" / 错误 4: echo "skip" 自动应答）
- MEMORY 增加 feedback：feedback_dont_skip_flow_again / feedback_audit_verify_with_code / feedback_run_is_canonical_entry / feedback_quality_gate

#### 测试

- 测试总数：426 个
- 新增测试文件：
  - `test_run_prism_os_interactive.py`（6 测试）— 决策点
  - `test_run_callers.py`（3 测试）— 调用方
  - `test_command_healthcheck.py`（3 测试）— 健康检查
  - `test_run_clarification.py`（5 测试）— --clarification
  - `test_entropy_hkr_strict.py`（7 测试）— 规则扩展
  - `test_ccos_review.py`（7 测试）— CCOS 大纲审核
- 全部通过

---

### v1.1.0 (2026-05-27)

**状态**：当前版本

#### 新增

- **NVIDIA NIM 四级 fallback**：接入 NVIDIA NIM 作为 LLM 链第二级（Kimi → NVIDIA NIM → Gateway → OpenRouter）
  - Endpoint: `https://integrate.api.nvidia.com/v1/chat/completions`（OpenAI兼容）
  - 推荐模型：meta/llama-3.1-70b-instruct（quality）、meta/llama-3.1-8b-instruct（fast）、mistralai/mistral-large-2-instruct（long-context）
  - 免费额度，可用 curl 直接调用

- **叙事生成增强**：
  - 五种叙事策略自动评估：人物线索型、数据驱动型、悬念解密型、观点碰撞型、时间线型
  - 预叙事阶段（Pre-narrative）输出策略选择理由和核心叙事元素
  - 字数扩充：草稿 < 2500 字时自动触发 LLM 扩充

#### 修复

- **bare except 全修复**：6 个文件（gap_analysis.py、cognitive_crack.py、logic_pressure.py、prism_engine.py、assassin.py、socratic_gateway.py）的 JSON 解析 fallback 从 `except:` 改为 `except (json.JSONDecodeError, ValueError)`，带 warning 日志

#### 测试

- 测试总数：253 个（27 个 gap_analysis + 新增 medium_fixes 等）
- 全部通过

---

### v1.0.10 (2026-05-26)

**状态**：当前版本

#### 修复

- **Windows SSL 全面绕过**：
  - `call_llm.py` 所有 API 调用改为 curl subprocess（`_curl_post` / `_curl_get`），绕过 Windows Python SSL 证书问题
  - `reality_anchor.py` 重写：Tavily / Firecrawl 搜索改为 curl subprocess（`-k` 参数）
  - `embedding.py` 添加 `verify=False` 和 `urllib3` 警告抑制
  - 所有外部 API 调用不再依赖 Python SSL 堆栈

- **跨机器密钥迁移**：
  - 新增 `scripts/.env` 文件，集中存放 KIMI_API_KEY / OPENROUTER_API_KEY / ZHIPU_API_KEY
  - `call_llm.py` / `embedding.py` / `reality_anchor.py` 启动时自动加载 `.env`
  - 迁移到新机器只需复制 `.env` 文件

#### 新增

- **HTTP 监听模式**：`python prism_os.py listen` 启动长期监听服务，支持跨机器 POST `/run` 触发
- **全局 API 节流**：`_global_throttle()` 在所有 curl 调用底层强制 0.8s 间隔，避免密集调用触发 rate limit
- **OpenRouter 付费模型验证列表**：6 个已验证可用模型替代免费限流列表
  - `qwen/qwen-2.5-72b-instruct` — 最强
  - `deepseek/deepseek-chat-v3` — 强
  - `google/gemma-4-26b-a4b-it` — 可用
  - `mistralai/mistral-small-24b-instruct-2501` — 可用
  - `meta-llama/llama-3.1-8b-instruct` — 可用
  - `qwen/qwen3-8b` — 快

#### 优化

- 意图识别：移除过于激进的 `purely_factual` 检查（10字以下+无强意图），fallback 默认触发
- LLM 重试次数：从 2 次降为 1 次，避免失败时放大 rate limit
- `classify_intent()` 置信度提升（0.3 → 0.6+），更准确识别讨论类话题
- OpenRouter 模型获取：不再使用 API 缓存的免费模型列表，直接用验证过的付费模型

#### 不可用模型（区域限制）

| 模型系列 | 状态 |
|---------|------|
| OpenAI（gpt-4o/gpt-4o-mini） | 403 区域限制 |
| Google Gemini | 403 区域限制 |
| Anthropic Claude（Sonnet/Opus） | 403 区域限制 |

---

### v1.0.9 (2026-05-21)

**状态**：开发中

#### 新增（RSS-Hunter × PRISM-OS 深度整合 → 选题情报员）

- **crack_queue v2.0 数据结构**：
  - 新增 `signals`（trend/emotion/contradiction/homogenization_alert）
  - 新增 `expression_angles`（创作者类型 + 表达入口 + 匹配度）
  - 新增 `creator_match`（growth_stage/sensitive_directions/match_score）
  - `priority_score` 增加 homogenization_penalty 因子

- **crack_hunter_wrapper prompt 升级**：
  - 从"判断裂缝"升级为"提炼 5 类认知信号"
  - signals：趋势/情绪/矛盾/同质化预警
  - expression_angles：为不同类型创作者生成表达入口

- **RSS-Hunter 输出改造**：
  - 不再写入 Obsidian，改为写入 crack_queue
  - 终端推送降级为每日简洁汇总
  - 新增 `prism_os.py queue` 子命令（--list/--tag/--dismiss）

- **PRISM-OS 接入层**：
  - `--from-queue`：队列浏览 + 多选合并进入主流程
  - `--match-queue`：输入时匹配队列，展示 signals/expression_angles
  - 正常输入被动提示：队列有相关裂缝时提示

#### 实施计划

| Phase | 内容 | 状态 |
|-------|------|------|
| A | crack_queue v2.0 + RSS-Hunter 输出改造 | ✅ 已完成 |
| B | `--from-queue` 入口 | ✅ 已完成 |
| C | `--match-queue` + 被动提示 | ✅ 已完成 |
| D | 数字分身扩展 + 归档功能 | 待开发 |
| D | 数字分身扩展 + 归档功能 | 待开发 |

方案文档：`docs/development/RSS-Hunter-PRISM-OS-Integration-Plan.md`

---

### v1.0.8 (2026-05-20)

**状态**：当前版本

#### 新增（Phase 5.5）

- **文章抓取方案**：集成 autocli（`D:\myproject\内容系统v1\contentforge\autocli.exe`）
  - `scrape_article()` 支持微信公众号（`weixin download`）和通用网页（`read`）
  - `extract_key_content()` 用 LLM 提取关键段落和摘要
  - `scrape_and_import_material()` 完整抓取→入库流程
- **Obsidian 入库自动召回**：
  - `scan_vault` glob 改为 `**/*.md` 递归扫描子目录
  - 素材写入 `洞察库/`、`原子库/`（直接目录，非 rss-cracks 子目录）
  - 入库后下次 `recall_materials_by_module` 自动发现新文件
- **逐模块交互确认界面**：
  - `interactive_content_generation_workflow()` 逐模块生成流程
  - 支持 [回车]确认 / [r]重写(最多2次) / [e]编辑 / [q]退出
  - CLI 入口：`python prism_os.py generate "<标题>" --platform wechat --interactive`
- **修改记录用于风格学习**：
  - `record_modification` 持久化到 `data/modification_log.json`
  - `get_style_preferences()` 从修改记录学习：HOOK长度、CASE深度/视角、高频删/添词
  - `build_style_hints()` 将偏好转为 prompt hint
  - `generate_single_module` 每次生成自动注入风格偏好

#### 修复

- `scan_vault` 只扫描单层 `*.md`，改为递归 `**/*.md` 以发现子目录素材

---

### v1.0.7 (2026-05-19)

**状态**：已发布

- **Phase 4.5 CCOS v2.0**：认知推进流动态大纲（Layer 0-8，14项输出）
  - 新增 `cognitive_outline.py` — 认知模块流 + 势能曲线 + 双平台差异化
  - 新增 `ccos` CLI 命令：`python prism_os.py ccos "<标题>" --platform both`
  - Layer 0 认知对齐追问（七类追问）
  - 支持公众号/小红书双平台分别生成
- **Phase 4.6 Gap Analysis 增强**：新增 `thesis_summary` 字段，`generate_outlines()` 标记废弃

#### 优化

- **Phase 4.7 LLM 优化**：
  - Layer 2 三个 LLM 调用改为并行化（extract_core_problem / extract_cognitive_tension / infer_potential_directions）
  - `generate_dual_platform_outline` 双平台共享 Layer 2 结果（18次→12次）
  - `calculate_entropy` 熵值计算改为纯公式实现（1次→0次）
  - `recognize_content_goal` / `recognize_user_motivation` 规则版（扩充关键词表）
  - `_call_llm_raw` 修复 scene bug（设置 GATEWAY_SCENE=writing-cn）
  - 回退 `classify_topic_type` / `decide_progression_method` 到 LLM（规则版覆盖率不足）

#### 修复

- 修复 `cognitive_outline.py` 9个 LLM 调用无 Scene 的 bug
- 修复 `gap_analysis.py` 缺少 `thesis_summary` 字段问题

#### 测试

- 53项单元测试全部通过

---

### v1.0.6 (2026-05-14)

**状态**：当前版本

#### 新增

- **数字分身 Phase 3.5**：从历史选题学习思维特征（dimension_weights, style_keywords），自动筛选候选标题
- **反馈循环**：记录用户对分身推荐的接受/拒绝，计算匹配度，每 50 次触发校准
- **单元测试**：60 个测试覆盖 storage/embedding/prism_engine/cognitive_crack 纯逻辑函数

#### 修复

- `call_llm.py` API Key 从硬编码改为环境变量（KIMI_API_KEY, OPENROUTER_API_KEY）
- 删除重复的 OPENROUTER_API_KEY 定义和 refresh_openrouter_models() 调用
- 删除无用的 start-gateway.sh / stop-gateway.sh（引用不存在的 dist/http-server.js）

#### 更新

- `save_yaml()` 使用 JSON 序列化，修复扩展字段丢失问题
- `load_yaml()` 兼容新旧两种格式

---

### v1.0.5 (2026-05-08)

**状态**：已合并

#### 新增

- **三级 LLM Fallback 架构**：
  - Gateway（免费）→ Kimi（付费兜底）→ OpenRouter（付费备用）
  - Kimi 场景模型自动映射（reasoning/quality/writing-cn 等）
  - OpenRouter 模型顺序：gemini-2.0-flash-exp → claude-sonnet-4.6
- **意图识别增强**：支持话题疑问句隐式触发（为什么、是什么、如何等）
- **Kimi 模型分配**：
  - kimi-k2.6：reasoning、long-context
  - moonshot-v1-128k：quality、writing-cn/en、translation、summary、extraction
  - moonshot-v1-32k：fast
  - moonshot-v1-128k-vision-preview：multimodal

#### 修复

- Kimi kimi-k2 模型 404 问题 → 改用 moonshot-v1-128k
- Kimi kimi-k2-thinking 429 限流 → 改用 kimi-k2.6
- 意图识别对话题提问不触发的问题

#### 更新

- README.md：新增 LLM 三级 Fallback 架构说明
- call_llm.py：重写三级 fallback 逻辑

---

### v1.0.4 (2026-04-30)

**状态**：已合并

#### 新增

- 完整的用户使用手册 `MANUAL.md`，面向零基础用户

#### 修复

- 删除了 SKILL.md 中重复的"错误处理"章节

---

### v1.0.3 (2026-04-30)

**状态**：当前版本

#### 补充

- **苏格拉底网关**：补充输入类型分类（keyword/sentence/question）、target_emotion 提取、cognitive_crack 识别
- **棱镜引擎**：统一标题长度为 18-28 字，补充四维中文定义（认知裂缝/利益锚定/场景具象/反常识挑衅）
- **现实校验锚**：补充 trend_score 计算、综合评分公式 `score×0.5 + novelty×0.3 + trend×0.2`
- **相似度算法**：实现 `Jaccard×0.4 + Cosine×0.6` 计算
- **词汇指纹检测**：与现实校验锚集成，支持 cliche 检测和替换建议
- **PRISMError 异常类**：新增专用异常
- **safe_generate 函数**：完整错误处理结构
- **性能优化**：缓存机制、并行生成、API 限流重试

#### 更新

- `references/socratic_gateway.md`：补充完整实现规格
- `references/prism_engine.md`：更新四维定义
- `references/reality_anchor.md`：补充综合评分和算法
- `scripts/storage.py`：增加 cliche 检测、相似度计算、PRISMError 支持

---

### v1.0.2 (2026-04-30)

**状态**：已合并

#### 新增

- **V3 扩展**（Phase 7）：
  - `assassin_mechanism.md` - 刺客机制
  - `knowledge_topology.md` - 知识拓扑图谱
  - `prompt_evolution.md` - Prompt 自动变异
- **V4 扩展**（Phase 8）：
  - `cognitive_crack_hunter.md` - 认知裂缝捕捉
  - `digital_twin.md` - 数字分身
- **词汇指纹库**：`vocab_fingerprint.json`

#### 更新

- SKILL.md 新增 Phase 7 和 Phase 8
- README.md 更新版本覆盖（V1-V4）
- 部署检查清单新增 V3/V4 相关项

---

### v1.0.1 (2026-04-30)

**状态**：初始版本

#### 包含

- **核心模块**（V1 + V1.5 + V2）：
  - SKILL.md 主配置
  - README.md 项目说明
  - 3 个 Python 脚本（call_llm.py / search.py / storage.py）
  - 8 个参考文档（intent_recognition / socratic_gateway / prism_engine / reality_anchor / gap_analysis / logic_stress_test / cognitive_journey）
  - config/user_config.yaml.example 配置模板

#### 功能

| 模块 | 说明 |
|------|------|
| Phase 0 | 意图识别 + 追问确认 |
| Phase 1 | 苏格拉底网关（熵值计算） |
| Phase 2 | 棱镜引擎（四维生成） |
| Phase 3 | 现实校验锚（搜索查重） |
| Phase 4 | Gap Analysis + 双端大纲 |
| Phase 5 | 逻辑压力测试 + 认知旅程 |

---

## 文档目录

| 文件 | 说明 |
|------|------|
| `SKILL.md` | Skill 入口，核心配置 |
| `README.md` | 项目说明 |
| `MANUAL.md` | 用户使用手册 |
| `CHANGELOG.md` | 本文件 |
| `config/user_config.yaml.example` | 配置模板 |
| `references/*.md` | 各模块详细说明 |
| `scripts/*.py` | 工具脚本 |

---

## 迭代规范

### 版本号格式

```
major.minor.patch
```

| 位置 | 说明 |
|------|------|
| major | 主版本，不兼容变更 |
| minor | 次版本，新增功能（向后兼容） |
| patch | 补丁，bug 修复 |

### 提交规范

更新时记录：

```markdown
### x.y.z (YYYY-MM-DD)

**状态**：待发布/已发布

#### 新增
- 新增功能描述

#### 修复
- bug 修复描述

#### 更新
- 现有功能变更

#### 删除
- 已废弃功能移除
```

---

## 计划

| 版本 | 目标 | 状态 |
|------|------|------|
| v1.0.7 | Phase 4.5-4.7 CCOS + LLM优化 | ✅ 已完成 |
| v1.1.0 | Phase 5 内容生成（模块级生成，素材先行） | 开发中 |
| v1.2.0 | Phase 5.5 小红书版本 | 已完成 |
| v1.3.0 | Phase 6.0 互动数据闭环（模板优选 MVP） | ✅ 已完成 |
| v1.3.1 | Phase 6.1 calibration 接入 narrate | ✅ 已完成 |
| v2.0.0 | Web UI 界面 | 规划中 |

---

**最后更新**：2026-06-03