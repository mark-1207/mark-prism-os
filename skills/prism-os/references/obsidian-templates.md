# Obsidian 模板（Case / Atom / Insight）

> PRISM-OS 知识库三套标准模板，用于 Phase 4.6 Gap 决策中"补充素材"环节
> 路径前缀：`D:\myproject\PRISM-OSv1\40_知识库\`

## 三类素材 + 路径

| 素材类型 | 路径 | 模板 |
|---------|------|------|
| 案例类 | `40_知识库/原子库/` | Case_案例模板.md |
| 观点/数据/方法 | `40_知识库/原子库/` | Atom_原子模板.md |
| 认知裂缝洞察 | `40_知识库/洞察库/` | Insight_洞察模板.md |

## Case 案例模板

```markdown
---
类型: Case
标题: {{TITLE}}
来源: {{SOURCE_URL}}
时间: {{PUBLISH_DATE}}
标签: [{{TAG1}}, {{TAG2}}]
---

## 背景
- 主体：{{ACTOR}}
- 场景：{{SCENE}}

## 关键事件
- 触发点：{{TRIGGER}}
- 转折：{{TURNING_POINT}}
- 结果：{{OUTCOME}}

## 可借鉴点
- {{LESSON_1}}
- {{LESSON_2}}

## 关联原子
- [[Atom_xxx]]
```

## Atom 原子模板

```markdown
---
类型: Atom
标签: [{{TAG1}}]
适用场景: {{SCENARIO}}
---

## 观点
> {{CORE_CLAIM}}

## 证据
- {{EVIDENCE_1}}
- {{EVIDENCE_2}}

## 反例
- {{COUNTER_CASE}}

## 出处
- {{SOURCE}}
```

## Insight 洞察模板

```markdown
---
类型: Insight
认知裂缝类型: {{CRACK_TYPE}}
置信度: {{CONFIDENCE}}
---

## 旧认知
> {{OLD_BELIEF}}

## 新认知
> {{NEW_BELIEF}}

## 裂缝张力
- 张力值: {{TENSION}}
- 反转策略: {{REVERSAL_STRATEGY}}

## 证据链
- {{EVIDENCE_1}}
- {{EVIDENCE_2}}

## 适用选题
- {{SUGGESTED_TOPIC_1}}
- {{SUGGESTED_TOPIC_2}}
```

## 入库流程

1. 写好 .md 文件
2. 命名：`{{Type}}_{{slug}}.md`
3. 放入对应目录
4. 跑 `python scripts/prism_os.py embedding`（重建 embedding 缓存）
5. 下次 Gap 分析会自动召回
