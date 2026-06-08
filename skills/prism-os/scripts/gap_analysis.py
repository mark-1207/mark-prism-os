#!/usr/bin/env python3
"""
PRISM-OS Phase 4: Gap Analysis & 双端大纲
素材缺口分析 + 公众号/小红书大纲生成

用法:
    python gap_analysis.py analyze "<命题>" "<素材>"
    python gap_analysis.py outline "<标题>"
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional
from pathlib import Path

# ============ Phase 2.5: Obsidian 知识网关集成 ============

# 动态导入 obsidian_knowledge（避免循环依赖）
_obsidian_cache = {}


def _get_obsidian_module():
    """懒加载 obsidian_knowledge 模块"""
    global _obsidian_cache
    if not _obsidian_cache:
        # 尝试从 .claude 目录导入
        obsidian_path = Path(__file__).parent.parent.parent / ".claude" / "obsidian_knowledge.py"
        if obsidian_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("obsidian_knowledge", obsidian_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _obsidian_cache["module"] = module
        else:
            return None
    return _obsidian_cache.get("module")


def integrate_knowledge(thesis: str, vault_path: Path = None) -> Dict:
    """
    2.19 整合 Obsidian 检索到 Phase 4

    Args:
        thesis: 命题
        vault_path: Obsidian Vault 路径

    Returns:
        {
            "knowledge_results": [...],  # Obsidian 搜索结果
            "integrated": bool           # 是否成功整合
        }
    """
    obsidian = _get_obsidian_module()
    if not obsidian:
        return {"knowledge_results": [], "integrated": False, "error": "obsidian_knowledge 模块不可用"}

    try:
        # 1. 扫描 Vault
        files = obsidian.scan_vault(vault_path)
        if not files:
            return {"knowledge_results": [], "integrated": False, "error": "未找到素材文件"}

        # 2. 全文搜索
        search_results = obsidian.full_text_search(thesis, vault_path, limit=20)

        # 3. 质量过滤
        quality_results = obsidian.filter_quality(search_results, threshold=7)

        return {
            "knowledge_results": quality_results,
            "integrated": True,
            "total_files": len(files),
            "search_hits": len(search_results),
            "quality_hits": len(quality_results)
        }
    except Exception as e:
        return {"knowledge_results": [], "integrated": False, "error": str(e)}


def calculate_readiness(knowledge_results: List[Dict], evidence_chain: List[str] = None) -> Dict:
    """
    2.20 计算真实素材就绪度

    Args:
        knowledge_results: Obsidian 搜索结果
        evidence_chain: 证据链列表

    Returns:
        {
            "readiness": float,         # 就绪度 0-1
            "matched_evidence": [...],   # 已匹配的证据
            "missing_evidence": [...],   # 缺失的证据
            "material_count": int        # 可用素材数
        }
    """
    if evidence_chain is None:
        evidence_chain = []

    matched = []
    missing = []

    # 检查证据链中的每项是否有对应素材
    for evidence in evidence_chain:
        # 简单匹配：检查素材内容是否包含证据关键词
        evidence_keywords = re.findall(r'[\w]+', evidence.lower())
        matched_flag = False

        for result in knowledge_results:
            content_lower = result.get("content", "").lower()
            if any(kw in content_lower for kw in evidence_keywords if len(kw) > 2):
                matched_flag = True
                matched.append({
                    "evidence": evidence,
                    "source": result.get("name", ""),
                    "type": result.get("type", ""),
                    "relevance": result.get("relevance", 0)
                })
                break

        if not matched_flag:
            missing.append(evidence)

    # 计算就绪度
    material_count = len(knowledge_results)
    if not evidence_chain:
        # 没有证据链要求时，基于素材数量评估
        if material_count >= 5:
            readiness = 0.9
        elif material_count >= 3:
            readiness = 0.7
        elif material_count >= 1:
            readiness = 0.5
        else:
            readiness = 0.2
    else:
        # 有证据链时，基于匹配率
        readiness = len(matched) / len(evidence_chain) if evidence_chain else 0

    return {
        "readiness": min(1.0, readiness),
        "matched_evidence": matched,
        "missing_evidence": missing,
        "material_count": material_count
    }


def output_materials(knowledge_results: List[Dict], limit: int = 10) -> List[Dict]:
    """
    2.21 输出可用素材列表

    Args:
        knowledge_results: Obsidian 搜索结果
        limit: 返回数量限制

    Returns:
        [{"name": str, "type": str, "path": str, "quality_score": float, "relevance": float}, ...]
    """
    materials = []

    for r in knowledge_results[:limit]:
        materials.append({
            "name": r.get("name", ""),
            "type": r.get("type", ""),
            "path": r.get("path", ""),
            "quality_score": r.get("quality_score", 0),
            "relevance": r.get("relevance", 0)
        })

    return materials


# ============ Phase 4: Gap Analysis ============

def analyze_gap(thesis: str, materials: str = "") -> Dict:
    """
    分析选题需要的证据链，评估现有素材就绪度

    Args:
        thesis: 命题
        materials: 现有素材（可选）

    Returns:
        {
            "evidence_chain": [...],
            "matched_materials": [...],
            "missing_evidence": [...],
            "gap_score": float,
            "readiness": float,
            "recommendation": str
        }
    """
    prompt = f"""你是内容策划分析师。分析选题需要的证据链，评估现有素材就绪度。

命题：{thesis}
现有素材：{materials if materials else "无"}

任务：
1. 总结命题的核心论点（一句话）
2. 提取支撑该论点所需的证据链（数据类型/案例/理论依据）
3. 评估现有素材就绪度

返回 JSON：
{{
  "thesis_summary": "命题的核心论点（一句话总结）",
  "evidence_chain": ["证据1", "证据2", "证据3"],
  "matched_materials": [{{"evidence": "证据1", "source": "来源", "match_score": 0.85}}],
  "missing_evidence": ["证据2", "证据3"],
  "gap_score": 0.67,
  "readiness": 0.33,
  "recommendation": "建议补充 2 个关键素材"
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "thesis_summary": thesis,
            "evidence_chain": [],
            "matched_materials": [],
            "missing_evidence": [],
            "gap_score": 1.0,
            "readiness": 0.0,
            "recommendation": "素材分析失败"
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "thesis_summary": thesis,
            "evidence_chain": [],
            "matched_materials": [],
            "missing_evidence": [],
            "gap_score": 1.0,
            "readiness": 0.0,
            "recommendation": "素材分析失败"
        }

    return parsed


# ============ Phase 4: 双端大纲（已废弃，仅 --legacy 可用） ============

def generate_outlines(title: str, audience: str = "", dimension: str = "") -> Dict:
    """
    为同一选题生成公众号/小红书两套大纲

    Args:
        title: 标题
        audience: 目标受众（可选）
        dimension: 标题维度（reversal/micro_scene/systemic_flaw/bridge）

    Returns:
        {
            "wechat_outline": {...},
            "xiaohongshu_outline": {...}
        }
    """
    # 维度差异化提示
    dimension_hints = {
        "reversal": {
            "wechat": "重点拆解反直觉真相，用逻辑推演颠覆常识",
            "xiaohongshu": "用反常识钩子引发好奇，快速揭示真相"
        },
        "micro_scene": {
            "wechat": "深入剖析具体场景，用细节还原真相",
            "xiaohongshu": "用具体场景引发共鸣，快速切入痛点"
        },
        "systemic_flaw": {
            "wechat": "揭示结构性问题，用系统思维分析根源",
            "xiaohongshu": "用痛点引发焦虑，快速给出解决方案"
        },
        "bridge": {
            "wechat": "提供方法论和工具，用步骤引导行动",
            "xiaohongshu": "用具体步骤降低门槛，快速引导行动"
        }
    }

    hint = dimension_hints.get(dimension, dimension_hints["reversal"])

    prompt = f"""你是全平台内容策划师。为同一选题生成两套差异化大纲。

选题：{title}
{f"目标受众：{audience}" if audience else ""}
标题维度：{dimension if dimension else "未指定"}

**公众号大纲（逻辑流）**：
- 结构：引子 → 论点 → 论据 → 反驳 → 升华
- 风格：深度、理性、逻辑严密
- 字数：3000-5000 字
- **差异化重点**：{hint['wechat']}

**小红书大纲（视觉流）**：
- 结构：钩子 → 痛点 → 解决方案 → 行动号召
- 风格：视觉化、情绪化、可操作
- 字数：800-1200 字
- **差异化重点**：{hint['xiaohongshu']}

返回 JSON：
{{
  "wechat_outline": {{
    "hook": "引子...",
    "sections": [{{"title": "...", "key_points": ["...", "..."]}}],
    "cta": "行动号召"
  }},
  "xiaohongshu_outline": {{
    "hook": "一句话钩子",
    "pain_point": "痛点描述",
    "solution": "3 步解决方案",
    "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
    "cta": "点赞收藏"
  }}
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "wechat_outline": None,
            "xiaohongshu_outline": None,
            "error": "大纲生成失败"
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "wechat_outline": None,
            "xiaohongshu_outline": None,
            "error": "大纲解析失败"
        }

    return parsed


def gap_analysis(thesis: str, materials: str = "", title: str = "", audience: str = "", dimension: str = "") -> Dict:
    """
    Phase 4 完整流程：Gap Analysis + 双端大纲 + Obsidian 知识整合

    Args:
        thesis: 命题
        materials: 现有素材
        title: 标题（可选，用于生成大纲）
        audience: 目标受众
        dimension: 标题维度（reversal/micro_scene/systemic_flaw/bridge）

    Returns:
        Gap Analysis + 双端大纲 + 知识网关结果
    """
    result = {
        "phase": "gap_analysis",
        "gap": None,
        "outlines": None,
        "knowledge": None  # Obsidian 知识整合结果
    }

    # ========== Obsidian 知识整合（Phase 2.5）==========
    knowledge_result = integrate_knowledge(thesis)
    result["knowledge"] = knowledge_result

    # ========== Gap Analysis ==========
    if thesis:
        # 获取证据链
        gap_result = analyze_gap(thesis, materials)

        # 如果有 Obsidian 素材，计算真实就绪度
        if knowledge_result.get("integrated") and knowledge_result.get("knowledge_results"):
            knowledge_results = knowledge_result["knowledge_results"]
            evidence_chain = gap_result.get("evidence_chain", [])

            readiness_info = calculate_readiness(knowledge_results, evidence_chain)
            gap_result["knowledge_readiness"] = readiness_info["readiness"]
            gap_result["matched_evidence"] = readiness_info["matched_evidence"]
            gap_result["missing_evidence"] = readiness_info["missing_evidence"]
            gap_result["material_count"] = readiness_info["material_count"]

            # 输出可用素材
            gap_result["materials"] = output_materials(knowledge_results)

            # 调整总体就绪度
            original_readiness = gap_result.get("readiness", 0)
            gap_result["readiness"] = max(original_readiness, readiness_info["readiness"])

        result["gap"] = gap_result

    # ========== 双端大纲 ==========
    if title:
        outline_result = generate_outlines(title, audience, dimension)
        result["outlines"] = outline_result

    return result


# ============ 辅助函数 ============

def _call_llm_raw(prompt: str) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=0.7, scene="writing-cn", error_prefix="[Error] LLM:")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出中解析 JSON"""
    if not text:
        return None

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

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
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


def main():
    if len(sys.argv) < 3:
        _safe_print({
            "error": "用法: gap_analysis.py <命令> <数据>",
            "commands": {
                "analyze": "gap_analysis.py analyze \"<命题>\" \"<素材>\" - 素材缺口分析",
                "outline": "gap_analysis.py outline \"<标题>\" - 生成双端大纲",
                "full": "gap_analysis.py full \"<命题>\" \"<素材>\" \"<标题>\" - 完整流程"
            }
        })
        sys.exit(1)

    command = sys.argv[1]

    if command == "analyze":
        thesis = sys.argv[2] if len(sys.argv) > 2 else ""
        materials = sys.argv[3] if len(sys.argv) > 3 else ""
        result = analyze_gap(thesis, materials)
        _safe_print(result)

    elif command == "outline":
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        print("[Deprecation] generate_outlines() 已废弃，请使用 cognitive_outline.py outline/dual", file=sys.stderr)
        result = generate_outlines(title)
        _safe_print(result)

    elif command == "full":
        thesis = sys.argv[2] if len(sys.argv) > 2 else ""
        materials = sys.argv[3] if len(sys.argv) > 3 else ""
        title = sys.argv[4] if len(sys.argv) > 4 else ""
        print("[Deprecation] gap_analysis() full 已废弃，Phase 4 已迁移至 cognitive_outline.py", file=sys.stderr)
        result = gap_analysis(thesis, materials, title)
        _safe_print(result)

    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()