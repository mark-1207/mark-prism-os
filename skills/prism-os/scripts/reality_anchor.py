#!/usr/bin/env python3
"""
PRISM-OS Phase 3: 现实校验锚（Reality Anchor）
搜索查重脚本

支持:
- Tavily API (优先)
- Firecrawl API (备用)

用法:
    python reality_anchor.py check "<标题>"
    python reality_anchor.py validate "[{\"title\": \"...\"}]"
"""

import sys
import json
import os
import re
import subprocess
from typing import Dict, List, Optional
from pathlib import Path

# ============ .env 自动加载（兼容跨机器迁移）============
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# API Keys
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "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")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "fc-1e66bdfd656a4fe5a3f94395151a7c6c")


# ============ 搜索 API（curl subprocess 实现，绕过 Python SSL 问题）============

def search_tavily(query: str, num_results: int = 10) -> List[Dict]:
    """调用 Tavily API 搜索（curl 实现，绕过 Python SSL 问题）"""
    try:
        payload = json.dumps({"api_key": TAVILY_API_KEY, "query": query, "max_results": num_results})
        proc = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-k", "-X", "POST",
             "https://api.tavily.com/search",
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, timeout=35
        )
        if proc.returncode != 0 or not proc.stdout:
            return []
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        return [
            {"title": item.get("title", ""), "url": item.get("url", ""),
             "snippet": item.get("content", item.get("snippet", ""))}
            for item in result.get("results", [])[:num_results]
        ]
    except Exception as e:
        print(f"[Tavily Error] {e}", file=sys.stderr)
        return []


def search_firecrawl(query: str, num_results: int = 10) -> List[Dict]:
    """调用 Firecrawl API 搜索（curl 实现，绕过 Python SSL 问题）"""
    try:
        payload = json.dumps({"query": query, "limit": num_results})
        proc = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-k", "-X", "POST",
             "https://api.firecrawl.dev/v0/search",
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {FIRECRAWL_API_KEY}",
             "-d", payload],
            capture_output=True, timeout=35
        )
        if proc.returncode != 0 or not proc.stdout:
            return []
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        if result.get("success"):
            return [
                {"title": item.get("title", ""), "url": item.get("url", ""),
                 "snippet": item.get("description", item.get("snippet", ""))}
                for item in result.get("data", [])[:num_results]
            ]
        return []
    except Exception as e:
        print(f"[Firecrawl Error] {e}", file=sys.stderr)
        return []


def search_titles(query: str, num_results: int = 10) -> List[Dict]:
    """调用搜索 API 查重（优先 Tavily，失败则 Firecrawl）"""
    results = search_tavily(query, num_results)
    if results:
        return results
    print("[Warning] Tavily 失败，切换到 Firecrawl", file=sys.stderr)
    results = search_firecrawl(query, num_results)
    if results:
        return results
    print("[Warning] 所有搜索 API 均失败，返回空结果", file=sys.stderr)
    return []


# ============ Phase 3: 相似度计算 ============

def tokenize_chinese(text: str) -> set:
    """简单中文分词：按字符拆分，过滤空白"""
    return set(c for c in text if not c.isspace())


def calculate_jaccard(title_a: str, title_b: str) -> float:
    """计算标题之间的 Jaccard 相似度"""
    tokens_a = tokenize_chinese(title_a.lower())
    tokens_b = tokenize_chinese(title_b.lower())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def calculate_duplicate_rate(title: str, search_results: List[Dict]) -> float:
    """计算标题查重率"""
    if not search_results:
        return 0.0
    max_similarity = 0.0
    for result in search_results:
        result_title = result.get("title", "")
        if not result_title:
            continue
        sim = calculate_jaccard(title, result_title)
        if sim > max_similarity:
            max_similarity = sim
    return max_similarity


def evaluate_competition_level(duplicate_rate: float) -> str:
    """根据查重率评估竞争度"""
    if duplicate_rate < 0.3:
        return "蓝海"
    elif duplicate_rate < 0.7:
        return "黄海"
    else:
        return "红海"


# ============ Phase 3: 现实校验主流程 ============

def reality_anchor(candidates: List[Dict], search_results_cache: Optional[Dict] = None) -> Dict:
    """现实校验锚主流程"""
    validated = []
    rejected = []
    search_results_cache = search_results_cache or {}

    for candidate in candidates:
        title = candidate.get("title", "")
        if not title:
            continue

        cache_key = title[:50]
        if cache_key in search_results_cache:
            search_results = search_results_cache[cache_key]
        else:
            search_results = search_titles(title)
            search_results_cache[cache_key] = search_results

        duplicate_rate = calculate_duplicate_rate(title, search_results)
        competition_level = evaluate_competition_level(duplicate_rate)

        validated_result = {
            **candidate,
            "duplicate_rate": duplicate_rate,
            "competition_level": competition_level,
            "search_results": search_results[:3]
        }

        if duplicate_rate > 0.8:
            validated_result["rejection_reason"] = "与现有内容重复度过高"
            rejected.append(validated_result)
        else:
            novelty_score = 1.0 - duplicate_rate
            validated_result["novelty_score"] = novelty_score
            validated.append(validated_result)

    statistics = {
        "total_count": len(candidates),
        "validated_count": len(validated),
        "rejected_count": len(rejected),
        "blue_ocean": sum(1 for v in validated if v["competition_level"] == "蓝海"),
        "yellow_ocean": sum(1 for v in validated if v["competition_level"] == "黄海"),
        "red_ocean": sum(1 for v in validated if v["competition_level"] == "红海"),
        "avg_novelty": sum(v.get("novelty_score", 0) for v in validated) / len(validated) if validated else 0
    }

    status = "success" if len(validated) >= len(candidates) * 0.5 else "partial"

    return {"status": status, "validated": validated, "rejected": rejected, "statistics": statistics}


def check_single_title(title: str) -> Dict:
    """检查单个标题"""
    search_results = search_titles(title)
    duplicate_rate = calculate_duplicate_rate(title, search_results)
    competition_level = evaluate_competition_level(duplicate_rate)
    novelty_score = 1.0 - duplicate_rate
    return {
        "title": title,
        "duplicate_rate": duplicate_rate,
        "competition_level": competition_level,
        "novelty_score": novelty_score,
        "search_results": search_results[:3]
    }


# ============ CLI 入口 ============

def _safe_print(obj):
    """修复 Windows GBK 编码问题"""
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


def main():
    if len(sys.argv) < 3:
        _safe_print({
            "error": "用法: reality_anchor.py <命令> <数据>",
            "commands": {
                "check": "reality_anchor.py check \"<标题>\" - 检查单个标题",
                "validate": "reality_anchor.py validate '[{\"title\": \"...\"}]' - 批量校验候选"
            }
        })
        sys.exit(1)

    command = sys.argv[1]
    data = sys.argv[2]

    if command == "check":
        result = check_single_title(data)
        _safe_print(result)
    elif command == "validate":
        try:
            candidates = json.loads(data)
        except json.JSONDecodeError:
            _safe_print({"error": "无效的 JSON 格式"})
            sys.exit(1)
        result = reality_anchor(candidates)
        _safe_print(result)
    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
