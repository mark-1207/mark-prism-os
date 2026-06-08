"""Phase 6.0 — 模板优选：按平台 × 叙事策略 / CCOS 模块组合统计真实互动率"""
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CALIBRATION_PATH = os.path.join(DATA_DIR, "feedback_calibration.yaml")


def calculate_engagement_rate(row: Dict) -> float:
    """计算互动率 = (点赞+评论+收藏+转发) / 阅读"""
    reads = row.get("阅读量") or 0
    if reads <= 0:
        return 0.0
    likes = row.get("点赞量") or 0
    comments = row.get("评论数") or 0
    collects = row.get("收藏量") or 0
    shares = row.get("转发量") or 0
    return (likes + comments + collects + shares) / reads


def calculate_ci(values: List[float]) -> tuple:
    """计算 95% 置信区间（简化版：mean ± 1.96 * stderr）"""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (0.0, values[0] * 2)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    stderr = math.sqrt(variance / n)
    ci_low = max(0.0, mean - 1.96 * stderr)
    ci_high = mean + 1.96 * stderr
    return (round(ci_low, 4), round(ci_high, 4))


def _extract_select_value(val):
    """提取 select 字段的值（可能是字符串或列表）"""
    if isinstance(val, list):
        return val[0] if val else "unknown"
    return val if val else "unknown"


def score_by_strategy(articles: List[Dict]) -> Dict[str, Dict[str, Dict]]:
    """按平台 × 叙事策略分组，计算平均互动率和置信区间

    Returns:
        {platform: {strategy: {avg_engagement, sample_size, confidence_low, confidence_high}}}
    """
    groups = defaultdict(lambda: defaultdict(list))
    for a in articles:
        platform = _extract_select_value(a.get("平台"))
        strategy = a.get("叙事策略", "unknown")
        if isinstance(strategy, list):
            strategy = strategy[0] if strategy else "unknown"
        rate = calculate_engagement_rate(a)
        groups[platform][strategy].append(rate)

    result = {}
    for platform, strategies in groups.items():
        result[platform] = {}
        for strategy, rates in strategies.items():
            avg = sum(rates) / len(rates)
            ci_low, ci_high = calculate_ci(rates)
            result[platform][strategy] = {
                "avg_engagement": round(avg, 4),
                "sample_size": len(rates),
                "confidence_low": ci_low,
                "confidence_high": ci_high,
            }
    return result


def score_by_module_combo(articles: List[Dict]) -> Dict[str, Dict[str, Dict]]:
    """按平台 × CCOS 模块组合分组，计算平均互动率

    Returns:
        {platform: {combo_key: {avg_engagement, sample_size}}}
    """
    groups = defaultdict(lambda: defaultdict(list))
    for a in articles:
        platform = _extract_select_value(a.get("平台"))
        modules = a.get("CCOS模块") or []
        if isinstance(modules, list):
            combo_key = ",".join(sorted(modules)) if modules else "unknown"
        else:
            combo_key = str(modules) if modules else "unknown"
        rate = calculate_engagement_rate(a)
        groups[platform][combo_key].append(rate)

    result = {}
    for platform, combos in groups.items():
        result[platform] = {}
        for combo_key, rates in combos.items():
            avg = sum(rates) / len(rates)
            result[platform][combo_key] = {
                "avg_engagement": round(avg, 4),
                "sample_size": len(rates),
            }
    return result


def run_calibration(articles: List[Dict], min_sample: int = 3) -> Dict:
    """运行模板优选，输出 calibration 配置

    Args:
        articles: 从 snapshot 加载的文章数据
        min_sample: 最小样本量阈值（低于此值的策略不参与排序）

    Returns:
        完整的 calibration 字典
    """
    # 只用 T+7d 或 T+30d 的数据（更稳定）
    stable_articles = [
        a for a in articles
        if a.get("时间点") in ("t_plus_7d", "t_plus_30d")
    ]
    if not stable_articles:
        stable_articles = articles  # fallback

    strategy_scores = score_by_strategy(stable_articles)
    module_scores = score_by_module_combo(stable_articles)

    # 过滤样本不足的策略
    for platform in strategy_scores:
        strategy_scores[platform] = {
            k: v for k, v in strategy_scores[platform].items()
            if v["sample_size"] >= min_sample
        }

    calibration = {
        "last_updated": datetime.now().isoformat(),
        "sample_size": len(stable_articles),
        "by_platform_strategy": strategy_scores,
        "by_platform_module_combo": module_scores,
    }
    return calibration


def save_calibration(calibration: Dict):
    """保存 calibration 到 YAML 文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        import yaml
        with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
            yaml.dump(calibration, f, allow_unicode=True, default_flow_style=False)
    except ImportError:
        with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
            json.dump(calibration, f, ensure_ascii=False, indent=2)


def load_calibration() -> Optional[Dict]:
    """加载 calibration 配置"""
    if not os.path.exists(CALIBRATION_PATH):
        return None
    try:
        import yaml
        with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (ImportError, Exception):
        with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
            return json.load(f)


if __name__ == "__main__":
    # CLI 入口
    snapshot_path = os.path.join(DATA_DIR, "metrics_snapshot.yaml")
    if not os.path.exists(snapshot_path):
        print(json.dumps({"error": "未找到 metrics_snapshot.yaml，请先运行 metrics sync"}))
        exit(1)

    try:
        import yaml
        with open(snapshot_path, "r", encoding="utf-8") as f:
            articles = yaml.safe_load(f) or []
    except (ImportError, Exception):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            articles = json.load(f)

    calibration = run_calibration(articles)
    save_calibration(calibration)
    print(json.dumps({
        "status": "ok",
        "sample_size": calibration["sample_size"],
        "strategies_scored": sum(
            len(v) for v in calibration.get("by_platform_strategy", {}).values()
        ),
    }, ensure_ascii=False))
