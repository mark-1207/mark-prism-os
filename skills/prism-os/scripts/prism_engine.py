#!/usr/bin/env python3
"""
PRISM-OS Phase 2: 棱镜引擎（Prism Engine）
四维标题生成脚本

用法:
    python prism_engine.py generate "<命题>"
    python prism_engine.py validate "<命题>"
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional, Tuple

# ============ Phase 2: 四维标题生成 ============

DIMENSIONS = {
    "reversal": {
        "name": "逆向拆解",
        "description": "颠覆常识，揭示反直觉真相",
        "formula": "为什么'常识A'其实是'真相B'？"
    },
    "benefit_anchor": {
        "name": "利益锚点",
        "description": "绑住用户的钱/前途/认知/效率",
        "formula": "为什么'做X'能让用户'得到Y'？"
    },
    "micro_scene": {
        "name": "微观切片",
        "description": "聚焦具体场景或人群",
        "formula": "在'场景X'中，'现象Y'如何发生？"
    },
    "contrarian": {
        "name": "反向论证",
        "description": "反对主流共识，揭示反方证据",
        "formula": "大家都说'A是真的'，但'B'才是真相"
    }
}

# 旧 4 维（保留为 --preset-flavor legacy 选项）
LEGACY_DIMENSIONS = {
    "reversal": {
        "name": "逆向拆解",
        "description": "颠覆常识，揭示反直觉真相",
        "formula": "为什么'常识A'其实是'真相B'？"
    },
    "micro_scene": {
        "name": "微观切片",
        "description": "聚焦具体场景或人群",
        "formula": "在'场景X'中，'现象Y'如何发生？"
    },
    "systemic_flaw": {
        "name": "系统归因",
        "description": "指向结构性问题",
        "formula": "'现象X'的根源是'系统缺陷Y'。"
    },
    "bridge": {
        "name": "认知脚手架",
        "description": "提供方法论或工具",
        "formula": "如何用'方法X'解决'问题Y'？"
    }
}

# ============ 读者标题原型（Phase 2 v2.0）============

TITLE_ARCHETYPES = {
    "opinion_assertion": {
        "name": "观点断言型",
        "description": "一个明确判断句，不解释、不铺垫，直接亮态度",
        "formula": "核心观点+具体对象+反常识标签",
        "reader_trigger": "立场/态度 - 这人敢这么说?"
    },
    "identity_label": {
        "name": "身份标签型",
        "description": "把读者划入一个身份，让ta觉得这说的就是我",
        "formula": "身份标签+共同困境/特征+悬念",
        "reader_trigger": "代入/归属 - XX的人，都..."
    },
    "scene_suspense": {
        "name": "场景悬念型",
        "description": "用具体场景开头，悬念不解释，逼读者点进来找答案",
        "formula": "具体场景+反预期结果+不说为什么",
        "reader_trigger": "好奇/画面 - 发生了什么?"
    },
    "data_counter_ask": {
        "name": "数据反问型",
        "description": "用具体数字制造冲击，再用反问让读者自己站队",
        "formula": "数据+对立面+反问",
        "reader_trigger": "冲击/反思 - 这个数字意味着什么?"
    },
    "story_hook": {
        "name": "故事钩子型",
        "description": "用第一人称真实经历开头，故事未讲完就截断",
        "formula": "我/他+做了X+发现Y+没说结论",
        "reader_trigger": "共情/代入 - 后来呢?"
    }
}

# 认知维度 → 标题原型推荐映射（PRD 4 维）
DIMENSION_TO_ARCHETYPE = {
    "reversal": ["opinion_assertion", "data_counter_ask"],
    "benefit_anchor": ["identity_label", "opinion_assertion"],
    "micro_scene": ["scene_suspense", "story_hook"],
    "contrarian": ["opinion_assertion", "data_counter_ask"],
}

BANNED_WORDS = [
    "赋能", "降维打击", "破圈", "必须知道", "震惊",
    "惊呆了", "重磅", "震撼", "颠覆", "必看",
    "绝了", "哭了", "全網", "全网", "藏不住了",
    "太绝了", "一定要看", "后悔没早知道", "刷屏",
    "炸裂", "沸腾", "刷爆", "都在看", "深度好文",
    "揭秘", "真相", "竟然", "原来", "惊人",
    "意外发现", "一文看懂", "深度思考", "底层逻辑",
    "你不知道", "99%", "每个人都",
    # 扩充：更多 AI 套路词
    "万万没想到", "意想不到", "出乎意料", "细思极恐",
    "不寒而栗", "毛骨悚然", "恍然大悟", "醍醐灌顶",
    "一针见血", "入木三分", "振聋发聩", "发人深省",
    "不可不知", "不可错过", "不容错过", "务必了解",
]


def _estimate_dimension_scores(thesis: str) -> Dict[str, float]:
    """
    基于命题文本特征估算4维认知得分（规则版，不调用LLM）

    Returns:
        {"reversal": float, "micro_scene": float, "systemic_flaw": float, "bridge": float}
    """
    scores = {"reversal": 0.3, "micro_scene": 0.3, "systemic_flaw": 0.3, "bridge": 0.3}

    # reversal: 反常识/逆向关键词
    reversal_kw = ["其实", "却", "反直觉", "真相", "误区", "不是", "错了", "你以为", "颠覆"]
    scores["reversal"] = min(0.3 + sum(1 for kw in reversal_kw if kw in thesis) * 0.15, 1.0)

    # micro_scene: 具体场景/人称
    scene_kw = ["在", "当", "一个", "我", "你", "他/她", "公司", "团队", "一个人", "身边", "每天"]
    scores["micro_scene"] = min(0.3 + sum(1 for kw in scene_kw if kw in thesis) * 0.12, 1.0)

    # systemic_flaw: 结构性问题/系统归因
    flaw_kw = ["系统", "结构", "根源", "制度", "机制", "循环", "体系", "底层", "资本", "社会"]
    scores["systemic_flaw"] = min(0.3 + sum(1 for kw in flaw_kw if kw in thesis) * 0.18, 1.0)

    # bridge: 方法/工具/框架
    bridge_kw = ["如何", "怎么", "方法", "模型", "框架", "步骤", "技巧", "策略", "方案", "工具"]
    scores["bridge"] = min(0.3 + sum(1 for kw in bridge_kw if kw in thesis) * 0.15, 1.0)

    return scores


def check_banned_words(title: str) -> Tuple[bool, List[str]]:
    """检查标题是否包含禁用词"""
    found = []
    for word in BANNED_WORDS:
        if word in title:
            found.append(word)
    return len(found) > 0, found


def generate_dimension_titles(thesis: str, dimension: str, identity_role: str = "", audience: str = "") -> List[Dict]:
    """
    生成单个维度的3个候选标题

    Args:
        thesis: 命题
        dimension: 维度名称
        identity_role: 用户身份
        audience: 目标受众

    Returns:
        [{"title": str, "rationale": str}, ...]
    """
    dim_config = DIMENSIONS.get(dimension, DIMENSIONS["reversal"])

    prompt = f"""你是顶级选题策划师，专注爆款内容策划。根据用户命题，生成{dimension}维度的3个候选标题。

**维度定义：**
{dim_config['name']}（{dim_config['description']}）
公式：{dim_config['formula']}

**爆款标题核心特征：**
1. **情绪触发**：引发好奇、惊讶、焦虑、共鸣等情绪反应
2. **认知冲突**：打破读者固有认知，制造"原来如此"的顿悟感
3. **悬念感**：留下未解之谜，激发点击欲望
4. **利益相关**：与读者的钱途、职业发展、认知升级直接相关
5. **具体可信**：有数字、场景、人物、时间等具体元素

**约束条件：**
- 每个标题必须在18-28字之间
- 禁止使用：赋能、降维打击、破圈、必须知道、震惊等陈词滥调
- **禁止 AI 套路化句式**：揭秘/真相/竟然/原来/惊人/意外发现/一文看懂/你不知道/…省略号悬念/问号感叹号堆砌
- **风格要求**：像真人写的朋友圈/即刻/小红书文案，不像营销号或 AI 生成；口语化、有具体人称、有真实场景
- 必须包含"认知落差"（旧认知 vs 新认知）
- 必须有具体数字、场景或对比
- 避免使用"你必须知道"等说教式开头
- **必须引发情绪反应**（好奇/惊讶/焦虑/共鸣）
- **必须与读者利益相关**（赚钱/职业/认知/效率）

**反面示例（禁止生成这类标题）：**
- ❌ "AI时代，你必须知道的5个职场真相"（说教+套路）
- ❌ "揭秘！AI裁员背后的惊人真相"（AI腔+禁用词）
- ❌ "为什么学AI的人都赚不到钱？"（AI腔问句）
- ❌ "AI时代下，裁员已成必然趋势"（空洞陈述）

**正面示例（参考风格）：**
- ✓ "我被AI替代的那天，才明白一个道理"（第一人称+场景+悬念）
- ✓ "同事被裁后，我偷偷学了3个月AI"（具体场景+人称+行动）
- ✓ "35岁，我决定不再假装不懂AI"（年龄标签+情绪+决定）

用户命题：{thesis}
{f"用户身份：{identity_role}" if identity_role else ""}
{f"目标受众：{audience}" if audience else ""}

返回JSON格式：
{{
  "candidates": [
    {{"title": "标题1", "rationale": "标题理由（说明情绪触发点和利益点）"}},
    {{"title": "标题2", "rationale": "标题理由（说明情绪触发点和利益点）"}},
    {{"title": "标题3", "rationale": "标题理由（说明情绪触发点和利益点）"}}
  ]
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return []

    parsed = _parse_llm_json(result)
    if not parsed or "candidates" not in parsed:
        return []

    # 验证和清理
    valid_candidates = []
    for c in parsed["candidates"]:
        title = c.get("title", "").strip()
        rationale = c.get("rationale", "").strip()

        # 检查长度（18-28字）
        char_count = len(title)
        if char_count < 18 or char_count > 28:
            continue

        # 检查禁用词
        has_banned, found = check_banned_words(title)
        if has_banned:
            continue

        valid_candidates.append({
            "title": title,
            "rationale": rationale,
            "dimension": dimension,
            "char_count": char_count
        })

    return valid_candidates


def select_title_archetypes(dimension_scores: Dict[str, float]) -> List[str]:
    """
    根据认知维度得分，推荐最适合的标题原型（2-4个）

    Args:
        dimension_scores: {"reversal": float, "micro_scene": float, "systemic_flaw": float, "bridge": float}

    Returns:
        推荐的 archetype key 列表（按优先级排序）
    """
    archetype_scores = {}
    for archetype_key in TITLE_ARCHETYPES:
        archetype_scores[archetype_key] = 0.0

    # 累计每个原型的得分（通过维度映射）
    for dimension, score in dimension_scores.items():
        if dimension in DIMENSION_TO_ARCHETYPE:
            for archetype in DIMENSION_TO_ARCHETYPE[dimension]:
                archetype_scores[archetype] = archetype_scores.get(archetype, 0.0) + score

    # 按得分降序排列
    ranked = sorted(archetype_scores.items(), key=lambda x: x[1], reverse=True)

    # 取前2-4个（得分>0.2的优先）
    selected = [k for k, v in ranked if v > 0.2]
    if len(selected) < 2:
        selected = [k for k, v in ranked[:2]]  # 至少2个
    if len(selected) > 4:
        selected = selected[:4]  # 至多4个

    return selected


def generate_archetype_titles(thesis: str, archetype: str,
                               identity_role: str = "", audience: str = "",
                               count: int = 2) -> List[Dict]:
    """
    按指定原型生成候选标题

    Args:
        thesis: 命题
        archetype: 原型 key（如 "opinion_assertion"）
        identity_role: 用户身份
        audience: 目标受众
        count: 生成几个（1-3）

    Returns:
        [{"title": str, "rationale": str, "archetype": str, "char_count": int}, ...]
    """
    arch_config = TITLE_ARCHETYPES.get(archetype)
    if not arch_config:
        return []

    prompt = f"""你是顶级选题策划师，专注爆款内容策划。用「{arch_config['name']}」的方式为命题生成 {count} 个候选标题。

**原型定义：**
- 名称：{arch_config['name']}
- 核心手法：{arch_config['description']}
- 公式：{arch_config['formula']}
- 读者触发点：{arch_config['reader_trigger']}

**爆款标题核心特征：**
1. **有观点**：标题像一个人在说话，不是一个主题概括
2. **有节奏**：短-长-短、问-答-问、数-感-问，读起来有呼吸感
3. **有人称**：出现"你"或"我"，制造对话感
4. **有情绪**：愤怒/惊讶/好奇/共鸣，不能是中性陈述
5. **有悬念**：说完一半，留一半，逼人点进去

**禁止格式：**
- 禁止：为什么XX，其实是YY？（AI腔过重）
- 禁止：XX的本质是YY（教科书标题）
- 禁止：你必须知道的XX个ZZ（说教式）
- 禁止以"如何"开头除非是故事钩子型

**长度要求：**
- 公众号：20-30字
- 小红书：15-22字（如有平台参数）

用户命题：{thesis}
{f"用户身份：{identity_role}" if identity_role else ""}
{f"目标受众：{audience}" if audience else ""}
原型：{arch_config['name']}

返回JSON：
{{
  "candidates": [
    {{"title": "标题1", "rationale": "标题理由（说明使用了什么手法、触发什么情绪）"}},
    ...
  ]
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return []

    parsed = _parse_llm_json(result)
    if not parsed or "candidates" not in parsed:
        return []

    valid_candidates = []
    for c in parsed["candidates"]:
        title = c.get("title", "").strip()
        rationale = c.get("rationale", "").strip()

        if not title:
            continue

        # 检查长度（18-28 字）
        char_count = len(title)
        if char_count < 18 or char_count > 28:
            continue

        # 检查禁用词
        has_banned, found = check_banned_words(title)
        if has_banned:
            continue

        valid_candidates.append({
            "title": title,
            "rationale": rationale,
            "archetype": archetype,
            "char_count": len(title)
        })

    return valid_candidates[:count]


def generate_all_titles(thesis: str, identity_role: str = "", audience: str = "", flavor: str = "prd") -> List[Dict]:
    """
    遍历 4 维，每维生成 3 个候选标题 = 总计 12 个

    流程：
    1. 遍历 4 维（reversal / benefit_anchor / micro_scene / contrarian）
    2. 每维调 generate_dimension_titles(thesis, dim, count=3)
    3. 失败/不足时补生成（同一维重试一次）
    4. 总计 12 个选题

    Args:
        thesis: 命题
        identity_role: 用户身份
        audience: 目标受众
        flavor: "prd"（默认）或 "legacy"（旧 4 维）

    Returns:
        所有候选标题列表
    """
    # 选择 4 维
    if flavor == "legacy":
        dimensions = list(LEGACY_DIMENSIONS.keys())
    else:
        dimensions = list(DIMENSIONS.keys())

    # 遍历 4 维，每维 3 选题
    all_candidates = []
    for dim in dimensions:
        dim_titles = generate_dimension_titles(thesis, dim, identity_role, audience)
        # 不足 3 时补一次
        if len(dim_titles) < 3:
            retry = generate_dimension_titles(thesis, dim, identity_role, audience)
            dim_titles.extend(retry)
        all_candidates.extend(dim_titles[:3])

    return all_candidates


def calculate_jaccard_similarity(title_a: str, title_b: str) -> float:
    """计算 Jaccard 相似度"""
    tokens_a = set(re.findall(r'\w+', title_a.lower()))
    tokens_b = set(re.findall(r'\w+', title_b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def _precompute_embeddings(titles: List[str]) -> Dict[str, Optional[List[float]]]:
    """预计算所有标题的向量（有缓存，失败返回 None）"""
    try:
        from embedding import embed
    except ImportError:
        return {}

    vectors = {}
    for title in titles:
        vec = embed(title)
        if vec is not None:
            vectors[title] = vec
    return vectors


def _calculate_similarity(title_a: str, title_b: str, vectors: Dict[str, List[float]]) -> float:
    """综合相似度：Jaccard×0.4 + Cosine×0.6（无向量时降级到纯 Jaccard）"""
    jaccard = calculate_jaccard_similarity(title_a, title_b)

    vec_a = vectors.get(title_a)
    vec_b = vectors.get(title_b)
    if vec_a and vec_b:
        try:
            from embedding import cosine_similarity
            cosine = cosine_similarity(vec_a, vec_b)
            return 0.4 * jaccard + 0.6 * cosine
        except ImportError:
            pass

    return jaccard


def check_orthogonality(candidates: List[Dict]) -> List[Dict]:
    """
    检查候选标题的正交性（相似度 < 0.75）
    使用 Embedding Cosine + Jaccard 综合相似度，Embedding 不可用时降级到纯 Jaccard

    Returns:
        带相似度标记的候选列表
    """
    titles = [c["title"] for c in candidates]
    vectors = _precompute_embeddings(titles)

    marked = []
    for i, candidate in enumerate(candidates):
        max_similarity = 0.0
        similar_titles = []

        for j, other in enumerate(candidates):
            if i == j:
                continue
            sim = _calculate_similarity(candidate["title"], other["title"], vectors)
            if sim > max_similarity:
                max_similarity = sim
            if sim > 0.5:
                similar_titles.append(other["title"][:20])

        candidate["max_similarity"] = max_similarity
        candidate["similar_titles"] = similar_titles[:3]
        candidate["orthogonal"] = max_similarity < 0.75

        marked.append(candidate)

    return marked


def prism_engine(thesis: str, identity_role: str = "", audience: str = "") -> Dict:
    """
    棱镜引擎主流程

    Args:
        thesis: 命题
        identity_role: 用户身份
        audience: 目标受众

    Returns:
        {
            "status": "success" | "partial" | "error",
            "candidates": [...],
            "orthogonal_count": int,
            "warnings": [...]
        }
    """
    # Step 1: 生成所有标题
    candidates = generate_all_titles(thesis, identity_role, audience)

    if not candidates:
        return {
            "status": "error",
            "candidates": [],
            "orthogonal_count": 0,
            "warnings": ["标题生成失败"]
        }

    # Step 2: 检查正交性
    candidates = check_orthogonality(candidates)

    # 统计
    orthogonal_count = sum(1 for c in candidates if c["orthogonal"])
    warnings = []

    # 添加相似度警告
    for c in candidates:
        if not c["orthogonal"]:
            warnings.append(f"标题 '{c['title'][:20]}...' 与其他候选相似度较高")

    status = "success" if orthogonal_count >= 5 else "partial"

    return {
        "status": status,
        "candidates": candidates,
        "orthogonal_count": orthogonal_count,
        "total_count": len(candidates),
        "warnings": warnings
    }


# ============ 辅助函数 ============

def _call_llm_raw(prompt: str) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=0.7, scene="writing-cn", error_prefix="LLM 调用错误:")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出中解析 JSON"""
    if not text:
        return None

    # 尝试提取 JSON 代码块
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试找到 JSON 对象
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[Warning] JSON 解析失败: {e}", file=sys.stderr)

    return None


# ============ CLI 入口 ============

def _safe_print(obj):
    """修复 Windows GBK 编码问题"""
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


def main():
    if len(sys.argv) < 3:
        _safe_print({
            "error": "用法: python prism_engine.py <命令> <命题>",
            "commands": {
                "generate": "python prism_engine.py generate <命题> - 生成候选标题",
                "validate": "python prism_engine.py validate <命题> - 生成并校验正交性"
            }
        })
        sys.exit(1)

    command = sys.argv[1]
    thesis = sys.argv[2]

    if command == "generate":
        candidates = generate_all_titles(thesis)
        _safe_print({
            "candidates": candidates,
            "total_count": len(candidates)
        })

    elif command == "validate":
        result = prism_engine(thesis)
        _safe_print(result)

    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()