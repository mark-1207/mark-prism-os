#!/usr/bin/env python3
"""
PRISM-OS 数据持久化脚本
用法: python storage.py <操作> <数据>
操作: append_log / load_log / load_config / save_config
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional
from datetime import datetime

class PRISMError(Exception):
    """PRISM-OS 专用异常类"""
    pass

def get_data_dir() -> str:
    """获取数据目录路径"""
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base_dir, "data")

def get_config_path() -> str:
    """获取配置文件路径"""
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base_dir, "config", "user_config.yaml")

def load_yaml(path: str) -> List[Dict]:
    """YAML 加载（支持 JSON 嵌套格式）"""
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        if not content.strip():
            return []

    result = []

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            json_str = line[2:].strip()
            if json_str.startswith("{"):
                # JSON 格式（新格式）
                try:
                    item = json.loads(json_str)
                    result.append(item)
                except json.JSONDecodeError:
                    pass
            else:
                # 旧格式兼容（key: value）
                current_item = {}
                # 解析简单的 key: value 格式
                if ": " in json_str:
                    key, value = json_str.split(": ", 1)
                    current_item[key.strip()] = value.strip().strip('"').strip("'")
                    result.append(current_item)

    return result

def save_yaml(path: str, data: List[Dict]) -> bool:
    """YAML 保存（使用 JSON 嵌套保留所有字段）"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write("  - ")
                # 使用 JSON 序列化保留所有字段
                f.write(json.dumps(item, ensure_ascii=False))
                f.write("\n")
        return True
    except Exception as e:
        return False

def append_log(entry: Dict) -> Dict:
    """追加选题日志"""
    log_path = os.path.join(get_data_dir(), "topic_log.yaml")
    logs = load_yaml(log_path)

    entry["timestamp"] = datetime.now().isoformat()
    entry["cumulative_count"] = len(logs) + 1
    logs.append(entry)

    if save_yaml(log_path, logs):
        return {"status": "ok", "message": "日志已保存", "cumulative_count": entry["cumulative_count"]}
    else:
        raise PRISMError("保存失败:未产生有效候选")


def append_selected_title(
    title: str,
    platform: str,
    source: str = "prism",
    metadata: Dict = None
) -> Dict:
    """
    记录用户从 prism 交互中选中的标题

    Args:
        title: 选中的标题
        platform: wechat / xiaohongshu / both
        source: 来源（prism/manual/adjust）
        metadata: 额外元数据（如 dimension、archetype 等）

    Returns:
        {"status": "ok", "entry": {...}}
    """
    log_path = os.path.join(get_data_dir(), "topic_log.yaml")
    logs = load_yaml(log_path)

    entry = {
        "selected_title": title,
        "platform": platform,
        "source": source,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        entry["metadata"] = metadata

    logs.append(entry)

    if save_yaml(log_path, logs):
        return {"status": "ok", "message": "选中标题已记录", "entry": entry}
    else:
        raise PRISMError("保存选中标题失败")


def get_latest_selected_title(platform: str = None) -> Optional[Dict]:
    """
    获取最近一次用户选中的标题

    Args:
        platform: 可选，筛选平台

    Returns:
        {"selected_title": str, "platform": str, "timestamp": str} 或 None
    """
    log_path = os.path.join(get_data_dir(), "topic_log.yaml")
    logs = load_yaml(log_path)

    for entry in reversed(logs):
        if "selected_title" in entry:
            if platform is None or entry.get("platform") == platform:
                return entry
    return None

def load_log(limit: int = 10) -> List[Dict]:
    """加载最近的选题日志"""
    if not isinstance(limit, int) or limit < 0:
        limit = 10
    log_path = os.path.join(get_data_dir(), "topic_log.yaml")
    logs = load_yaml(log_path)
    return logs[-limit:] if logs else []

def load_config() -> Dict:
    """加载用户配置"""
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    config = {}
    current_section = None

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line and not line.startswith("  "):
            current_section = line.replace(":", "").strip()
            config[current_section] = {}
        elif ": " in line and current_section:
            key, value = line.split(": ", 1)
            config[current_section][key.strip()] = value.strip().strip('"').strip("'").strip('[').strip(']')

    return config

def save_config(config: Dict) -> Dict:
    """保存用户配置"""
    config_path = get_config_path()

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        lines = []
        for section, items in config.items():
            lines.append(f"{section}:")
            for key, value in items.items():
                lines.append(f"  {key}: \"{value}\"")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return {"status": "ok"}
    except Exception as e:
        raise PRISMError(f"配置保存失败: {str(e)}")

# ============ 相似度计算（用于查重） ============

def tokenize(text: str) -> List[str]:
    """简单分词"""
    return re.findall(r'\w+', text.lower())

def calculate_similarity(title_a: str, title_b: str, embedding_model=None) -> float:
    """
    相似度计算：Jaccard×0.4 + Cosine×0.6
    """
    # Jaccard 相似度
    tokens_a = set(tokenize(title_a))
    tokens_b = set(tokenize(title_b))
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if tokens_a or tokens_b else 0

    # Cosine 相似度（如有嵌入模型）
    if embedding_model:
        vec_a = embedding_model.embed(title_a)
        vec_b = embedding_model.embed(title_b)
        cosine = cosine_similarity([vec_a], [vec_b])[0][0]
    else:
        cosine = 0

    return 0.4 * jaccard + 0.6 * cosine

# ============ 词汇指纹检测 ============

def load_vocab_fingerprint() -> Dict:
    """加载词汇指纹库"""
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    fp_path = os.path.join(base_dir, "references", "vocab_fingerprint.json")

    if not os.path.exists(fp_path):
        return {"cliche_patterns": [], "replacement_map": {}}

    with open(fp_path, "r", encoding="utf-8") as f:
        return json.load(f)

def check_cliche(title: str) -> Dict:
    """
    检测标题是否使用陈词滥调
    """
    vocab = load_vocab_fingerprint()

    for pattern in vocab.get("cliche_patterns", []):
        if re.search(pattern["pattern"], title):
            replacement_map = vocab.get("replacement_map", {})
            suggestion = title
            for word, replacement in replacement_map.items():
                if word in title:
                    suggestion = title.replace(word, replacement)
                    break

            return {
                "is_cliche": True,
                "matched_pattern": pattern["pattern"],
                "reason": pattern["reason"],
                "suggestion": suggestion
            }

    return {"is_cliche": False}

# ============ 数字分身反馈 ============

def save_twin_feedback(feedback: Dict) -> Dict:
    """
    保存数字分身反馈

    Args:
        feedback: {
            "thesis": str,
            "twin_selected": List[str],
            "user_selected": str,
            "match": bool
        }

    Returns:
        {"status": "ok"}
    """
    feedback_path = os.path.join(get_data_dir(), "twin_feedback.yaml")
    feedbacks = load_yaml(feedback_path)

    feedback["timestamp"] = datetime.now().isoformat()
    feedbacks.append(feedback)

    if save_yaml(feedback_path, feedbacks):
        return {"status": "ok", "message": "反馈已保存"}
    else:
        raise PRISMError("反馈保存失败")


def load_twin_feedback(limit: int = 100) -> List[Dict]:
    """
    加载数字分身反馈

    Args:
        limit: 加载数量限制

    Returns:
        反馈列表
    """
    feedback_path = os.path.join(get_data_dir(), "twin_feedback.yaml")
    feedbacks = load_yaml(feedback_path)
    return feedbacks[-limit:] if feedbacks else []


def calculate_twin_accuracy(limit: int = 50) -> Dict:
    """
    计算数字分身匹配度

    Args:
        limit: 计算最近 N 条反馈

    Returns:
        {
            "accuracy": float,  # 匹配度
            "total": int,  # 总反馈数
            "matches": int,  # 匹配数
            "needs_calibration": bool  # 是否需要校准
        }
    """
    feedbacks = load_twin_feedback(limit=limit)
    if not feedbacks:
        return {
            "accuracy": 0.0,
            "total": 0,
            "matches": 0,
            "needs_calibration": False
        }

    total = len(feedbacks)
    matches = sum(1 for f in feedbacks if f.get("match", False))
    accuracy = matches / total if total > 0 else 0.0

    # 检查是否需要校准（每 50 次）
    config = load_config()
    calibration_interval = int(config.get("digital_twin", {}).get("calibration_interval", "50"))
    needs_calibration = total > 0 and total % calibration_interval == 0

    return {
        "accuracy": accuracy,
        "total": total,
        "matches": matches,
        "needs_calibration": needs_calibration
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "用法: python storage.py <操作> <数据JSON>"}))
        sys.exit(1)

    operation = sys.argv[1]
    data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    try:
        if operation == "append_log":
            print(json.dumps(append_log(data)))
        elif operation == "load_log":
            print(json.dumps(load_log(data.get("limit", 10))))
        elif operation == "load_config":
            print(json.dumps(load_config()))
        elif operation == "save_config":
            print(json.dumps(save_config(data)))
        elif operation == "check_cliche":
            print(json.dumps(check_cliche(data.get("title", ""))))
        elif operation == "save_twin_feedback":
            print(json.dumps(save_twin_feedback(data)))
        elif operation == "load_twin_feedback":
            print(json.dumps(load_twin_feedback(data.get("limit", 100))))
        elif operation == "calculate_twin_accuracy":
            print(json.dumps(calculate_twin_accuracy(data.get("limit", 50))))
        else:
            print(json.dumps({"error": f"未知操作: {operation}"}))
    except PRISMError as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()