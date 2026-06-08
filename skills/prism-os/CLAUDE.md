# PRISM-OS 项目红线（AI 必读）

> 适用：任何 AI 代理（Claude / Codex / Cursor 等）操作本仓库
> 版本：v1.0.0 | 创建：2026-06-05
> 权威：与仓库根 `CLAUDE.md` 内容相同；流程规范以 `./SKILL.md` 为准

---

## 🚨 4 条铁律（屡次犯错的现场）

| # | 错误 | 正确做法 |
|---|------|----------|
| 1 | 直接调 `prism/gap/ccos/narrate` 单步命令 | 一律 `python prism_os.py run "<命题>"` |
| 2 | 审计/对比前没 Read/Grep 验证代码就下结论 | 先 `Read` / `Grep` 验证存在性，再下"缺失/差异"判断 |
| 3 | 替用户定义"想写什么" / 用项目边界挡选题 | 用户给选题就接，不评价"是不是这个项目的范围" |
| 4 | `echo "skip"` 自动应答，把交互流程全跑完 | 决策点必须让用户亲自回答；调试用 `--no-interactive` |

详细证据链见 `C:\Users\admin\.claude\projects\D--myproject\memory\feedback_dont_skip_flow_again.md` 等记忆文件。

---

## ⚠️ 5 个已知代码缺口（只标不修，待后续 PR）

| ID    | 触发条件（你看到 X） | 正确动作（做 Y） |
|-------|---------------------|------------------|
| GAP-1 | 跑 `run "..." --platform wechat` 平台参数不生效 | 改用 `python prism_os.py ccos "..." --platform wechat` 单独跑 CCOS |
| GAP-2 | 跑完 `run` 没出文章，停在刺客 | 手动再跑 `python prism_os.py narrate "..." --platform wechat` |
| GAP-3 | 跑 `run` 静默默认选了第一个候选标题 | 检查是否在后台跑（stdin 不可用）；前台重跑并显式输入编号 |
| GAP-4 | 跑 `run` 静默默认继续了 CCOS 大纲 | 同上 |
| GAP-5 | 跑 `run` 完没处理 Gap 缺口就进入 Phase 5 | 手动跑 `python prism_os.py gap "<thesis>"` 看缺口，再决定补/调/退 |

完整位置 + 修复建议见 `./SKILL.md` § 已知代码缺口。

---

## ✅ 必须遵守的 3 件事

1. **走 run**：所有 PRISM-OS 内容生成走 `python scripts/prism_os.py run "<命题>"`
2. **不跳过流程**：除非用户明确说"只跑 X 阶段"，否则不直接调子命令
3. **遇缺口先看本表**：跑出来结果异常时，先核对本表 GAP-1~5，再决定下一步

---

## 📚 进一步阅读

- 流程规范：`./SKILL.md`（事实源，450-500 行）
- 实操手册：`./MANUAL.md`（命令示例、UI 文本、FAQ）
- 流程图：见 SKILL.md § 完整工作流
