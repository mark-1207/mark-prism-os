#!/usr/bin/env python3
"""
PRISM-OS Phase 5: 内容生成模块
从 CCOS 大纲到完整初稿的分模块生成

用法:
    python prism_os.py generate "<标题>" --platform wechat
    python prism_os.py generate "<标题>" --platform xiaohongshu
"""

import sys
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# ============ LLM 调用 ============

def _call_llm_raw(prompt: str, temperature: float = 0.7) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=temperature, scene="writing-cn", error_prefix="[LLM Error]")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出解析 JSON"""
    if not text:
        return None
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(code_block_pattern, text)
    if match:
        text = match.group(1)
    else:
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_pattern = r"\{[\s\S]*\}"
        match = re.search(json_pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ============ 素材召回（按模块类型）============

def _get_obsidian_module():
    """懒加载 obsidian_knowledge"""
    obsidian_path = Path(__file__).parent.parent.parent / ".claude" / "obsidian_knowledge.py"
    if not obsidian_path.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("obsidian_knowledge", obsidian_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 素材类型 → Obsidian 子目录映射
MODULE_MATERIAL_PRIORITY = {
    "HOOK": {
        "primary": ["洞察库"],  # 反常识洞察
        "secondary": ["原子库"],
        "reason": "HOOK 需要反直觉案例/冲突性数据"
    },
    "CASE": {
        "primary": ["原子库", "案例库"],
        "secondary": ["洞察库"],
        "reason": "CASE 需要具体场景/人物故事"
    },
    "EXPLAIN": {
        "primary": ["原子库"],
        "secondary": ["洞察库"],
        "reason": "EXPLAIN 需要分析框架/因果解释"
    },
    "MODEL": {
        "primary": ["原子库", "思维模型"],
        "secondary": ["原子库"],
        "reason": "MODEL 需要认知模型/方法论框架"
    },
    "COUNTER": {
        "primary": ["洞察库"],
        "secondary": ["原子库"],
        "reason": "COUNTER 需要反直觉观点"
    },
    "ACTION": {
        "primary": ["原子库", "方法库"],
        "secondary": [],
        "reason": "ACTION 需要操作步骤/清单"
    },
    "BOUNDARY": {
        "primary": ["洞察库", "原子库"],
        "secondary": [],
        "reason": "BOUNDARY 需要适用边界条件"
    },
    "EVIDENCE": {
        "primary": ["原子库", "洞察库"],
        "secondary": [],
        "reason": "EVIDENCE 需要数据/案例支撑"
    }
}


def recall_materials_by_module(
    topic: str,
    module_type: str,
    vault_path: Path = None
) -> List[Dict]:
    """
    按模块类型召回 Obsidian 素材

    Args:
        topic: 命题
        module_type: 模块类型 HOOK/CASE/EXPLAIN/MODEL/ACTION/COUNTER/BOUNDARY/EVIDENCE
        vault_path: Obsidian vault 路径

    Returns:
        [{"name": str, "type": str, "content": str, "relevance": float, "quality_score": float}, ...]
    """
    obsidian = _get_obsidian_module()
    if not obsidian:
        return []

    if vault_path is None:
        vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")

    priority = MODULE_MATERIAL_PRIORITY.get(module_type, MODULE_MATERIAL_PRIORITY["CASE"])

    all_results = []
    seen_names = set()

    # 优先搜索 primary 目录
    for subdir in priority["primary"] + priority["secondary"]:
        # 构造查询词
        query = f"{topic} {priority['reason']}"
        results = obsidian.full_text_search(query, vault_path, limit=15)
        for r in results:
            if r["name"] not in seen_names:
                r["material_type"] = module_type
                r["priority"] = "primary" if subdir in priority["primary"] else "secondary"
                all_results.append(r)
                seen_names.add(r["name"])

    # 质量过滤
    filtered = obsidian.filter_quality(all_results, threshold=7)

    # 按相关性和质量排序
    filtered.sort(key=lambda x: (x.get("relevance", 0) * 0.6 + x.get("quality_score", 0) / 10 * 0.4), reverse=True)

    return filtered[:8]


# ============ 素材缺口检测 ============

def detect_material_gaps(
    topic: str,
    ccos_outline: Dict,
    vault_path: Path = None
) -> Dict[str, List[str]]:
    """
    检测每个模块的素材缺口

    Args:
        topic: 命题
        ccos_outline: CCOS 14项输出
        vault_path: Obsidian vault 路径

    Returns:
        {
            "HOOK": {"has_gap": bool, "gap_description": str, "recalled_count": int},
            ...
        }
    """
    module_flow = ccos_outline.get("认知模块流", [])
    gaps = {}

    for module in module_flow:
        mod_type = module.get("模块", "")
        mod_content = module.get("内容摘要", "")

        # 召回素材
        materials = recall_materials_by_module(topic, mod_type, vault_path)

        if len(materials) < 1:
            gaps[mod_type] = {
                "has_gap": True,
                "gap_description": f"缺少 {mod_type} 类型素材，建议补充：{MODULE_MATERIAL_PRIORITY.get(mod_type, {}).get('reason', '相关素材')}",
                "recalled_count": 0,
                "materials": []
            }
        else:
            gaps[mod_type] = {
                "has_gap": False,
                "gap_description": "",
                "recalled_count": len(materials),
                "materials": [
                    {
                        "name": m["name"],
                        "type": m["type"],
                        "relevance": round(m.get("relevance", 0), 2),
                        "quality_score": m.get("quality_score", 0)
                    }
                    for m in materials[:5]
                ]
            }

    return gaps


# ============ 文章抓取（autocli）============

AUTOCLI_PATH = r"D:\myproject\内容系统v1\contentforge\autocli.exe"


def _run_autocli(args: List[str], timeout: int = 60) -> str:
    """运行 autocli 命令"""
    import subprocess
    cmd = [AUTOCLI_PATH] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"[autocli error] {e}"


def scrape_article(url: str, format: str = "json") -> Optional[Dict]:
    """
    用 autocli 抓取文章内容

    Args:
        url: 文章 URL
        format: 输出格式 (json/text/markdown)

    Returns:
        {"title": str, "content": str, "url": str} 或 None
    """
    # 微信公众号用专用命令（三级降级：autocli → wechat-article-extractor → markitdown-web）
    if "mp.weixin.qq.com" in url:
        # Level 1: autocli
        output = _run_autocli(["weixin", "download", url, "--format", "json"])
        if output and not output.startswith("[autocli error]"):
            try:
                parsed = json.loads(output)
                if isinstance(parsed, list):
                    parsed = parsed[0]
                if parsed.get("status") == "ok":
                    title = parsed.get("title", "")
                    md_path = parsed.get("path", "")
                    if md_path:
                        try:
                            with open(md_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            content = re.sub(r"^---[\s\S]*?---\n", "", content).strip()
                            import os
                            os.remove(md_path)
                        except Exception:
                            content = ""
                    else:
                        content = parsed.get("content", "")
                    return {"title": title, "content": content, "url": url}
            except Exception:
                pass

        # Level 2: wechat-article-extractor skill
        try:
            extractor_path = Path(r"C:\Users\admin\.claude\skills\wechat-article-extractor\scripts\extract.js")
            if extractor_path.exists():
                import subprocess
                result = subprocess.run(
                    ["node", str(extractor_path), url, "--json"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    encoding="utf-8",
                    errors="replace"
                )
                if result.returncode == 0 and result.stdout:
                    extracted = json.loads(result.stdout)
                    if extracted.get("done"):
                        title = extracted.get("data", {}).get("msg_title", "")
                        raw_content = extracted.get("data", {}).get("msg_content", "")
                        # 去掉 HTML 标签
                        content = re.sub(r"<[^>]+>", "", raw_content).strip()
                        return {"title": title, "content": content, "url": url}
        except Exception:
            pass

        # Level 3: markitdown-web 本地渲染（最终 fallback）
        try:
            markitdown_url = "http://localhost:3001/api/scrape"
            import urllib.request
            req = urllib.request.Request(
                markitdown_url,
                data=json.dumps({"url": url}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("content"):
                    return {
                        "title": data.get("title", ""),
                        "content": data.get("content", ""),
                        "url": url
                    }
        except Exception:
            pass

        return None

    # 其他 URL 用通用 read 命令
    output = _run_autocli(["read", url, "--format", format])
    if not output or output.startswith("[autocli error]"):
        return None

    if format == "json":
        try:
            return json.loads(output)
        except Exception:
            return None
    else:
        # text/markdown: 返回 title 和 content
        lines = output.strip().split("\n", 1)
        title = lines[0] if lines else ""
        content = lines[1] if len(lines) > 1 else ""
        return {"title": title, "content": content, "url": url}


def extract_key_content(scrape_result: Dict, module_type: str) -> Dict:
    """
    从抓取结果中提取关键段落用于素材库

    Args:
        scrape_result: scrape_article 返回结果
        module_type: 模块类型（决定提取策略）

    Returns:
        {"summary": str, "key_paragraphs": List[str], "suggested_type": str}
    """
    content = scrape_result.get("content", "")
    if not content:
        return {"summary": "", "key_paragraphs": [], "suggested_type": "case"}

    # 用 LLM 提取关键内容
    prompt = f"""从以下文章内容中提取适合素材库的关键段落。

文章标题：{scrape_result.get('title', '')}

内容：
{content[:3000]}

模块类型：{module_type}
- HOOK：需要反直觉案例、冲突性数据
- CASE：需要具体场景、人物故事、决策过程
- MODEL：需要分析框架、因果解释
- ACTION：需要操作步骤、清单
- EXPLAIN：需要深度解读、维度分析

提取 2-3 个关键段落（每个 100-300 字），返回 JSON：
{{
  "summary": "200字以内的内容摘要",
  "key_paragraphs": ["段落1", "段落2", "段落3"],
  "suggested_type": "case/atom/insight"
}}"""

    raw = _call_llm_raw(prompt, temperature=0.3)
    if not raw:
        return {"summary": content[:500], "key_paragraphs": [content[:1000]], "suggested_type": "case"}

    parsed = _parse_llm_json(raw)
    if not parsed:
        return {"summary": content[:500], "key_paragraphs": [content[:1000]], "suggested_type": "case"}

    return parsed


# ============ 素材缺口提示 → 搜索推荐 ============

def generate_gap_search_query(
    topic: str,
    module_type: str,
    gap_description: str
) -> str:
    """生成缺口搜索提示"""
    return f"{topic} {gap_description}"


def search_gap_articles(
    topic: str,
    module_type: str,
    gap_description: str,
    max_results: int = 5
) -> List[Dict]:
    """
    搜索缺口相关文章（Tavily / DuckDuckGo / SerpAPI 三源备份）

    Args:
        topic: 命题
        module_type: 模块类型
        gap_description: 缺口描述
        max_results: 最大结果数

    Returns:
        [{"title": str, "url": str, "snippet": str, "source": str}, ...]
    """
    query = generate_gap_search_query(topic, module_type, gap_description)
    results = []

    # 尝试 Tavily API
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        try:
            import urllib.request
            import urllib.error
            payload = json.dumps({
                "query": query,
                "max_results": max_results,
                "api_key": tavily_key
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")[:200],
                        "source": "tavily"
                    })
        except Exception as e:
            print(f"[Warning] Tavily 搜索失败: {e}", file=sys.stderr)

    # 尝试 DuckDuckGo（备选）
    if len(results) < 3:
        try:
            import urllib.request
            import urllib.error
            import html
            encoded_query = urllib.request.quote(query)
            ddg_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for topic_item in data.get("RelatedTopics", [])[:max_results]:
                    if topic_item.get("Text") and topic_item.get("FirstURL"):
                        results.append({
                            "title": html.unescape(topic_item.get("Text", "")[:100]),
                            "url": topic_item.get("FirstURL", ""),
                            "snippet": topic_item.get("Text", "")[:200],
                            "source": "duckduckgo"
                        })
        except Exception as e:
            print(f"[Warning] DuckDuckGo 搜索失败: {e}", file=sys.stderr)

    # 尝试 SerpAPI（第三备份）
    if len(results) < 3:
        serpapi_key = os.environ.get("SERPAPI_API_KEY")
        if serpapi_key:
            try:
                import urllib.request
                encoded_query = urllib.request.quote(query)
                serp_url = f"https://serpapi.com/search.json?q={encoded_query}&api_key={serpapi_key}&num={max_results}"
                req = urllib.request.Request(serp_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    for item in data.get("organic_results", [])[:max_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", "")[:200],
                            "source": "serpapi"
                        })
            except Exception as e:
                print(f"[Warning] SerpAPI 搜索失败: {e}", file=sys.stderr)

    # 如果都失败，返回 LLM 推荐的搜索词
    if not results:
        results = [{
            "title": "搜索建议",
            "url": "",
            "snippet": f"建议搜索：{query}（请手动搜索相关素材入库）",
            "source": "llm_fallback"
        }]

    return results[:max_results]


# ============ 抓取重试逻辑 (Issue 7) ============

def _is_retryable_scrape_error(scrape_result: Dict) -> bool:
    """判断抓取错误是否可重试"""
    if scrape_result is None:
        return True  # 超时/网络错误可重试
    # 微信反爬错误码
    error_str = str(scrape_result.get("error", "")).lower()
    if any(code in error_str for code in ["403", "451", "blocked", "反爬"]):
        return False
    return True


def _scrape_with_retry(
    url: str,
    format: str = "json",
    max_retries: int = 3,
    initial_delay: float = 1.0
) -> Optional[Dict]:
    """
    带指数退避重试的抓取

    Args:
        url: 文章 URL
        format: 输出格式
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）

    Returns:
        scrape_article 返回结果或 None
    """
    delay = initial_delay
    last_result = None

    for attempt in range(max_retries + 1):
        result = scrape_article(url, format=format)
        last_result = result

        if result is not None:
            # 成功或不可重试的错误
            if not _is_retryable_scrape_error(result):
                return result  # 不可重试的错误，直接返回
            # 有内容算成功
            if result.get("content"):
                return result

        # 判断是否继续重试
        if attempt < max_retries:
            import time
            time.sleep(delay)
            delay *= 2  # 指数退避：1s, 2s, 4s

    return last_result  # 返回最后一次结果（通常是 None）


# ============ 抓取并入库完整流程 ============

def scrape_and_import_material(
    url: str,
    module_type: str,
    topic: str,
    vault_path: Path = None
) -> Dict:
    """
    抓取文章 → 提取关键内容 → 入库 Obsidian

    Args:
        url: 文章 URL
        module_type: 模块类型（决定提取策略）
        topic: 命题（用于关联）
        vault_path: Obsidian vault 路径

    Returns:
        {"status": str, "title": str, "material_type": str, "path": str, "error": str}
    """
    if vault_path is None:
        vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")

    # 1. 抓取（带重试）
    scrape_result = _scrape_with_retry(url, format="json")
    if not scrape_result:
        return {"status": "scrape_failed", "title": "", "material_type": "case", "path": "", "error": "抓取失败"}

    title = scrape_result.get("title", "未命名")
    content = scrape_result.get("content", "")

    # 2. 提取关键内容
    extracted = extract_key_content(scrape_result, module_type)

    # 3. 写入 Obsidian
    obsidian = _get_obsidian_module()
    if not obsidian:
        return {"status": "obsidian_module_not_found", "title": title, "material_type": "case", "path": "", "error": "无法加载 obsidian_knowledge"}

    # 判断素材类型
    suggested_type = extracted.get("suggested_type", "case")
    if module_type == "HOOK":
        subdir = "洞察库"
        material_type = "insight"
    elif suggested_type == "insight":
        subdir = "洞察库"
        material_type = "insight"
    elif suggested_type in ("case", "viewpoint"):
        subdir = "原子库"
        material_type = "atom"
    else:
        subdir = "原子库"
        material_type = "atom"

    # 写入文件（直接写入父目录，方便 scan_vault 递归发现）
    from datetime import datetime
    import re

    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)[:80] or "untitled"
    today = datetime.now().strftime("%Y-%m-%d")

    if material_type == "insight":
        file_path = vault_path / f"40_知识库/{subdir}/{safe_title}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter_lines = ["---",
            f"type: insight",
            "status: active",
            f"topics: [{topic}]",
            f"source_url: {url}",
            f"created: {today}",
            f"updated: {today}",
            "---"]
        body = f"# {title}\n\n## 核心观点\n{extracted.get('summary', '')}\n\n## 关键段落\n" + "\n\n".join(f"- {p}" for p in extracted.get("key_paragraphs", []))
        content_full = "\n".join(frontmatter_lines) + "\n" + body
    else:
        file_path = vault_path / f"40_知识库/{subdir}/{safe_title}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter_lines = ["---",
            "type: atom",
            "subtype: case",
            "status: active",
            f"topics: [{topic}]",
            f"source_url: {url}",
            f"source_note: {title}",
            f"created: {today}",
            f"updated: {today}",
            "---"]
        body = f"# {title}\n\n## 原子内容\n> {extracted.get('summary', '')}\n\n## 来源\n- 链接：[{title}]({url})\n\n## 关键段落\n" + "\n\n".join(f"- {p}" for p in extracted.get("key_paragraphs", []))
        content_full = "\n".join(frontmatter_lines) + "\n" + body

    try:
        file_path.write_text(content_full, encoding="utf-8")
        return {
            "status": "success",
            "title": title,
            "material_type": material_type,
            "path": str(file_path),
            "error": ""
        }
    except Exception as e:
        return {"status": "write_failed", "title": title, "material_type": material_type, "path": "", "error": str(e)}


def scrape_gap_results(search_results: List[Dict], topic: str, vault_path: Path = None) -> List[Dict]:
    """
    对 search_gap_articles 返回的结果列表批量抓取入库

    Args:
        search_results: search_gap_articles 返回的 [{"url": ..., "title": ..., "source": ...}, ...]
        topic: 命题
        vault_path: Obsidian vault 路径

    Returns:
        [{"url": str, "title": str, "status": str, "path": str}, ...]
    """
    imported = []
    for r in search_results:
        url = r.get("url", "")
        if not url:
            continue
        result = scrape_and_import_material(url, "CASE", topic, vault_path)
        imported.append({
            "url": url,
            "title": r.get("title", ""),
            "status": result.get("status", ""),
            "path": result.get("path", "")
        })
    return imported


# ============ 用户手写润色 ============

def polish_user_material(
    user_text: str,
    platform: str,
    material_type: str = "case"
) -> Dict:
    """
    用户手写素材 → AI 润色

    润色原则：
    - 口语化 → 书面化
    - 精简重复内容
    - 前后逻辑连贯
    - 不改变原意、不扩展内容、不改变第一人称视角

    Returns:
        {"polished": str, "original": str, "changes": List[str]}
    """
    platform_hint = "更书面化，适合公众号深度叙事" if platform == "wechat" else "保留口语感，适合小红书"

    prompt = f"""你是内容润色专家。用户写了一{material_type}素材，需要你润色。

原文：
{user_text}

平台：{platform}（{platform_hint}）

润色要求：
1. 口语化→书面化，但保留真实感
2. 精简重复内容
3. 前后逻辑连贯
4. 不改变原意、不扩展内容、不改变第一人称视角
5. 让内容更像"文章"而非"聊天记录"

返回 JSON：
{{
  "polished": "润色后的文本",
  "original": "原文",
  "changes": ["变更描述1", "变更描述2"]
}}"""

    raw = _call_llm_raw(prompt, temperature=0.3)
    if not raw:
        return {"polished": user_text, "original": user_text, "changes": ["润色失败，保留原文"]}

    parsed = _parse_llm_json(raw)
    if not parsed:
        return {"polished": user_text, "original": user_text, "changes": ["润色解析失败，保留原文"]}

    return parsed


# ============ 模块生成 Prompt 构建 ============

def _build_hook_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 HOOK 模块 prompt"""
    platform_hints = {
        "wechat": {
            "role": "思想产品式的开篇",
            "length": "20-30字",
            "function": "制造认知停顿，让人重新思考",
            "style": "反直觉断言/数据冲击/强冲突场景",
            "forbidden": "正确的废话、温和观点"
        },
        "xiaohongshu": {
            "role": "种草安利式的封面",
            "length": "20字以内，可带emoji",
            "function": "制造情绪共鸣，让人想点进去",
            "style": "身份标签/情绪词/悬念/这说的就是我",
            "forbidden": "平铺直叙、无刺激点"
        }
    }
    hints = platform_hints.get(platform, platform_hints["wechat"])

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:200]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 HOOK（开篇钩子）。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

内容目标：{ccos.get('内容目标', '')}
认知张力：{ccos.get('核心认知冲突', '')}

HOOK 要求：
- 角色：{hints['role']}
- 长度：{hints['length']}
- 功能：{hints['function']}
- 写法：{hints['style']}
- 禁止：{hints['forbidden']}
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 1 个 HOOK，直接输出钩子文本，不要解释。"""


def _build_case_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 CASE 模块 prompt"""
    platform_hints = {
        "wechat": {
            "function": "论据，服务论点",
            "depth": "深度叙事，500字以上",
            "structure": "起承转合，决策/心理变化",
            "perspective": "第三或第一均可",
            "key": "细节够真，有时间感"
        },
        "xiaohongshu": {
            "function": "主角，故事即观点",
            "depth": "短平快场景，200-300字",
            "structure": "情绪弧线，高潮前置",
            "perspective": "第一人称亲历感",
            "key": "情绪共鸣强，能让读者代入"
        }
    }
    hints = platform_hints.get(platform, platform_hints["wechat"])

    prev_context = ""
    if previous_modules:
        prevs = [f"- {m.get('模块', m.get('module', 'Unknown'))}：{m.get('draft', '')[:80]}" for m in previous_modules[-2:]]
        prev_context = "前序模块摘要：\n" + "\n".join(prevs) + "\n\n"

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:300]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 CASE（案例）模块。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

{prev_context}
CASE 要求：
- 功能：{hints['function']}
- 深度：{hints['depth']}
- 结构：{hints['structure']}
- 视角：{hints['perspective']}
- 关键：{hints['key']}
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 CASE 模块内容，{'400-600字' if platform == 'wechat' else '200-300字'}，直接输出内容。"""


def _build_explain_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 EXPLAIN 模块 prompt（公众号必有，小红书可选）"""
    if platform == "xiaohongshu":
        return ""  # 小红书 EXPLAIN 可选

    prev_context = ""
    if previous_modules:
        prevs = [f"- {m.get('模块', m.get('module', 'Unknown'))}：{m.get('draft', '')[:80]}" for m in previous_modules[-2:]]
        prev_context = "前序模块摘要：\n" + "\n".join(prevs) + "\n\n"

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:300]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 EXPLAIN（解读分析）模块。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

{prev_context}
EXPLAIN 要求：
- 功能：对案例或观点进行深度解读
- 深度：2-3个维度分析
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 EXPLAIN 模块内容，200-400字，直接输出内容。"""


def _build_model_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 MODEL 模块 prompt"""
    if platform == "xiaohongshu":
        return ""  # 小红书 MODEL 可选

    prev_context = ""
    if previous_modules:
        prevs = [f"- {m.get('模块', m.get('module', 'Unknown'))}：{m.get('draft', '')[:80]}" for m in previous_modules[-2:]]
        prev_context = "前序模块摘要：\n" + "\n".join(prevs) + "\n\n"

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:300]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 MODEL（认知模型）模块。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

{prev_context}
MODEL 要求：
- 功能：提炼可复用的认知模型或框架
- 命名：需要有模型名称，让人能记住
- 结构：完整框架，3层以上
- 关键：让人能记住模型名字
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 MODEL 模块内容，包含模型名称和框架描述，200-400字，直接输出内容。"""


def _build_counter_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 COUNTER 模块 prompt"""
    if platform == "xiaohongshu":
        return ""  # 小红书 COUNTER 可选

    prev_context = ""
    if previous_modules:
        prevs = [f"- {m.get('模块', m.get('module', 'Unknown'))}：{m.get('draft', '')[:80]}" for m in previous_modules[-2:]]
        prev_context = "前序模块摘要：\n" + "\n".join(prevs) + "\n\n"

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:300]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 COUNTER（反直觉观点）模块。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

{prev_context}
COUNTER 要求：
- 功能：制造记忆点，反直觉观点
- 写法：2-3句反直觉内容
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 COUNTER 模块内容，100-200字，直接输出内容。"""


def _build_action_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 ACTION 模块 prompt"""
    platform_hints = {
        "wechat": {"style": "步骤化1-2-3"},
        "xiaohongshu": {"style": "清单化3-5条"}
    }
    hints = platform_hints.get(platform, platform_hints["wechat"])

    prev_context = ""
    if previous_modules:
        prevs = [f"- {m.get('模块', m.get('module', 'Unknown'))}：{m.get('draft', '')[:80]}" for m in previous_modules[-2:]]
        prev_context = "前序模块摘要：\n" + "\n".join(prevs) + "\n\n"

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:300]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 ACTION（行动步骤）模块。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

{prev_context}
ACTION 要求：
- 功能：给出具体行动步骤
- 风格：{hints['style']}
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 ACTION 模块内容，{'150-300字' if platform == 'wechat' else '100-200字'}，直接输出内容。"""


def _build_boundary_prompt(topic: str, ccos: Dict, materials: List[Dict], previous_modules: List[Dict], platform: str) -> str:
    """构建 BOUNDARY 模块 prompt"""
    if platform == "xiaohongshu":
        return ""  # 小红书 BOUNDARY 可选

    prev_context = ""
    if previous_modules:
        prevs = [f"- {m.get('模块', m.get('module', 'Unknown'))}：{m.get('draft', '')[:80]}" for m in previous_modules[-2:]]
        prev_context = "前序模块摘要：\n" + "\n".join(prevs) + "\n\n"

    materials_text = ""
    if materials:
        mats = [f"- {m['name']}: {m.get('content', '')[:300]}" for m in materials[:3]]
        materials_text = "\n参考素材：\n" + "\n".join(mats)

    return f"""你是资深内容策划师。为命题生成{platform}平台的 BOUNDARY（适用边界）模块。

命题：{topic}
{ccos.get('最终动态认知大纲', '')}

{prev_context}
BOUNDARY 要求：
- 功能：说明观点的适用边界，提升高级感
- 写法：1-2句边界条件
- 信息密度：{ccos.get('信息密度要求', '')}
- Anti-AI：{ccos.get('Anti-AI要求', '')}

语言风格：{ccos.get('语言风格', '')}

{materials_text}

请生成 BOUNDARY 模块内容，50-100字，直接输出内容。"""


# ============ 模块生成器映射 ============

MODULE_BUILDERS = {
    "HOOK": _build_hook_prompt,
    "CASE": _build_case_prompt,
    "EXPLAIN": _build_explain_prompt,
    "MODEL": _build_model_prompt,
    "COUNTER": _build_counter_prompt,
    "ACTION": _build_action_prompt,
    "BOUNDARY": _build_boundary_prompt,
}

# 平台模块配置
PLATFORM_MODULE_CONFIG = {
    "wechat": ["HOOK", "CASE", "EXPLAIN", "MODEL", "COUNTER", "ACTION", "BOUNDARY"],
    "xiaohongshu": ["HOOK", "CASE", "ACTION", "BOUNDARY"]
}


# ============ 单模块生成 ============

def generate_single_module(
    topic: str,
    module_type: str,
    ccos_outline: Dict,
    materials: List[Dict],
    previous_modules: List[Dict],
    platform: str,
    rewrite_count: int = 0
) -> Dict:
    """
    生成单个模块内容

    Returns:
        {
            "module": str,
            "draft": str,
            "materials_used": List[str],
            "rewrite_count": int,
            "status": str
        }
    """
    builder = MODULE_BUILDERS.get(module_type)
    if not builder:
        return {"module": module_type, "draft": "", "status": "unsupported_module"}

    # 加载风格偏好并注入
    style_prefs = get_style_preferences(platform)
    style_hints = build_style_hints(style_prefs)

    # 小红书可选模块，若无 builder 则跳过
    prompt = builder(topic, ccos_outline, materials, previous_modules, platform)
    if not prompt:
        return {"module": module_type, "draft": "", "status": "skipped_optional"}

    # 追加风格偏好到 prompt
    if style_hints:
        prompt = prompt + "\n\n" + style_hints

    raw = _call_llm_raw(prompt, temperature=0.6)
    if not raw:
        return {"module": module_type, "draft": "", "status": "llm_failed"}

    # 清理输出
    draft = raw.strip()

    return {
        "module": module_type,
        "draft": draft,
        "materials_used": [m["name"] for m in materials[:3]],
        "rewrite_count": rewrite_count,
        "status": "success"
    }


# ============ 修改记录 ============

_MOD_LOG_PATH = Path(__file__).parent.parent / "data" / "modification_log.json"
_modification_log: List[Dict] = []


def _load_mod_log() -> List[Dict]:
    """从磁盘加载修改记录"""
    if not _MOD_LOG_PATH.exists():
        return []
    try:
        with open(_MOD_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_mod_log(log: List[Dict]) -> None:
    """持久化修改记录到磁盘"""
    _MOD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_MOD_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] 保存修改记录失败: {e}", file=sys.stderr)


def get_modification_log() -> List[Dict]:
    """获取当前内存中的修改记录（惰性加载，只从磁盘读一次）"""
    global _modification_log
    if not _modification_log:
        _modification_log = _load_mod_log()
    return _modification_log


def record_modification(
    module: str,
    original: str,
    modified: str,
    platform: str,
    topic: str,
    user_id: str = "digital_twin"
) -> None:
    """后台静默记录修改（不打断流程）"""
    global _modification_log
    if not _modification_log:
        _modification_log = _load_mod_log()

    entry = {
        "module": module,
        "original": original,
        "modified": modified,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "platform": platform,
        "topic": topic
    }
    _modification_log.append(entry)
    _save_mod_log(_modification_log)


def get_style_preferences(platform: str, min_samples: int = 3) -> Dict[str, Any]:
    """
    从修改记录中学习用户风格偏好

    分析维度：
    - HOOK 风格：长度、用词特点
    - CASE 风格：深度/短平快、叙事视角
    - 共同修改词：高频修改词（可能是用户不喜欢/喜欢替换的词）
    - 删除词 vs 添加词：对比 original vs modified 差异

    Returns:
        {
            "hook_length_avg": float,
            "case_depth": str,  # "long" / "short"
            "case_perspective": str,  # "first" / "third"
            "removed_words": List[str],  # 用户倾向删除的词
            "added_words": List[str],   # 用户倾向添加的词
            "sample_count": int
        }
    """
    global _modification_log
    if not _modification_log:
        _modification_log = _load_mod_log()

    entries = [e for e in _modification_log if e["platform"] == platform]
    if len(entries) < min_samples:
        return {"sample_count": len(entries), "style_summary": ""}

    hook_lengths = []
    case_depths = []
    case_perspectives = []
    removed_words = []
    added_words = []

    for e in entries:
        original = e.get("original", "")
        modified = e.get("modified", "")

        if e["module"] == "HOOK":
            hook_lengths.append(len(modified))
        elif e["module"] == "CASE":
            if len(modified) > 400:
                case_depths.append("long")
            else:
                case_depths.append("short")
            # 简单视角判断：是否包含"我"
            case_perspectives.append("first" if "我" in modified else "third")

        # 词级别差异（简单启发式）
        orig_words = set(original)
        mod_words = set(modified)
        for w in orig_words - mod_words:
            if len(w) > 1:
                removed_words.append(w)
        for w in mod_words - orig_words:
            if len(w) > 1:
                added_words.append(w)

    from collections import Counter
    hook_len_avg = sum(hook_lengths) / len(hook_lengths) if hook_lengths else 0
    case_depth_pref = Counter(case_depths).most_common(1)[0][0] if case_depths else "long"
    case_persp_pref = Counter(case_perspectives).most_common(1)[0][0] if case_perspectives else "first"

    # 高频差异词（至少出现2次）
    removed_counter = Counter(removed_words)
    added_counter = Counter(added_words)
    frequent_removed = [w for w, c in removed_counter.items() if c >= 2]
    frequent_added = [w for w, c in added_counter.items() if c >= 2]

    return {
        "hook_length_avg": round(hook_len_avg, 1),
        "case_depth": case_depth_pref,
        "case_perspective": case_persp_pref,
        "removed_words": frequent_removed[:10],
        "added_words": frequent_added[:10],
        "sample_count": len(entries)
    }


def build_style_hints(prefs: Dict[str, Any]) -> str:
    """将风格偏好转为 prompt hint"""
    if prefs.get("sample_count", 0) == 0:
        return ""
    hints = []
    if prefs.get("hook_length_avg"):
        hints.append(f"HOOK 长度参考：约 {prefs['hook_length_avg']:.0f} 字")
    if prefs.get("case_depth"):
        depth = "深度叙事（500字+）" if prefs["case_depth"] == "long" else "短平快（200-300字）"
        hints.append(f"CASE 深度：{depth}")
    if prefs.get("case_perspective"):
        persp = "第一人称" if prefs["case_perspective"] == "first" else "第三人称"
        hints.append(f"CASE 视角：{persp}")
    if prefs.get("removed_words"):
        removed_str = "、".join(prefs["removed_words"][:5])
        hints.append(f"避免用词：{removed_str}")
    if hints:
        return "用户风格偏好：" + " | ".join(hints) + "。请参考以上偏好。"
    return ""


# ============ 分模块生成流程 ============

def content_generation_workflow(
    topic: str,
    ccos_outline: Dict,
    platform: str,
    vault_path: Path = None,
    auto_scrape: bool = False
) -> Dict:
    """
    Phase 5 核心流程：分模块生成

    Args:
        topic: 命题
        ccos_outline: CCOS 14项输出
        platform: wechat / xiaohongshu
        vault_path: Obsidian vault 路径
        auto_scrape: 是否自动抓取搜索结果入库（默认 False）

    Returns:
        {
            "status": str,
            "topic": str,
            "platform": str,
            "modules": [
                {
                    "module": str,
                    "draft": str,
                    "status": str,
                    "materials_used": List[str],
                    "rewrite_count": int
                },
                ...
            ],
            "material_gaps": {...},
            "full_draft": str,
            "generation_stats": {
                "total_modules": int,
                "success_count": int,
                "skipped_count": int,
                "failed_count": int
            }
        }
    """
    if vault_path is None:
        vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")

    result = {
        "status": "running",
        "topic": topic,
        "platform": platform,
        "modules": [],
        "material_gaps": {},
        "full_draft": "",
        "generation_stats": {}
    }

    # 1. 素材缺口检测
    gaps = detect_material_gaps(topic, ccos_outline, vault_path)
    result["material_gaps"] = gaps

    # 1.5 缺口补货：对有缺口的模块搜索外部素材
    for mod_type, gap_info in gaps.items():
        if gap_info.get("has_gap"):
            gap_desc = gap_info.get("gap_description", "")
            try:
                search_results = search_gap_articles(topic, mod_type, gap_desc, max_results=3)
                gap_info["search_results"] = search_results
                if auto_scrape and search_results:
                    imported = scrape_gap_results(search_results, topic, vault_path)
                    gap_info["imported"] = imported
                else:
                    gap_info["imported"] = []
            except Exception:
                gap_info["search_results"] = []
                gap_info["imported"] = []

    # 2. 确定要生成的模块列表
    modules_to_generate = PLATFORM_MODULE_CONFIG.get(platform, PLATFORM_MODULE_CONFIG["wechat"])
    module_flow = ccos_outline.get("认知模块流", [])

    # 按模块流顺序生成
    generated_modules = []
    previous_modules = []

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for mod_info in module_flow:
        mod_type = mod_info.get("模块", "")
        if mod_type not in modules_to_generate:
            continue

        gap_info = gaps.get(mod_type, {})

        # 召回素材
        materials = recall_materials_by_module(topic, mod_type, vault_path)

        # 追加已抓取入库的素材（Issue 2: 搜索结果应用于生成）
        imported = gap_info.get("imported", [])
        for imp in imported:
            if imp.get("status") == "success" and imp.get("path"):
                # 从已入库文件读取内容作为素材
                try:
                    imp_path = Path(imp["path"])
                    if imp_path.exists():
                        content = imp_path.read_text(encoding="utf-8")
                        # 去掉 frontmatter
                        content = re.sub(r"^---[\s\S]*?---\n", "", content).strip()
                        materials.append({
                            "name": imp.get("title", imp_path.stem),
                            "type": "imported",
                            "content": content[:500],
                            "relevance": 0.9,
                            "quality_score": 8.0,
                            "source": "search_scraped"
                        })
                except Exception:
                    pass
            elif imp.get("status") == "success" and not imp.get("path"):
                # 无文件路径时用搜索结果 snippet
                search_snippets = gap_info.get("search_results", [])
                for snip in search_snippets:
                    if snip.get("url") == imp.get("url"):
                        materials.append({
                            "name": imp.get("title", "导入素材"),
                            "type": "imported",
                            "content": snip.get("snippet", ""),
                            "relevance": 0.85,
                            "quality_score": 7.5,
                            "source": "search_snippet"
                        })
                        break

        # 生成模块
        gen_result = generate_single_module(
            topic, mod_type, ccos_outline,
            materials, previous_modules, platform
        )

        if gen_result["status"] == "success":
            success_count += 1
        elif gen_result["status"] == "skipped_optional":
            skipped_count += 1
        else:
            failed_count += 1

        generated_modules.append({
            **gen_result,
            "gap_detected": gap_info.get("has_gap", False),
            "gap_description": gap_info.get("gap_description", ""),
            "recalled_materials": gap_info.get("materials", [])
        })

        if gen_result["status"] == "success":
            previous_modules.append(gen_result)

    result["modules"] = generated_modules
    result["status"] = "completed"

    # 3. 拼接完整草稿
    full_parts = []
    for m in generated_modules:
        if m["status"] == "success" and m["draft"]:
            full_parts.append(f"【{m['module']}】\n{m['draft']}")

    result["full_draft"] = "\n\n---\n\n".join(full_parts)

    # 4. 统计
    result["generation_stats"] = {
        "total_modules": len(generated_modules),
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count
    }

    return result


# ============ 逐模块交互生成 ============

def interactive_content_generation_workflow(
    topic: str,
    ccos_outline: Dict,
    platform: str,
    vault_path: Path = None
) -> Dict:
    """
    Phase 5.5 逐模块交互生成流程

    流程：
    1. 展示缺口检测结果
    2. 逐模块生成 → 显示草稿 → 用户选择：确认/重写/手动修改
    3. 重写最多 2 次，仍不满意提示手动修改
    4. 确认后进入下一模块
    5. 全部完成后输出完整草稿
    """
    if vault_path is None:
        vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")

    gaps = detect_material_gaps(topic, ccos_outline, vault_path)

    # 缺口补货：对有缺口的模块搜索外部素材
    for mod_type, gap_info in gaps.items():
        if gap_info.get("has_gap"):
            gap_desc = gap_info.get("gap_description", "")
            try:
                search_results = search_gap_articles(topic, mod_type, gap_desc, max_results=3)
                gap_info["search_results"] = search_results
            except Exception:
                gap_info["search_results"] = []

    modules_to_generate = PLATFORM_MODULE_CONFIG.get(platform, PLATFORM_MODULE_CONFIG["wechat"])
    module_flow = ccos_outline.get("认知模块流", [])
    previous_modules = []
    confirmed_modules = []

    print(f"\n{'='*60}")
    print(f"命题：{topic}  |  平台：{platform}")
    print(f"{'='*60}")

    # 展示缺口概览
    print("\n【素材缺口检测】")
    for mod_type in modules_to_generate:
        gap = gaps.get(mod_type, {})
        if gap.get("has_gap"):
            print(f"  ⚠ {mod_type}: {gap.get('gap_description', '缺素材')}")
            # 展示搜索结果
            sr = gap.get("search_results", [])
            if sr:
                for i, r in enumerate(sr[:3], 1):
                    print(f"     [{i}] {r.get('title', '')[:40]} — {r.get('source', '')}")
                print(f"     输入编号抓取入库（如 1 3），或直接回车跳过")
        else:
            print(f"  ✅ {mod_type}: 已召回 {gap.get('recalled_count', 0)} 条素材")

    print("\n【开始逐模块生成】输入 q 随时退出\n")

    for mod_info in module_flow:
        mod_type = mod_info.get("模块", "")
        if mod_type not in modules_to_generate:
            continue

        gap = gaps.get(mod_type, {})
        print(f"\n{'─'*50}")
        print(f"▶ 模块 {mod_type}")
        if gap.get("has_gap"):
            print(f"  缺口：{gap.get('gap_description', '')}")
            # 展示搜索结果供抓取
            sr = gap.get("search_results", [])
            if sr:
                for i, r in enumerate(sr[:3], 1):
                    print(f"     [{i}] {r.get('title', '')[:50]} — {r.get('source', '')}")
                try:
                    import_opt = input("  抓取编号入库（如 1 3）或回车跳过 → ").strip()
                    if import_opt:
                        indices = [int(x) - 1 for x in import_opt.split() if x.isdigit()]
                        to_scrape = [sr[i] for i in indices if 0 <= i < len(sr)]
                        if to_scrape:
                            imported = scrape_gap_results(to_scrape, topic, vault_path)
                            gap["imported"] = imported
                            ok = [x for x in imported if x.get("status") == "success"]
                            print(f"  已入库 {len(ok)} 条")
                except (EOFError, KeyboardInterrupt):
                    pass
        if gap.get("recalled_materials"):
            mats = gap["recalled_materials"]
            print(f"  素材：{', '.join(m['name'] for m in mats[:3])}")

        rewrite_count = 0
        while True:
            materials = recall_materials_by_module(topic, mod_type, vault_path)
            result = generate_single_module(
                topic, mod_type, ccos_outline,
                materials, previous_modules, platform,
                rewrite_count=rewrite_count
            )

            if result["status"] != "success":
                print(f"  [生成失败: {result['status']}]")
                break

            print(f"\n  【{mod_type} 草稿】")
            print(f"  {result['draft'][:500]}")
            if len(result['draft']) > 500:
                print(f"  ...(共 {len(result['draft'])} 字)")

            # 询问用户
            if rewrite_count >= 2:
                print("  [已达最大重写次数，建议手动修改]")
                action = input("  操作：[回车]确认 [r]重写 [e]直接编辑 [p]润色编辑 → ").strip().lower()
            else:
                action = input("  操作：[回车]确认 [r]重写 [e]直接编辑 [p]润色编辑 → ").strip().lower()

            if action == "q":
                print("\n退出。已确认模块：", [m["module"] for m in confirmed_modules])
                return {
                    "status": "interrupted",
                    "topic": topic,
                    "platform": platform,
                    "confirmed_modules": confirmed_modules,
                    "previous_modules": previous_modules
                }
            elif action == "r" and rewrite_count < 2:
                rewrite_count += 1
                continue
            elif action == "p":
                # Issue 5: 润色后编辑
                print("  请输入润色参考内容（空行结束输入，输入的内容将作为润色素材）：")
                lines = []
                while True:
                    try:
                        line = input()
                        if line == "":
                            break
                        lines.append(line)
                    except (EOFError, KeyboardInterrupt):
                        lines = []
                        break
                user_text = "\n".join(lines).strip()
                if user_text:
                    # 以当前草稿为基础，结合用户输入进行润色
                    polished_result = polish_user_material(
                        user_text or result["draft"],
                        platform,
                        mod_type
                    )
                    polished = polished_result.get("polished", result["draft"])
                    print(f"\n  【润色预览】")
                    print(f"  {polished[:500]}")
                    if len(polished) > 500:
                        print(f"  ...(共 {len(polished)} 字)")
                    confirm = input("  [回车]确认润色结果 [e]直接编辑原文 [r]放弃 → ").strip().lower()
                    if confirm == "e":
                        # 切回直接编辑
                        pass  # fall through to edit branch
                    elif confirm == "r":
                        continue  # 放弃此次编辑
                    else:
                        # 确认润色结果
                        record_modification(mod_type, result["draft"], polished, platform, topic)
                        result = {**result, "draft": polished, "status": "manually_edited"}
                        break
                else:
                    print("  未输入内容，跳过")
                    continue

            if action == "e":
                print("  请输入修改后的内容（空行结束输入）：")
                lines = []
                while True:
                    try:
                        line = input()
                        if line == "":
                            break
                        lines.append(line)
                    except (EOFError, KeyboardInterrupt):
                        lines = []
                        break
                edited = "\n".join(lines)
                if edited.strip():
                    record_modification(mod_type, result["draft"], edited, platform, topic)
                    result = {**result, "draft": edited, "status": "manually_edited"}
                break
            else:
                # 确认
                record_modification(mod_type, result["draft"], result["draft"], platform, topic)
                break

        confirmed_modules.append(result)
        if result["status"] in ("success", "manually_edited"):
            previous_modules.append(result)

    # 拼接完整草稿
    full_parts = []
    for m in confirmed_modules:
        if m.get("draft"):
            full_parts.append(f"【{m['module']}】\n{m['draft']}")

    print(f"\n{'='*60}")
    print("【完整草稿】")
    print(f"{'='*60}")
    print("\n\n---\n\n".join(full_parts))

    return {
        "status": "completed",
        "topic": topic,
        "platform": platform,
        "confirmed_modules": confirmed_modules,
        "full_draft": "\n\n---\n\n".join(full_parts)
    }


# ============ 叙事生成策略（Phase 5 重构）============

NARRATIVE_STRATEGIES = {
    "人物线索型": {
        "description": "以多个人物故事为线索，串起全文论点",
        "适合素材": "案例素材丰富（3+个真实人物故事）",
        "核心张力模式": "每个人的故事证明一个侧面，多个故事叠加强化论点",
        "prompt_hint": "用人物故事作为主线，每个案例带出一个认知",
    },
    "观点碰撞型": {
        "description": "正方vs反方观点交锋，最终综合",
        "适合素材": "理论/分析/洞察素材多",
        "核心张力模式": "先对立，后统一，读者在碰撞中被说服",
        "prompt_hint": "制造观点冲突，不同立场对话，最终指向你的真正立场",
    },
    "悬念解密型": {
        "description": "先给反常识结论，再逐层揭示为什么",
        "适合素材": "数据/洞察/反直觉素材多",
        "核心张力模式": "开头扔结论，读者好奇凭什么这么说，然后逐段揭示",
        "prompt_hint": "开头给出令人震惊的结论，后续段落逐步揭示为什么",
    },
    "数据驱动型": {
        "description": "用数据做骨架，穿插叙事解读",
        "适合素材": "统计数据/研究报告多",
        "核心张力模式": "数字制造冲击，解读还原真相",
        "prompt_hint": "用关键数字做段落转折点，每个数据后接深度解读",
    },
    "时间线型": {
        "description": "按时间演变展开，呈现趋势或变化",
        "适合素材": "历史素材/演变过程多",
        "核心张力模式": "从A时刻到B时刻发生了什么，让变化本身说话",
        "prompt_hint": "用时间线做叙事驱动，变化前后对比制造张力",
    },
}


def compute_calibration_boost(
    calibration: Optional[Dict],
    platform: str,
    strategy: str,
    max_boost: float = 5.0
) -> float:
    """根据历史表现为某个策略加分

    Args:
        calibration: feedback_calibration.yaml 加载的配置
        platform: wechat / xiaohongshu
        strategy: 策略名（数据驱动型 / 观点碰撞型等）
        max_boost: 封顶值，避免单策略压制其他

    Returns:
        加分值（正数=推荐，负数=不推荐，0=无影响）
    """
    if not calibration or not calibration.get("by_platform_strategy"):
        return 0.0

    platform_data = calibration.get("by_platform_strategy", {}).get(platform, {})
    if not platform_data:
        return 0.0

    strategy_data = platform_data.get(strategy)
    if not strategy_data:
        return 0.0

    sample_size = strategy_data.get("sample_size", 0)
    if sample_size < 3:
        return 0.0  # 冷启动不调整

    # 计算平台 baseline（所有策略的平均互动率）
    all_engagements = [s["avg_engagement"] for s in platform_data.values() if s.get("sample_size", 0) >= 1]
    avg_engagement = strategy_data.get("avg_engagement", 0)

    if not all_engagements:
        return 0.0

    # 如果只有 1 个策略有数据，用全局默认 baseline 5%
    if len(all_engagements) == 1:
        baseline = 0.05
    else:
        baseline = sum(all_engagements) / len(all_engagements)

    scale = 10
    sample_boost = 1.5 if sample_size >= 10 else 1.0

    boost = (avg_engagement - baseline) * scale * sample_boost
    # 封顶
    boost = max(-max_boost, min(max_boost, boost))
    return round(boost, 3)


def evaluate_narrative_strategy(
    topic: str,
    ccos_outline: Dict,
    materials: List[Dict],
    search_results: List[Dict],
    calibration: Optional[Dict] = None,
    platform: str = "wechat",
) -> Dict:
    """
    综合知识库素材 + 搜索结果，评估并选择最优叙事策略

    评分逻辑：
    - 案例类素材 → 人物线索型 +分
    - 数据类内容 → 数据驱动型 +分
    - 洞察/反直觉 → 悬念解密型 +分
    - 分析/理论 → 观点碰撞型 +分
    - 时间序列 → 时间线型 +分
    - CCOS 主结构加权（故事驱动型→人物线索，认知升级型→观点碰撞/悬念解密等）

    Returns:
        {
            "strategy": str,           # 选中的策略名
            "reasoning": str,           # 选择理由
            "scores": Dict[str, float], # 各策略得分
            "material_assignment": [   # 素材分配表
                {"material": str, "position": str, "proves": str, "strategy_use": str}
            ]
        }
    """
    scores = {name: 0.0 for name in NARRATIVE_STRATEGIES}

    # 统计素材类型分布
    material_texts = []
    for m in materials:
        text = m.get("content", "") or m.get("name", "")
        material_texts.append(text)

    search_texts = []
    for r in search_results:
        text = f"{r.get('title', '')} {r.get('snippet', '')}"
        search_texts.append(text)

    all_text = " ".join(material_texts + search_texts)

    # 关键词评分
    keyword_indicators = {
        "人物线索型": ["故事", "案例", "人物", "他/她", "创业", "转型", "成功", "经历", "真实"],
        "数据驱动型": ["数据", "统计", "比例", "百分比", "%", "研究", "报告", "研究显示", "发现", "分析"],
        "悬念解密型": ["真相", "揭秘", "实际上", "但其实", "不是", "误区", "盲点", "反直觉", "隐藏"],
        "观点碰撞型": ["认为", "观点", "争议", "有人说", "另一方面", "vs", "对比", "正方", "反方"],
        "时间线型": ["过去", "现在", "演变", "趋势", "历程", "发展", "周期", "早年", "至今", "起初", "后来", "回溯"],
    }

    for strategy, keywords in keyword_indicators.items():
        for kw in keywords:
            if kw in all_text:
                scores[strategy] += 1

    # CCOS 主结构加权
    main_structure = ccos_outline.get("主结构", "")
    if "故事驱动" in main_structure:
        scores["人物线索型"] += 2
    elif "认知升级" in main_structure:
        scores["悬念解密型"] += 1
        scores["观点碰撞型"] += 1
    elif "问题拆解" in main_structure:
        scores["数据驱动型"] += 1

    # 内容目标加权
    content_goal = ccos_outline.get("内容目标", "")
    if "认知升级" in content_goal:
        scores["悬念解密型"] += 1
        scores["观点碰撞型"] += 1
    elif "情绪共鸣" in content_goal or "情感" in content_goal:
        scores["人物线索型"] += 2

    # 素材数量阈值（太少时不触发对应策略）
    total_material_score = sum(scores.values())
    if total_material_score < 3:
        # 素材太少时用悬念解密型保守策略
        scores["悬念解密型"] += 1

    # Calibration 加分（Phase 6.1）
    calibration_boosts = {}
    calibration_applied = False
    if calibration:
        calibration_applied = True
        for strategy in scores:
            boost = compute_calibration_boost(calibration, platform, strategy)
            if boost != 0:
                calibration_boosts[strategy] = boost
                scores[strategy] += boost

    best_strategy = max(scores, key=lambda k: scores[k])
    best_score = scores[best_strategy]

    # 生成素材分配表（简版，给预叙事用）
    material_assignment = []
    case_materials = [m for m in materials if "case" in m.get("type", "").lower()]
    data_materials = [m for m in materials if any(kw in m.get("content", "") for kw in ["数据", "统计", "%"])]
    insight_materials = [m for m in materials if "insight" in m.get("type", "").lower()]

    for m in case_materials[:3]:
        material_assignment.append({
            "material": m.get("name", ""),
            "position": "展开段落（案例切入）",
            "proves": "论点：真实存在的转型路径",
            "strategy_use": "人物线索型"
        })
    for m in data_materials[:3]:
        material_assignment.append({
            "material": m.get("name", ""),
            "position": "论证段落（数据支撑）",
            "proves": "论点：数字背后的趋势",
            "strategy_use": "数据驱动型"
        })

    return {
        "strategy": best_strategy,
        "reasoning": f"基于{len(materials)}条知识库素材和{len(search_results)}条搜索结果，{best_strategy}得分最高（{best_score:.1f}分）",
        "scores": scores,
        "material_assignment": material_assignment,
        "strategy_guide": NARRATIVE_STRATEGIES[best_strategy],
        "calibration_applied": calibration_applied,
        "calibration_boosts": calibration_boosts,
    }


def generate_prenarrative(
    topic: str,
    ccos_outline: Dict,
    strategy: Dict,
    materials: List[Dict],
    search_results: List[Dict],
    platform: str,
) -> str:
    """
    生成预叙事（200字叙事策略）
    包含：核心论点 + 主线叙事方向 + 素材分配表 + 各段落核心意图
    """
    # 构建素材上下文
    all_materials_text = "\n".join([
        f"- [{m.get('name', '')}]({m.get('type', '')}): {m.get('content', '')[:200]}"
        for m in materials[:8]
    ])
    search_context = "\n".join([
        f"- {r.get('title', '')}: {r.get('snippet', '')[:150]}"
        for r in search_results[:6]
    ])

    prompt = f"""你是资深内容策划师。基于可用素材，为命题制定叙事策略。

命题：{topic}
CCOS大纲核心：{ccos_outline.get('最终动态认知大纲', '')[:200]}
CCOS主结构：{ccos_outline.get('主结构', '')}
CCOS推进方式：{ccos_outline.get('推进方式', '')}

选定叙事策略：{strategy['strategy']}
策略说明：{strategy['strategy_guide']['description']}
策略理由：{strategy['reasoning']}

知识库素材：
{all_materials_text}

搜索素材：
{search_context}

请生成200字以内的预叙事，包含：
1. 核心论点（一句话，这篇文章最想传达什么）
2. 主线叙事方向（怎么讲这个故事）
3. 素材分配（每个素材用在哪个位置、证明什么）
4. 段落节奏（开头/展开/深化/收尾各用什么情绪）

平台：{platform}（公众号需更深度、更叙事感）
目标字数：2500-3000字

输出格式：直接输出预叙事文本，不要JSON。"""

    raw = _call_llm_raw(prompt, temperature=0.5)
    return raw or ""


def generate_full_draft(
    topic: str,
    ccos_outline: Dict,
    prenarrative: str,
    strategy: Dict,
    materials: List[Dict],
    search_results: List[Dict],
    platform: str,
) -> str:
    """
    一稿生成：完整草稿，不按模块拼接
    输入：预叙事 + 全部素材上下文
    """
    all_materials_text = "\n".join([
        f"- [{m.get('name', '')}]({m.get('type', '')}): {m.get('content', '')[:300]}"
        for m in materials[:10]
    ])
    search_context = "\n".join([
        f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}"
        for r in search_results[:8]
    ])

    platform_hints = {
        "wechat": "公众号深度叙事风格，理性与情绪交织，信息密度高，禁止空洞总结",
        "xiaohongshu": "小红书风格，情绪共鸣强，第一人称，短段落，emoji点缀",
    }
    hints = platform_hints.get(platform, platform_hints["wechat"])

    prompt = f"""你是资深内容策划师。基于预叙事策略，一稿生成完整文章。

命题：{topic}

【预叙事策略】
{prenarrative}

【CCOS大纲】
内容目标：{ccos_outline.get('内容目标', '')}
核心认知冲突：{ccos_outline.get('核心认知冲突', '')}
内容立场：{ccos_outline.get('内容立场', '')}
主结构：{ccos_outline.get('主结构', '')}
推进方式：{ccos_outline.get('推进方式', '')}
语言风格：{ccos_outline.get('语言风格', '')}
Anti-AI要求：{ccos_outline.get('Anti-AI要求', '')}

【可用素材】
知识库：
{all_materials_text}

搜索素材：
{search_context}

【写作要求】
- 平台：{hints}
- **总字数必须达到2500-3000字（严格不低于2500字，不超过3000字）**
- **结构要求：必须写5-7个自然段落，每个段落400-600字**
- **写完后请用数字统计全文字数，如果低于2500字请务必扩充**
- 风格：故事驱动、自然段落，不许用"一、二、三"或"第一章、第二章"这类模块式标题
- 开头要有画面感/场景感，不要平铺直叙
- 素材必须被真正消化后融入叙事，不是堆砌
- 核心张力从头贯穿到尾，不能写着写着忘了论点
- 禁止：同义反复、空洞总结、模板感、套话、数字编号式标题
- 强制：真实细节、具体数字（必须用）、人物心理、时间感

直接输出完整文章正文，不要解释，不要JSON，不要标题。"""

    raw = _call_llm_raw(prompt, temperature=0.6)
    return raw or ""


def revise_paragraph(
    topic: str,
    current_draft: str,
    paragraph_to_revise: str,
    user_modification: str,
    ccos_outline: Dict,
    platform: str,
) -> str:
    """
    段落级修改：用户指出要改某段，LLM在全文上下文下重写那一段

    Args:
        current_draft: 完整草稿（用于上下文）
        paragraph_to_revise: 用户指定要改的段落内容
        user_modification: 用户的修改方向/要求
    """
    prompt = f"""你是资深内容编辑。用户要求修改文章的某个段落。

命题：{topic}
CCOS核心立场：{ccos_outline.get('内容立场', '')}
CCOS推进方式：{ccos_outline.get('推进方式', '')}

【完整文章草稿】
{current_draft}

【用户要求修改的段落】
{paragraph_to_revise}

【用户的修改方向】
{user_modification}

要求：
1. 在全文上下文中重写这个段落
2. 保持与文章其他部分的连贯性（论点一致、情绪连贯）
3. 不要破坏文章的叙事主线
4. 输出：只输出修改后的段落内容（不要全文）

直接输出修改后的段落，不要解释。"""

    raw = _call_llm_raw(prompt, temperature=0.4)
    return raw or paragraph_to_revise


def check_ccos_structure(ccos_outline: Dict, article_text: str) -> Dict:
    """
    CCOS 结构预检查：生成前验证大纲是否完整，生成后检查文章覆盖了多少模块
    这里用于生成前的预检查
    """
    required_modules = ["HOOK", "CASE", "COUNTER", "ACTION"]
    if ccos_outline.get("主结构") == "认知升级型":
        required_modules.append("MODEL")
    if ccos_outline.get("主结构") == "问题拆解型":
        required_modules.append("EXPLAIN")

    module_flow = ccos_outline.get("认知模块流", [])
    defined_modules = [m.get("模块", "") for m in module_flow]

    missing = [m for m in required_modules if m not in defined_modules]

    return {
        "ccos_complete": len(missing) == 0,
        "defined_modules": defined_modules,
        "required_but_missing": missing,
        "warning": f"建议在生成前补充缺失模块：{', '.join(missing)}" if missing else "",
    }


def narrative_generation_workflow(
    topic: str,
    ccos_outline: Dict,
    platform: str,
    vault_path: Path = None,
    search_results: List[Dict] = None,
    auto_scrape: bool = False,
    calibration: Optional[Dict] = None,
) -> Dict:
    """
    Phase 5 重构后的叙事生成流程

    流程：
    1. CCOS 预检查（结构是否完整）
    2. 收集素材（知识库召回 + 搜索结果）
    3. 策略评估（综合素材类型选择最优叙事策略）
    4. 预叙事生成（叙事策略文本化）
    5. 一稿生成（完整草稿，2500-3000字）
    6. 返回草稿供段落级修改

    Returns:
        {
            "status": str,
            "topic": str,
            "platform": str,
            "prenarrative": str,
            "strategy": {...},
            "full_draft": str,
            "word_count": int,
            "material_gaps": Dict,
            "materials_used": List[str],
        }
    """
    if vault_path is None:
        vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")
    if search_results is None:
        search_results = []

    result = {
        "status": "running",
        "topic": topic,
        "platform": platform,
        "prenarrative": "",
        "strategy": {},
        "full_draft": "",
        "word_count": 0,
        "material_gaps": {},
        "materials_used": [],
    }

    # Step 1: CCOS 预检查
    ccos_check = check_ccos_structure(ccos_outline, "")
    result["ccos_check"] = ccos_check
    if ccos_check.get("warning"):
        print(f"[CCOS Precheck] {ccos_check['warning']}", file=sys.stderr)

    # Step 2: 素材收集
    gaps = detect_material_gaps(topic, ccos_outline, vault_path)
    result["material_gaps"] = gaps

    # 合并搜索结果到素材池
    all_materials = []
    for mod_type, gap_info in gaps.items():
        all_materials.extend(gap_info.get("materials", []))
        # 如果有搜索结果，加入模拟素材（用于策略评估）
        if gap_info.get("search_results"):
            for sr in gap_info["search_results"][:3]:
                all_materials.append({
                    "name": sr.get("title", ""),
                    "type": "search_result",
                    "content": sr.get("snippet", ""),
                    "url": sr.get("url", ""),
                })
    # 添加传入的搜索结果
    for sr in search_results:
        all_materials.append({
            "name": sr.get("title", ""),
            "type": "search_result",
            "content": sr.get("snippet", ""),
            "url": sr.get("url", ""),
        })

    result["materials_used"] = [m.get("name", "") for m in all_materials[:15]]

    # Step 3: 策略评估（Phase 6.1 接入 calibration）
    strategy = evaluate_narrative_strategy(
        topic, ccos_outline, all_materials, search_results,
        calibration=calibration, platform=platform
    )
    result["strategy"] = strategy
    print(f"[Narrative] 策略: {strategy['strategy']} (得分: {strategy['scores']})", file=sys.stderr)
    if strategy.get("calibration_boosts"):
        print(f"[Calibration] 历史表现加权: {strategy['calibration_boosts']}", file=sys.stderr)

    # Step 4: 预叙事生成
    prenarrative = generate_prenarrative(
        topic, ccos_outline, strategy, all_materials, search_results, platform
    )
    result["prenarrative"] = prenarrative

    # Step 5: 一稿生成
    full_draft = generate_full_draft(
        topic, ccos_outline, prenarrative, strategy, all_materials, search_results, platform
    )

    if not full_draft:
        result["status"] = "llm_failed"
        return result

    # Step 5b: 字数校验与自动扩充
    word_count = len(full_draft)
    print(f"[字数] 草稿 {word_count} 字", file=sys.stderr)
    if word_count < 2500:
        print(f"[字数] 不足2500字，正在进行扩充...", file=sys.stderr)
        expansion_prompt = f"""你是资深内容策划师。下面这篇文章需要扩充到2500-3000字。

当前字数：{word_count}字
目标字数：2500-3000字

扩写要求：
- 在现有内容基础上扩充，不要删除已有内容
- 增加更多具体细节：人物对话、场景描写、心理活动、数据支撑
- 每个段落至少扩充200-300字
- 保持原有的叙事风格和核心论点
- 不要添加新的模块式标题

【原文】
{full_draft}

直接输出扩充后的完整文章，不要解释，不要JSON。"""

        expanded = _call_llm_raw(expansion_prompt, temperature=0.6)
        if expanded and len(expanded) > word_count:
            full_draft = expanded
            word_count = len(full_draft)
            print(f"[字数] 扩充后 {word_count} 字", file=sys.stderr)

    result["full_draft"] = full_draft
    result["word_count"] = word_count
    result["status"] = "completed"

    return result


# ============ 交互式叙事生成（CLI使用）============

def interactive_narrative_workflow(
    topic: str,
    ccos_outline: Dict,
    platform: str,
    vault_path: Path = None,
    calibration: Optional[Dict] = None,
) -> Dict:
    """
    交互式叙事生成流程
    展示预叙事 → 生成一稿 → 用户选择段落修改 → 最终确认
    """
    if vault_path is None:
        vault_path = Path(r"D:\软件\obsidian笔记\内容素材库")

    print(f"\n{'='*60}")
    print(f"叙事生成 | 命题：{topic}")
    print(f"{'='*60}")

    # 1. 缺口检测 + 搜索补货
    gaps = detect_material_gaps(topic, ccos_outline, vault_path)
    search_results_all = []
    for mod_type, gap_info in gaps.items():
        if gap_info.get("has_gap"):
            sr = search_gap_articles(topic, mod_type, gap_info.get("gap_description", ""), max_results=3)
            gap_info["search_results"] = sr
            search_results_all.extend(sr)

    # 2. 策略评估
    all_materials = []
    for gap_info in gaps.values():
        all_materials.extend(gap_info.get("materials", []))
        for sr in gap_info.get("search_results", []):
            all_materials.append({
                "name": sr.get("title", ""),
                "type": "search_result",
                "content": sr.get("snippet", ""),
            })

    strategy = evaluate_narrative_strategy(
        topic, ccos_outline, all_materials, search_results_all,
        calibration=calibration, platform=platform
    )
    print(f"\n【策略评估】{strategy['strategy']} — {strategy['reasoning']}")
    scores_str = ", ".join([f"{k}:{v}" for k, v in strategy['scores'].items()])
    print(f"  得分：{scores_str}")

    # 3. 预叙事
    prenarrative = generate_prenarrative(
        topic, ccos_outline, strategy, all_materials, search_results_all, platform
    )
    if prenarrative:
        print(f"\n【预叙事】")
        print(prenarrative[:300])
        if len(prenarrative) > 300:
            print("  ...")

        confirm = input("\n预叙事确认 → [回车]继续生成 [e]编辑预叙事 → ").strip().lower()
        if confirm == "e":
            print("  请输入修改后的预叙事（空行结束）：")
            lines = []
            while True:
                try:
                    line = input()
                    if line == "":
                        break
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            if lines:
                prenarrative = "\n".join(lines)

    # 4. 一稿生成
    print(f"\n【生成中...】（基于预叙事 + {len(all_materials)} 条素材）")
    full_draft = generate_full_draft(
        topic, ccos_outline, prenarrative, strategy, all_materials, search_results_all, platform
    )

    if not full_draft:
        print("[Error] 生成失败")
        return {"status": "llm_failed", "topic": topic}

    print(f"  草稿完成，共 {len(full_draft)} 字")

    # 5. 段落级修改
    paragraphs = split_into_paragraphs(full_draft)
    confirmed_paragraphs = []

    for i, para in enumerate(paragraphs, 1):
        print(f"\n{'─'*40}")
        print(f"段落 {i}/{len(paragraphs)}")
        print(f"{'─'*40}")
        print(para[:300])
        if len(para) > 300:
            print("  ...")

        action = input("  操作：[回车]确认 [r]重写 [e]直接编辑 → ").strip().lower()

        if action == "r":
            # 重写这一段
            revised = revise_paragraph(
                topic, full_draft, para,
                "重写这段，保持全文连贯性",
                ccos_outline, platform
            )
            confirmed_paragraphs.append(revised)
            full_draft = full_draft.replace(para, revised, 1)
        elif action == "e":
            print("  请输入修改后的段落（空行结束）：")
            lines = []
            while True:
                try:
                    line = input()
                    if line == "":
                        break
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            edited = "\n".join(lines)
            if edited:
                confirmed_paragraphs.append(edited)
                full_draft = full_draft.replace(para, edited, 1)
            else:
                confirmed_paragraphs.append(para)
        else:
            confirmed_paragraphs.append(para)

    result_draft = "\n\n".join(confirmed_paragraphs)

    print(f"\n{'='*60}")
    print("【最终草稿】")
    print(f"{'='*60}")
    print(result_draft)

    return {
        "status": "completed",
        "topic": topic,
        "platform": platform,
        "prenarrative": prenarrative,
        "strategy": strategy.get("strategy", ""),
        "full_draft": result_draft,
        "word_count": len(result_draft),
    }


def split_into_paragraphs(text: str) -> List[str]:
    """将文章按空行分割为段落"""
    parts = text.split("\n\n")
    return [p.strip() for p in parts if p.strip()]


# ============ v2 新增：写作框架改造（Commit 6-9）============

# 5种文章原型（卡兹克 khazix-writer）
ARTICLE_ARCHETYPES = {
    "调查实验型": {
        "name": "调查实验型",
        "description": "通过调查、实验或数据收集来验证/推翻一个假设",
        "typical_modules": ["HOOK", "CASE", "EXPLAIN", "EVIDENCE", "ACTION"],
        "best_for": "有数据/实验支撑的选题，需要展示过程",
        "reader_value": "跟着作者一起发现真相的过程感"
    },
    "产品体验型": {
        "name": "产品体验型",
        "description": "深度体验某个产品/服务，给出真实评价和洞察",
        "typical_modules": ["HOOK", "CASE", "EXPLAIN", "BOUNDARY", "ACTION"],
        "best_for": "产品测评/工具推荐/服务对比",
        "reader_value": "省去自己试错的时间成本"
    },
    "现象解读型": {
        "name": "现象解读型",
        "description": "对某个社会/行业现象进行多维度解读，揭示本质",
        "typical_modules": ["HOOK", "CASE", "EXPLAIN", "MODEL", "COUNTER", "ACTION"],
        "best_for": "社会现象/行业趋势/认知升级类选题",
        "reader_value": "看到现象背后的本质，认知升级"
    },
    "工具分享型": {
        "name": "工具分享型",
        "description": "分享好用工具/方法/资源，注重实操性",
        "typical_modules": ["HOOK", "CASE", "MODEL", "ACTION"],
        "best_for": "效率工具/工作方法/资源合集",
        "reader_value": "直接可用的方法论/工具清单"
    },
    "方法论分享型": {
        "name": "方法论分享型",
        "description": "分享自己验证过的做事方法/思维框架",
        "typical_modules": ["HOOK", "CASE", "EXPLAIN", "MODEL", "ACTION", "BOUNDARY"],
        "best_for": "个人经验总结/方法论提炼/框架分享",
        "reader_value": "可复用的思维框架和行动指南"
    },
}


# ============ v2.1: 写作前真实经历询问 ============

def prompt_real_experience(
    topic: str,
    ccos_outline: Dict,
    platform: str
) -> Dict:
    """
    Gap分析后、预叙事前，询问用户是否有真实经历可补充

    Returns:
        {"prompt": str, "question_areas": List[str]}
    """
    platform_hint = "公众号深度叙事" if platform == "wechat" else "小红书生活化分享"

    prompt = f"""你是资深内容策划师。为以下命题设计"真实经历询问"文案。

命题：{topic}
平台：{platform}（{platform_hint}）
核心冲突：{ccos_outline.get('核心认知冲突', '')}
内容立场：{ccos_outline.get('内容立场', '')}

请设计一个问题，引导用户回忆和分享相关的真实经历。要求：
1. 语气自然，像朋友聊天
2. 引导用户回忆具体场景，而非抽象观点
3. 给出2-3个具体的问题方向（如：自己经历的/朋友经历的/观察到的）

返回JSON：
{{
  "prompt": "询问文案（50-100字）",
  "question_areas": ["方向1", "方向2", "方向3"]
}}"""

    raw = _call_llm_raw(prompt, temperature=0.5)
    if raw:
        parsed = _parse_llm_json(raw)
        if parsed:
            return parsed

    return {
        "prompt": f"在开始写'{topic}'之前，你有什么相关的真实经历或观察吗？可以是自己的故事、朋友的案例、或者你看到的真实事件。这些会让文章更有说服力。",
        "question_areas": ["个人亲身经历", "朋友/同事的案例", "观察到的社会现象"]
    }


# ============ v2.2: 质量自检 L1-L4 + AI腔识别 ============

# L1 硬性规则：禁用词列表（自动拦截，不依赖 LLM）
QUALITY_L1_BANNED_WORDS = [
    "赋能", "抓手", "闭环", "拉通", "对齐", "落地", "打法", "底层逻辑",
    "降本增效", "颗粒度", "组合拳", "颠覆性", "前所未有的",
]

QUALITY_L1_BANNED_PATTERNS = [
    (r"在.{0,5}的今天", "AI腔：'在...的今天'句式"),
    (r"众所周知", "AI腔：'众所周知'"),
    (r"总而言之", "AI腔：'总而言之'式结尾"),
    (r"不仅.{0,10}而且", "排比句式（允许但标记）"),
]


def quality_check(article_text: str, platform: str) -> Dict:
    """
    写作后质量自检：L1自动拦截 + L2-L4 + AI腔 LLM审核

    Args:
        article_text: 文章全文
        platform: wechat / xiaohongshu

    Returns:
        {
            "status": "pass" | "issues_found" | "check_failed",
            "platform": str,
            "issues": [{"level": "L1"|"L2"|"L3"|"L4", "type": str, "location": str, "suggestion": str, "severity": "error"|"warning"}],
            "ai_mannerisms": [{"type": str, "count": int, "examples": [str]}],
            "score": float  # 0-100
        }
    """
    if not article_text or len(article_text) < 50:
        return {
            "status": "check_failed",
            "platform": platform,
            "issues": [{"level": "L1", "type": "内容不足", "location": "全文", "suggestion": "文章少于50字，无法进行质量检查", "severity": "error"}],
            "ai_mannerisms": [],
            "score": 0
        }

    issues = []

    # L1: 硬性规则自动拦截
    for word in QUALITY_L1_BANNED_WORDS:
        count = article_text.count(word)
        if count > 0:
            issues.append({
                "level": "L1",
                "type": "禁用词",
                "location": f"正文（出现{count}次）",
                "suggestion": f"删除或替换'{word}'",
                "severity": "error"
            })

    for pattern, desc in QUALITY_L1_BANNED_PATTERNS:
        matches = re.findall(pattern, article_text)
        if matches:
            severity = "warning" if "允许但标记" in desc else "error"
            issues.append({
                "level": "L1",
                "type": "AI句式",
                "location": f"正文（出现{len(matches)}次）",
                "suggestion": desc,
                "severity": severity
            })

    # L2-L4 + AI腔：LLM 审核
    prompt = f"""你是资深内容审校专家。对以下文章进行L2-L4质量审核。

【审核标准】
L2 风格层：
- AI腔（句式工整对称、排比滥用、过渡词套路化）
- 书面腔（过于正式，缺少口语节奏）
- 模板感（像填空模板，每个段落结构一样）

L3 内容层：
- 逻辑漏洞（前后矛盾、因果不成立）
- 数据无来源（引用了数据但未注明出处）
- 事实存疑（声称的事实需要验证）

L4 活人感：
- 是否有真实细节（时间/地点/人物/数字）
- 是否有情绪起伏（不是从头到尾一个调）
- 是否像真人写的（有判断、有偏见、有不确定性）

平台：{platform}

【文章】
{article_text[:3000]}

返回JSON（仅JSON，不要解释）：
{{
  "issues": [
    {{"level": "L2", "type": "AI腔", "location": "第X段", "suggestion": "...", "severity": "warning"}},
    {{"level": "L3", "type": "数据无来源", "location": "第X段", "suggestion": "...", "severity": "warning"}},
    {{"level": "L4", "type": "缺少真实细节", "location": "全文", "suggestion": "...", "severity": "warning"}}
  ],
  "ai_mannerisms": [
    {{"type": "排比句", "count": 3, "examples": ["不仅...而且..."]}}
  ],
  "score": 85
}}"""

    raw = _call_llm_raw(prompt, temperature=0.3)
    if raw:
        parsed = _parse_llm_json(raw)
        if parsed:
            llm_issues = parsed.get("issues", [])
            for issue in llm_issues:
                if "level" not in issue:
                    issue["level"] = "L2"
                if "severity" not in issue:
                    issue["severity"] = "warning"
                if "location" not in issue:
                    issue["location"] = "全文"
            issues.extend(llm_issues)

            ai_mannerisms = parsed.get("ai_mannerisms", [])
            score = parsed.get("score", 70)

            l1_error_count = sum(1 for i in issues if i["severity"] == "error")
            l1_deduction = l1_error_count * 10
            score = max(0, min(100, score - l1_deduction))

            status = "issues_found" if issues else "pass"
            if any(i["severity"] == "error" for i in issues):
                status = "issues_found"

            return {
                "status": status,
                "platform": platform,
                "issues": issues,
                "ai_mannerisms": ai_mannerisms,
                "score": score
            }

    return {
        "status": "check_failed",
        "platform": platform,
        "issues": issues,
        "ai_mannerisms": [],
        "score": 0
    }


# ============ v2.7: 三遍审校完整交互（花叔）============

def proofreading_flow(article_text: str, platform: str) -> Dict:
    """
    花叔三遍审校流程：

    第一遍（L1-L2）：内容+风格审校
    第二遍（L3）：逻辑+事实审校
    第三遍（L4）：活人感审校

    全程交互：列出问题 → 用户选择接受/拒绝 → 增量修改 → 实时保存

    Args:
        article_text: 文章全文
        platform: wechat / xiaohongshu

    Returns:
        {
            "status": "completed",
            "confirmed_issues": [...],  # 用户确认的问题
            "rejected_issues": [...],   # 用户拒绝的问题
            "final_article": str,       # 最终文章
            "total_issues": int
        }
    """
    print("\n━━━ 花叔三遍审校 ━━━", file=sys.stderr)
    print("第1遍: 内容+风格审校", file=sys.stderr)

    # 第一遍：复用 quality_check 的 L1 检测逻辑
    first_pass_issues = []
    for word in QUALITY_L1_BANNED_WORDS:
        count = article_text.count(word)
        if count > 0:
            first_pass_issues.append({
                "level": "L1",
                "type": "禁用词",
                "location": f"正文（出现{count}次）",
                "suggestion": f"删除或替换'{word}'",
                "severity": "error",
                "original_text": word
            })

    for pattern, desc in QUALITY_L1_BANNED_PATTERNS:
        matches = re.findall(pattern, article_text)
        if matches:
            severity = "warning" if "允许但标记" in desc else "error"
            first_pass_issues.append({
                "level": "L1",
                "type": "AI句式",
                "location": f"正文（出现{len(matches)}次）",
                "suggestion": desc,
                "severity": severity,
                "matched_text": matches[0]
            })

    # LLM 风格审校
    style_prompt = f"""你是资深内容审校师。对以下文章进行风格审校，检测AI腔和套话。

文章：
{article_text[:3000]}

检测重点：
- AI腔（句式工整对称、排比滥用、过渡词套路化）
- 模板感（像填空模板）
- 书面腔（过于正式，缺少口语节奏）

返回JSON（仅JSON）：
{{"issues": [
  {{"type": "AI腔/套话/模板感", "location": "第X段", "suggestion": "..."}}
]}}"""

    raw = _call_llm_raw(style_prompt, temperature=0.3)
    if raw:
        parsed = _parse_llm_json(raw)
        if parsed:
            for issue in parsed.get("issues", []):
                issue["level"] = "L2"
                issue["severity"] = "warning"
                first_pass_issues.append(issue)

    # 第二遍：L3 逻辑+事实
    print("第2遍: 逻辑+事实审校", file=sys.stderr)
    second_pass_issues = []
    fact_prompt = f"""你是资深内容审校师。对以下文章进行事实和逻辑审校。

文章：
{article_text[:3000]}

检测重点：
- 数据无来源（引用了数据但未注明出处）
- 逻辑漏洞（前后矛盾、因果不成立）
- 事实存疑（声称的事实需要验证）

返回JSON（仅JSON）：
{{"issues": [
  {{"type": "数据无来源/逻辑漏洞/事实存疑", "location": "第X段", "suggestion": "..."}}
]}}"""

    raw2 = _call_llm_raw(fact_prompt, temperature=0.3)
    if raw2:
        parsed2 = _parse_llm_json(raw2)
        if parsed2:
            for issue in parsed2.get("issues", []):
                issue["level"] = "L3"
                issue["severity"] = "warning"
                second_pass_issues.append(issue)

    # 第三遍：L4 活人感
    print("第3遍: 活人感审校", file=sys.stderr)
    third_pass_issues = []
    life_prompt = f"""你是资深内容审校师。对以下文章进行活人感审校。

文章：
{article_text[:3000]}

检测重点：
- 是否有真实细节（时间/地点/人物/数字）
- 是否有情绪起伏（不是从头到尾一个调）
- 是否像真人写的（有判断、有偏见、有不确定性）

返回JSON（仅JSON）：
{{"issues": [
  {{"type": "缺少真实细节/情绪平淡/不像真人写", "location": "第X段", "suggestion": "..."}}
]}}"""

    raw3 = _call_llm_raw(life_prompt, temperature=0.3)
    if raw3:
        parsed3 = _parse_llm_json(raw3)
        if parsed3:
            for issue in parsed3.get("issues", []):
                issue["level"] = "L4"
                issue["severity"] = "warning"
                third_pass_issues.append(issue)

    all_issues = first_pass_issues + second_pass_issues + third_pass_issues
    confirmed = []
    rejected = []

    # 交互确认
    print(f"\n发现 {len(all_issues)} 个问题：\n", file=sys.stderr)
    for i, issue in enumerate(all_issues, 1):
        print(f"  [{i}] {issue.get('level', '')} {issue.get('type', '')}: {issue.get('suggestion', '')}", file=sys.stderr)
        print(f"      位置: {issue.get('location', '')}", file=sys.stderr)

    print("\n是否逐个确认修改？（输入空行全部确认，q 跳过）：", file=sys.stderr)
    try:
        choice = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "y"

    if choice.lower() == "q":
        return {
            "status": "skipped",
            "confirmed_issues": [],
            "rejected_issues": all_issues,
            "final_article": article_text,
            "total_issues": len(all_issues)
        }

    if choice == "":
        # 空行 = 全部确认
        confirmed = all_issues
    else:
        # 逐个确认
        confirmed = all_issues

    # 应用确认的修改（生成修改后版本）
    final_article = article_text
    if confirmed:
        modifications = [f"第{i+1}项: {issue.get('suggestion', '')}" for i, issue in enumerate(confirmed)]
        revise_prompt = f"""你是资深内容编辑。用户已确认以下 {len(confirmed)} 项修改，请逐一应用到文章。

原文：
{article_text[:4000]}

确认的修改：
{chr(10).join(modifications)}

要求：
1. 逐一应用每项修改
2. 保持文章整体风格一致
3. 不要添加新内容，只修改确认的问题点

直接输出修改后的完整文章，不要解释。"""

        raw_revise = _call_llm_raw(revise_prompt, temperature=0.3)
        if raw_revise:
            final_article = raw_revise.strip()

    return {
        "status": "completed",
        "confirmed_issues": confirmed,
        "rejected_issues": rejected,
        "accepted_count": len(confirmed),
        "rejected_count": len(rejected),
        "final_article": final_article,
        "total_issues": len(all_issues),
        "pass_1_issues": len(first_pass_issues),
        "pass_2_issues": len(second_pass_issues),
        "pass_3_issues": len(third_pass_issues)
    }


# ============ v2.3: 工具箱架构 — 按话题动态选原型+模块 ============

def select_article_architecture(
    topic: str,
    ccos_outline: Dict,
    platform: str
) -> Dict:
    """
    工具箱模式：根据话题内容动态选择合适的文章原型和模块组合

    Returns:
        {
            "archetype": str,
            "modules": [str],
            "module_flow": [{"module": str, "purpose": str, "estimated_words": int}],
            "reasoning": str
        }
    """
    # 先基于规则做初步选择
    content_goal = ccos_outline.get("内容目标", "")
    main_structure = ccos_outline.get("主结构", "")
    combined = f"{content_goal} {main_structure}"

    rule_scores = {}
    if any(kw in combined for kw in ["认知升级", "现象", "解读", "趋势"]):
        rule_scores["现象解读型"] = 2
    if any(kw in combined for kw in ["方法", "工具", "实操", "步骤"]):
        rule_scores["工具分享型"] = 1
        rule_scores["方法论分享型"] = 1
    if any(kw in combined for kw in ["实验", "调查", "数据驱动", "验证"]):
        rule_scores["调查实验型"] = 2
    if any(kw in combined for kw in ["体验", "测评", "产品", "试用"]):
        rule_scores["产品体验型"] = 2
    if any(kw in combined for kw in ["故事", "案例", "人物"]):
        rule_scores["现象解读型"] = rule_scores.get("现象解读型", 0) + 1

    if not rule_scores:
        rule_scores["现象解读型"] = 1

    # LLM 增强选择
    prompt = f"""你是资深内容架构师。为以下命题选择最合适的文章原型和模块组合。

命题：{topic}
内容目标：{content_goal}
主结构：{main_structure}
平台：{platform}

可选原型：
{json.dumps({k: {"name": v["name"], "description": v["description"], "typical_modules": v["typical_modules"]} for k, v in ARTICLE_ARCHETYPES.items()}, ensure_ascii=False, indent=2)}

规则初步评分：{json.dumps(rule_scores, ensure_ascii=False)}

要求：
1. 选择1个最合适的原型
2. 从原型的 typical_modules 中选 4-6 个模块
3. 为每个模块写一行 purpose（这个模块在这篇文章里做什么）
4. 为每个模块估算字数

返回JSON：
{{
  "archetype": "原型名",
  "modules": ["HOOK", "CASE", ...],
  "module_flow": [
    {{"module": "HOOK", "purpose": "制造认知冲突", "estimated_words": 200}},
    ...
  ],
  "reasoning": "为什么选这个原型"
}}"""

    raw = _call_llm_raw(prompt, temperature=0.4)
    if raw:
        parsed = _parse_llm_json(raw)
        if parsed and parsed.get("archetype") in ARTICLE_ARCHETYPES:
            arch = ARTICLE_ARCHETYPES[parsed["archetype"]]
            return {
                "archetype": parsed["archetype"],
                "modules": parsed.get("modules", arch["typical_modules"]),
                "module_flow": parsed.get("module_flow", []),
                "reasoning": parsed.get("reasoning", "")
            }

    # Fallback: 用得分最高的原型
    best_arch = max(rule_scores, key=lambda k: rule_scores[k])
    arch = ARTICLE_ARCHETYPES[best_arch]
    default_modules = arch["typical_modules"][:5] if platform == "xiaohongshu" else arch["typical_modules"][:6]
    return {
        "archetype": best_arch,
        "modules": default_modules,
        "module_flow": [{"module": m, "purpose": "", "estimated_words": 300} for m in default_modules],
        "reasoning": f"基于规则选择{best_arch}"
    }


# ============ v2.4: 并行双引擎搜索 ============

def search_parallel(query: str, max_results: int = 5) -> List[Dict]:
    """
    Tavily + SerpAPI(engine=baidu) 同query并行，合并去重，DDG兜底

    Returns:
        [{"title": str, "url": str, "snippet": str, "source": str}, ...]
    """
    import concurrent.futures
    import urllib.request
    import urllib.error

    results = []
    seen_urls = set()

    def _search_tavily(q: str, n: int) -> List[Dict]:
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            return []
        try:
            payload = json.dumps({
                "query": q, "max_results": n, "api_key": tavily_key
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:200],
                    "source": "tavily"
                }
                for item in data.get("results", [])[:n]
            ]
        except Exception:
            return []

    def _search_serpapi_baidu(q: str, n: int) -> List[Dict]:
        serpapi_key = os.environ.get("SERPAPI_API_KEY")
        if not serpapi_key:
            return []
        try:
            encoded_q = urllib.request.quote(q)
            url = f"https://serpapi.com/search.json?q={encoded_q}&api_key={serpapi_key}&engine=baidu&num={n}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", "")[:200],
                    "source": "serpapi_baidu"
                }
                for item in data.get("organic_results", [])[:n]
            ]
        except Exception:
            return []

    def _search_ddg(q: str, n: int) -> List[Dict]:
        try:
            import html
            encoded_q = urllib.request.quote(q)
            ddg_url = f"https://api.duckduckgo.com/?q={encoded_q}&format=json&no_html=1"
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results_list = []
            for topic_item in data.get("RelatedTopics", [])[:n]:
                if topic_item.get("Text") and topic_item.get("FirstURL"):
                    results_list.append({
                        "title": html.unescape(topic_item.get("Text", "")[:100]),
                        "url": topic_item.get("FirstURL", ""),
                        "snippet": topic_item.get("Text", "")[:200],
                        "source": "duckduckgo"
                    })
            return results_list
        except Exception:
            return []

    # 并行调用 Tavily + SerpAPI百度
    tavily_results = []
    serpapi_results = []

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_tavily = executor.submit(_search_tavily, query, max_results)
            future_serpapi = executor.submit(_search_serpapi_baidu, query, max_results)
            tavily_results = future_tavily.result(timeout=20) or []
            serpapi_results = future_serpapi.result(timeout=20) or []
    except Exception:
        pass

    # 合并去重（按 URL）
    for r in tavily_results + serpapi_results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            results.append(r)

    # DDG 兜底
    if len(results) < 2:
        ddg_results = _search_ddg(query, max_results)
        for r in ddg_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(r)

    return results[:max_results]


# ============ v2.5: crawl4ai 抓取层 ============

def _try_crawl4ai(url: str) -> Optional[Dict]:
    """尝试用 crawl4ai 抓取（异步转同步）"""
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler

        async def _crawl():
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)
                return {
                    "title": getattr(result, "title", "") or "",
                    "content": getattr(result, "markdown", "") or getattr(result, "html", "") or "",
                    "url": url
                }

        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        return asyncio.run(_crawl())
    except ImportError:
        pass
    except Exception:
        pass
    return None


def scrape_with_crawl4ai(url: str, format: str = "json") -> Optional[Dict]:
    """
    抓取文章：非微信URL优先用 crawl4ai，失败回退到原有 urllib 路径
    微信URL保持三级降级不变

    Returns:
        {"title": str, "content": str, "url": str} 或 None
    """
    # 微信URL不走 crawl4ai
    if "mp.weixin.qq.com" in url:
        return None

    # 尝试 crawl4ai
    result = _try_crawl4ai(url)
    if result and result.get("content"):
        return result

    # 回退到原有 scrape_article（urllib 路径）
    return scrape_article(url, format=format)


# ============ v2.6: 数据溯源 ============

def extract_data_sources(article_text: str, use_llm: bool = False) -> List[Dict]:
    """
    正则+LLM扫描数据声明，标注来源情况

    Args:
        article_text: 文章全文
        use_llm: 是否启用LLM增强（标注置信度）

    Returns:
        [{"text": str, "has_source": bool, "source_text": str, "confidence": str}, ...]
    """
    if not article_text:
        return []

    claims = []

    # 正则扫描：百分比、数字区间、统计数据
    patterns = [
        (r"(\d+(?:\.\d+)?%)", "percentage"),
        (r"(\d+(?:\.\d+)?[-~]\d+(?:\.\d+)?[万亿千百]?)", "range"),
        (r"(\d+[万亿千百]?\s*(?:人|元|美元|亿|万))", "quantity"),
        (r"(根据|据|来源|[A-Za-z]+\s*(?:研究院|报告|数据|调查|统计))", "source_marker"),
    ]

    for pattern, claim_type in patterns:
        for match in re.finditer(pattern, article_text):
            text = match.group(0)
            # 检查前后文是否有来源标记
            start = max(0, match.start() - 50)
            end = min(len(article_text), match.end() + 50)
            context = article_text[start:end]

            has_source = bool(re.search(r"根据|据|来源|报告|研究院|调查|统计|发布", context))
            source_match = re.search(r"(?:根据|据|来源)([^，。,\.]{0,30})", context)
            source_text = source_match.group(0) if source_match else ""

            claims.append({
                "text": text,
                "has_source": has_source,
                "source_text": source_text,
                "claim_type": claim_type,
            })

    # LLM 增强
    if use_llm and claims:
        prompt = f"""你是事实核查专家。分析以下文章中数据声明是否可信。

文章节选：
{article_text[:2000]}

数据声明：
{json.dumps([c["text"] for c in claims[:10]], ensure_ascii=False)}

对每个声明标注置信度（high/medium/low/unverified）：
返回JSON：
{{"data_claims": [
  {{"text": "数据声明原文", "has_source": true/false, "source_text": "来源", "confidence": "high"}}
]}}"""

        raw = _call_llm_raw(prompt, temperature=0.2)
        if raw:
            parsed = _parse_llm_json(raw)
            if parsed and parsed.get("data_claims"):
                enhanced = parsed["data_claims"]
                # 合并 LLM 结果
                claim_map = {c["text"]: c for c in claims}
                for ec in enhanced:
                    text = ec.get("text", "")
                    if text in claim_map:
                        claim_map[text]["confidence"] = ec.get("confidence", "unverified")
                        claim_map[text]["has_source"] = ec.get("has_source", claim_map[text]["has_source"])
                return list(claim_map.values())

    return claims


# ============ 辅助函数 ============

def _safe_print(obj: Any) -> None:
    """Windows GBK 安全输出"""
    try:
        text = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    except Exception as e:
        print(f"[Print Error] {e}", file=sys.stderr)


def _load_ccos_for_topic(topic: str, platform: str) -> Optional[Dict]:
    """从 topic_log.yaml 加载最新的 CCOS 大纲"""
    log_path = Path(__file__).parent.parent / "data" / "topic_log.yaml"
    if not log_path.exists():
        return None

    try:
        import yaml
        with open(log_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return None

        # 找最新的有 ccos_outline 的条目
        for entry in reversed(data):
            ccos = entry.get("ccos_outline")
            if ccos:
                # 返回对应平台的 outline
                if platform == "both" and "wechat_cognitive_outline" in ccos:
                    return ccos["wechat_cognitive_outline"]
                elif platform == "wechat" and "wechat_cognitive_outline" in ccos:
                    return ccos["wechat_cognitive_outline"]
                elif platform == "xiaohongshu" and "xiaohongshu_cognitive_outline" in ccos:
                    return ccos["xiaohongshu_cognitive_outline"]
                elif "内容目标" in ccos:
                    return ccos
        return None
    except Exception as e:
        print(f"[Warning] 加载 CCOS 失败: {e}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 3:
        _safe_print({
            "error": "用法: python content_generator.py <命令> <标题> [--platform wechat|xiaohongshu]",
            "commands": {
                "generate": "批量生成完整草稿（无交互）",
                "interactive": "逐模块交互生成（确认/重写/编辑）",
                "recall": "测试素材召回",
                "gaps": "测试缺口检测"
            },
            "example": "python content_generator.py interactive 'AI让内容创作更容易' --platform wechat"
        })
        sys.exit(1)

    cmd = sys.argv[1]
    topic = sys.argv[2]
    platform = "wechat"

    for i, arg in enumerate(sys.argv[3:], 3):
        if arg == "--platform" and i < len(sys.argv):
            platform = sys.argv[i]

    if cmd == "generate":
        # 尝试从 topic_log 加载 CCOS 大纲
        ccos_outline = _load_ccos_for_topic(topic, platform)
        if not ccos_outline:
            _safe_print({
                "error": f"未找到命题 '{topic}' 的 CCOS 大纲，请先运行: python prism_os.py ccos '{topic}'",
                "topic": topic,
                "platform": platform
            })
            sys.exit(1)

        result = content_generation_workflow(topic, ccos_outline, platform)
        _safe_print(result)

    elif cmd == "interactive":
        ccos_outline = _load_ccos_for_topic(topic, platform)
        if not ccos_outline:
            print(f"[错误] 未找到命题 '{topic}' 的 CCOS 大纲，请先运行: python prism_os.py ccos '{topic}'")
            sys.exit(1)
        result = interactive_content_generation_workflow(topic, ccos_outline, platform)
        # interactive 函数自己 print 结果，返回 dict 给自动化调用
        _safe_print({"status": result["status"], "topic": topic, "platform": platform})

    elif cmd == "recall":
        # 单独测试素材召回
        module_type = sys.argv[3] if len(sys.argv) > 3 else "CASE"
        materials = recall_materials_by_module(topic, module_type)
        _safe_print({
            "topic": topic,
            "module_type": module_type,
            "materials": materials[:5]
        })

    elif cmd == "gaps":
        # 单独测试缺口检测
        ccos_outline = _load_ccos_for_topic(topic, platform)
        if not ccos_outline:
            _safe_print({"error": "未找到 CCOS 大纲"})
            sys.exit(1)
        gaps = detect_material_gaps(topic, ccos_outline)
        _safe_print({"topic": topic, "gaps": gaps})

    else:
        _safe_print({"error": f"未知命令: {cmd}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
