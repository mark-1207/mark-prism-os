#!/usr/bin/env python3
"""
PRISM-OS 搜索查重脚本
用法: python search.py "<标题>"
"""

import sys
import json
import os
from typing import Dict, List

def load_config() -> Dict:
    """加载用户配置"""
    return {
        "search_api_url": os.environ.get("SEARCH_API_URL", ""),
        "search_api_key": os.environ.get("SEARCH_API_KEY", "")
    }

def search(query: str, num_results: int = 10) -> List[Dict]:
    """
    调用搜索API

    Args:
        query: 搜索关键词
        num_results: 返回结果数量

    Returns:
        [{"title": "...", "url": "...", "snippet": "..."}, ...]
    """
    config = load_config()

    if not config["search_api_url"] or not config["search_api_key"]:
        return [{"error": "请配置 SEARCH_API_URL 和 SEARCH_API_KEY 环境变量"}]

    try:
        import urllib.request
        import urllib.error

        payload = {
            "query": query,
            "num_results": num_results
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            config["search_api_url"],
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['search_api_key']}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("results", [])

    except urllib.error.HTTPError as e:
        return [{"error": f"HTTP错误: {e.code} {e.reason}"}]
    except urllib.error.URLError as e:
        return [{"error": f"网络错误: {e.reason}"}]
    except Exception as e:
        return [{"error": f"未知错误: {str(e)}"}]

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "用法: python search.py \"<标题>\""
        }))
        sys.exit(1)

    query = sys.argv[1]
    results = search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()