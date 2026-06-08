#!/usr/bin/env python3
"""
PRISM-OS Embedding 模块
提供独立的向量生成和相似度计算能力
"""

import os
import sys
import json
import hashlib
import re
import shutil
from typing import List, Optional
from pathlib import Path

import numpy as np
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ .env 自动加载（兼容跨机器迁移）============
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# ============ 常量 ============

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_EMBEDDING_MODEL = os.getenv("ZHIPU_EMBEDDING_MODEL", "embedding-2")
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
REQUEST_TIMEOUT = 30

# ============ 缓存管理 ============

def _get_cache_path() -> str:
    """获取缓存文件路径（相对于脚本目录的 ../data/）"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "..", "data")
    return os.path.join(data_dir, "embedding_cache.json")

def _load_cache() -> dict:
    """加载缓存，支持损坏恢复"""
    cache_path = _get_cache_path()

    if not os.path.exists(cache_path):
        return {"version": 1, "cache": {}}

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # 损坏恢复：备份并重建空缓存
        bak_path = cache_path + ".bak"
        if os.path.exists(cache_path):
            shutil.copy2(cache_path, bak_path)
        return {"version": 1, "cache": {}}

def _save_cache(cache: dict) -> bool:
    """保存缓存"""
    cache_path = _get_cache_path()
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        return True
    except IOError:
        return False

def clear_cache():
    """清空所有缓存（仅调试用）"""
    cache_path = _get_cache_path()
    if os.path.exists(cache_path):
        os.remove(cache_path)

# ============ 向量操作 ============

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """计算两个向量的 Cosine 相似度"""
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def _jaccard(text_a: str, text_b: str) -> float:
    """计算 Jaccard 相似度（基于词汇）"""
    tokens_a = set(re.findall(r'\w+', text_a.lower()))
    tokens_b = set(re.findall(r'\w+', text_b.lower()))
    if not tokens_a and not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

def _md5(text: str) -> str:
    """计算文本的 MD5 哈希"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()

# ============ 核心接口 ============

def embed(text: str, model: str = None) -> Optional[List[float]]:
    """
    生成文本向量
    流程：检查缓存 → 有则返回 → 无则调智谱API → 写入缓存 → 返回向量
    超时/失败返回 None
    """
    if not text or not text.strip():
        return None

    model = model or ZHIPU_EMBEDDING_MODEL
    cache = _load_cache()
    text_hash = _md5(text)

    # 缓存命中
    if text_hash in cache.get("cache", {}):
        return cache["cache"][text_hash]

    # 检查 API Key
    api_key = ZHIPU_API_KEY
    if not api_key:
        print("ERROR: ZHIPU_API_KEY environment variable not set", file=sys.stderr)
        return None

    # 调用智谱 API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "input": text
    }

    try:
        response = requests.post(
            ZHIPU_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )
        response.raise_for_status()
        data = response.json()

        # 提取向量 (embedding-2 返回格式: data[0].embedding)
        embedding = data.get("data", [{}])[0].get("embedding")
        if not embedding:
            print("ERROR: No embedding in API response", file=sys.stderr)
            return None

        # 写入缓存
        if "cache" not in cache:
            cache["cache"] = {}
        cache["cache"][text_hash] = embedding
        _save_cache(cache)

        return embedding

    except requests.exceptions.Timeout:
        print("ERROR: API request timeout", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        return None

def get_similarity(text_a: str, text_b: str) -> Optional[float]:
    """
    计算两个标题的相似度
    公式：0.4 × Jaccard + 0.6 × Cosine(向量)
    Cosine 失败时降级到纯 Jaccard
    """
    if not text_a or not text_b:
        return None

    # Jaccard
    jaccard = _jaccard(text_a, text_b)

    # 获取向量并计算 Cosine
    vec_a = embed(text_a)
    vec_b = embed(text_b)

    if vec_a and vec_b:
        cosine = cosine_similarity(vec_a, vec_b)
        return 0.4 * jaccard + 0.6 * cosine
    else:
        # 降级到纯 Jaccard
        return jaccard

# ============ CLI 接口 ============

def cli_embed(text: str):
    """CLI: embed <文本>"""
    vector = embed(text)
    if vector:
        print(json.dumps({"status": "ok", "vector": vector, "dimension": len(vector)}))
    else:
        print(json.dumps({"status": "error", "message": "Failed to generate embedding"}))

def cli_similarity(text_a: str, text_b: str):
    """CLI: similarity <文本A> <文本B>"""
    similarity = get_similarity(text_a, text_b)
    if similarity is not None:
        print(json.dumps({"status": "ok", "similarity": similarity}))
    else:
        print(json.dumps({"status": "error", "message": "Failed to calculate similarity"}))

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python embedding.py embed <文本>")
        print("  python embedding.py similarity <文本A> <文本B>")
        print("  python embedding.py clear")
        sys.exit(1)

    command = sys.argv[1]

    if command == "embed":
        if len(sys.argv) < 3:
            print("ERROR: missing text argument", file=sys.stderr)
            sys.exit(1)
        cli_embed(sys.argv[2])

    elif command == "similarity":
        if len(sys.argv) < 4:
            print("ERROR: missing text arguments", file=sys.stderr)
            sys.exit(1)
        cli_similarity(sys.argv[2], sys.argv[3])

    elif command == "clear":
        clear_cache()
        print(json.dumps({"status": "ok", "message": "Cache cleared"}))

    else:
        print(f"ERROR: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()