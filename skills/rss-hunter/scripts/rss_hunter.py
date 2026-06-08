#!/usr/bin/env python3
"""
RSS-Hunter — 信息源猎手
RSS 抓取 + 认知裂缝检测 + crack_queue 写入

用法:
    python rss_hunter.py fetch                    # 抓取所有信源，更新去重记录
    python rss_hunter.py hunt                     # 抓取 + 裂缝检测 + 写入 crack_queue
    python rss_hunter.py hunt --source "36氪"     # 只处理指定信源
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ============ 路径设置 ============

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent  # PRISM-OSv1/
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "prism-os" / "scripts"))

# 导入现有模块
sys.path.insert(0, str(PROJECT_ROOT / ".claude"))
from feed_parser import parse_xml, extract_items, extract_fields, is_duplicate
from crack_hunter_wrapper import analyze_content
from rss_monitor import _fetch_feed

# 导入 crack_queue
from crack_queue import CrackQueue


def _safe_print(text: str):
    """Windows GBK 安全输出"""
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")


# ============ 配置 ============

CONFIG_FILE = SCRIPT_DIR.parent / "config" / "feeds.yaml"


def _load_config() -> Dict:
    """加载信源配置"""
    import yaml
    if not CONFIG_FILE.exists():
        _safe_print(f"[Error] 配置文件不存在: {CONFIG_FILE}")
        return {"monitored_sources": []}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        _safe_print(f"[Error] 加载配置失败: {e}")
        return {"monitored_sources": []}


# ============ 辅助函数 ============

def _get_source_tags(source: Dict) -> Tuple[str, List[str]]:
    """从信源配置提取 category 和 tags"""
    category = source.get("category", source.get("region", "general"))
    tags = source.get("tags", [])
    if not tags:
        tags = [source.get("region", "general")]
    return category, tags


def _build_crack_entry(
    fields: Dict,
    crack_info: Dict,
    source_name: str,
    category: str,
    tags: List[str]
) -> Dict:
    """构建 crack_queue 条目"""
    return {
        "title": fields["title"],
        "source": source_name,
        "source_link": fields.get("link", ""),
        "crack_type": crack_info.get("crack_type", "未知"),
        "consensus": crack_info.get("consensus", ""),
        "reality": crack_info.get("reality", ""),
        "confidence": crack_info.get("confidence", 0),
        "signals": crack_info.get("signals", {}),
        "expression_angles": crack_info.get("expression_angles", []),
        "creator_match": crack_info.get("creator_match", {}),
        "tags": tags,
        "category": category,
    }


# ============ 共享抓取逻辑 ============

def _load_sources(source_filter: Optional[str] = None) -> List[Dict]:
    """加载并过滤信源列表"""
    config = _load_config()
    sources = config.get("monitored_sources", [])
    if source_filter:
        sources = [s for s in sources if s.get("name") == source_filter]
        if not sources:
            _safe_print(f"[Error] 未找到信源: {source_filter}")
    return sources


def _iter_new_items(sources: List[Dict]):
    """抓取所有信源，yield 新条目 (fields, source_name, category, tags)"""
    for source in sources:
        name = source.get("name", "未知")
        url = source.get("url", "")
        category, tags = _get_source_tags(source)

        if not url:
            _safe_print(f"[跳过] {name} — 无 URL")
            continue

        _safe_print(f"[抓取] {name}...")
        xml_content = _fetch_feed(url)
        if not xml_content:
            _safe_print(f"  ✗ 抓取失败")
            continue

        root = parse_xml(xml_content)
        if not root:
            _safe_print(f"  ✗ XML 解析失败")
            continue

        items = extract_items(root)
        if not items:
            _safe_print(f"  ⚠ 无条目")
            continue

        new_count = 0
        skip_count = 0
        for item in items:
            fields = extract_fields(item, url)
            if is_duplicate(fields["title"], fields["pub_date"]):
                skip_count += 1
            else:
                new_count += 1
                yield fields, name, category, tags

        _safe_print(f"  ✓ 新条目: {new_count}, 跳过: {skip_count}")


# ============ fetch 命令 ============

def cmd_fetch(source_filter: Optional[str] = None):
    """抓取所有信源，更新去重记录"""
    sources = _load_sources(source_filter)
    if not sources:
        return

    total_new = 0
    for _fields, _name, _cat, _tags in _iter_new_items(sources):
        total_new += 1

    _safe_print(f"\n[完成] 总计新条目: {total_new}")


# ============ hunt 命令 ============

def cmd_hunt(source_filter: Optional[str] = None):
    """抓取 + 裂缝检测 + 写入 crack_queue"""
    sources = _load_sources(source_filter)
    if not sources:
        return

    q = CrackQueue()
    total_cracks = 0
    total_non_cracks = 0
    total_errors = 0
    crack_entries = []  # 收集裂缝用于最终汇总

    for fields, name, category, tags in _iter_new_items(sources):
        # 裂缝检测
        try:
            has_crack, crack_info = analyze_content(
                fields["title"],
                fields["summary"],
                name
            )
        except Exception as e:
            _safe_print(f"  [Error] 裂缝检测失败: {fields['title'][:30]}... — {e}")
            total_errors += 1
            continue

        if has_crack:
            # 构建条目
            entry = _build_crack_entry(fields, crack_info, name, category, tags)
            q.add(entry)
            crack_entries.append(entry)
            total_cracks += 1
        else:
            total_non_cracks += 1

    # 汇总输出（不再逐条推送）
    active, total = q.count()
    _safe_print(f"\n{'=' * 40}")
    _safe_print(f"[RSS-Hunter] 完成：新增 {total_cracks} 条认知裂缝，队列当前共 {active} 条待消费")
    _safe_print(f"{'=' * 40}")

    # 展示新增裂缝摘要
    if crack_entries:
        _safe_print("\n新增裂缝：")
        for e in crack_entries[:5]:  # 最多展示5条
            signals = e.get("signals", {})
            emotions = signals.get("emotion", [])
            crack_type = e.get("crack_type", "")
            confidence = e.get("confidence", 0)

            print(f"  - [{crack_type}] {e['title'][:40]}...")
            if emotions:
                print(f"    信号：{'/'.join(emotions)}")
            if signals.get("trend"):
                print(f"    趋势：{signals['trend'][:30]}...")

    if total_non_cracks > 0:
        _safe_print(f"\n（另有 {total_non_cracks} 条为普通条目，未写入队列）")


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(
        description="RSS-Hunter — 信息源猎手：RSS 抓取 + 认知裂缝检测 + crack_queue 写入"
    )
    subparsers = parser.add_subparsers(dest="command")

    # fetch 命令
    fetch_parser = subparsers.add_parser("fetch", help="抓取所有信源，更新去重记录")
    fetch_parser.add_argument("--source", "-s", help="只处理指定信源（按 name 精确匹配）")

    # hunt 命令
    hunt_parser = subparsers.add_parser("hunt", help="抓取 + 裂缝检测 + 写入 crack_queue")
    hunt_parser.add_argument("--source", "-s", help="只处理指定信源（按 name 精确匹配）")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args.source)
    elif args.command == "hunt":
        cmd_hunt(args.source)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()