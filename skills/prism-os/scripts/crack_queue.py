#!/usr/bin/env python3
"""
CrackQueue — 选题情报员队列管理
crack_queue.json 数据结构 + 读写操作

用法:
    from crack_queue import CrackQueue
    q = CrackQueue()
    q.add(entry)
    q.list_all()
    q.tag(id, "战略级")
    q.dismiss(id)
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============ 路径配置 ============

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # PRISM-OSv1/
DATA_DIR = PROJECT_ROOT / "data"
CRACK_QUEUE_FILE = DATA_DIR / "crack_queue.json"
CRACK_ARCHIVE_FILE = DATA_DIR / "crack_archive.json"

# 配置
MAX_QUEUE_SIZE = 100
MAX_QUEUE_DAYS = 60
ARCHIVE_AFTER_DAYS = 60

# creator_model 缓存（避免每次 add 都调 LLM）
_CREATOR_MODEL_CACHE: Optional[Dict] = None
_CREATOR_MODEL_CACHE_TTL = 300  # 5分钟内复用

# ============ 优先级计算 ============

TAG_MULTIPLIERS = {
    "战略级": 2.0,
    "关注": 1.5,
}

RECENCY_FACTORS = [
    (7, 1.0),
    (30, 0.7),
    (float("inf"), 0.4),
]


def _calc_recency_factor(created_at: str) -> float:
    """根据创建时间计算衰减因子"""
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except Exception:
        return 1.0
    now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
    days = (now - created).days
    for threshold, factor in RECENCY_FACTORS:
        if days <= threshold:
            return factor
    return 0.4


def _calc_priority_score(entry: Dict) -> float:
    """计算条目优先级分数"""
    confidence = entry.get("confidence", 0)

    # tag multiplier
    tags = entry.get("manual_tags", [])
    tag_mult = 1.0
    for tag in tags:
        tag_mult = max(tag_mult, TAG_MULTIPLIERS.get(tag, 1.0))

    # recency factor
    recency = _calc_recency_factor(entry.get("created_at", ""))

    # homogenization penalty
    signals = entry.get("signals", {})
    homogenization = signals.get("homogenization_alert", "不确定")
    homo_penalty = 0.5 if homogenization == "是" else 1.0

    score = confidence * tag_mult * recency * homo_penalty
    return round(score, 3)


# ============ 主类 ============


class CrackQueue:
    """裂纹队列表管理"""

    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.queue_path = CRACK_QUEUE_FILE
        self.archive_path = CRACK_ARCHIVE_FILE

    # ============ 读写 ============

    def _load_queue(self) -> List[Dict]:
        if not self.queue_path.exists():
            return []
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_queue(self, entries: List[Dict]):
        with open(self.queue_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def _load_archive(self) -> List[Dict]:
        if not self.archive_path.exists():
            return []
        try:
            with open(self.archive_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_archive(self, entries: List[Dict]):
        with open(self.archive_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    # ============ 核心操作 ============

    def add(self, entry: Dict) -> str:
        """添加新条目到队列"""
        global _CREATOR_MODEL_CACHE

        if "id" not in entry:
            entry["id"] = str(uuid.uuid4())
        if "created_at" not in entry:
            entry["created_at"] = datetime.now().isoformat()
        if "status" not in entry:
            entry["status"] = "new"
        if "manual_tags" not in entry:
            entry["manual_tags"] = []
        if "notes" not in entry:
            entry["notes"] = ""
        if "consumed_by" not in entry:
            entry["consumed_by"] = None

        # 计算优先级
        entry["priority_score"] = _calc_priority_score(entry)

        # 计算 creator_match（使用缓存）
        signals = entry.get("signals", {})
        if signals:
            try:
                # 延迟导入避免循环
                from cognitive_crack import learn_thinking_pattern, compute_creator_match
                import time
                now = time.time()
                if (_CREATOR_MODEL_CACHE is None or
                        now - _CREATOR_MODEL_CACHE.get("_ts", 0) > _CREATOR_MODEL_CACHE_TTL):
                    _CREATOR_MODEL_CACHE = learn_thinking_pattern(history_limit=20)
                    _CREATOR_MODEL_CACHE["_ts"] = now
                creator_model = {k: v for k, v in _CREATOR_MODEL_CACHE.items() if not k.startswith("_")}
                creator_match = compute_creator_match(entry, creator_model)
                entry["creator_match"] = creator_match
            except Exception:
                pass  # creator_match 计算失败不影响写入

        entries = self._load_queue()

        # 检查容量，清理最老的 consumed/dismissed 条目
        if len(entries) >= MAX_QUEUE_SIZE:
            self._cleanup(keep_new=True)

        entries.append(entry)
        self._save_queue(entries)
        return entry["id"]

    def get(self, entry_id: str) -> Optional[Dict]:
        """根据 ID 获取条目"""
        entries = self._load_queue()
        for e in entries:
            if e.get("id") == entry_id:
                return e
        return None

    def list_all(self, status_filter: Optional[str] = None) -> List[Dict]:
        """列出所有条目，可选状态过滤"""
        entries = self._load_queue()
        if status_filter:
            entries = [e for e in entries if e.get("status") == status_filter]
        entries.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return entries

    def list_active(self) -> List[Dict]:
        """列出 new + reviewed 条目（待消费）"""
        entries = self._load_queue()
        active = [e for e in entries if e.get("status") in ("new", "reviewed")]
        active.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return active

    def tag(self, entry_id: str, tag: str) -> bool:
        """给条目打标签"""
        entries = self._load_queue()
        for e in entries:
            if e.get("id") == entry_id:
                tags = e.get("manual_tags", [])
                if tag not in tags:
                    tags.append(tag)
                    e["manual_tags"] = tags
                    e["priority_score"] = _calc_priority_score(e)
                self._save_queue(entries)
                return True
        return False

    def untag(self, entry_id: str, tag: str) -> bool:
        """移除标签"""
        entries = self._load_queue()
        for e in entries:
            if e.get("id") == entry_id:
                tags = e.get("manual_tags", [])
                if tag in tags:
                    tags.remove(tag)
                    e["manual_tags"] = tags
                    e["priority_score"] = _calc_priority_score(e)
                self._save_queue(entries)
                return True
        return False

    def set_status(self, entry_id: str, status: str) -> bool:
        """设置条目状态"""
        valid_statuses = {"new", "reviewed", "consumed", "dismissed"}
        if status not in valid_statuses:
            return False
        entries = self._load_queue()
        for e in entries:
            if e.get("id") == entry_id:
                e["status"] = status
                self._save_queue(entries)
                return True
        return False

    def dismiss(self, entry_id: str) -> bool:
        """标记为 dismissed，直接删除不归档"""
        entries = self._load_queue()
        new_entries = [e for e in entries if e.get("id") != entry_id]
        if len(new_entries) < len(entries):
            self._save_queue(new_entries)
            return True
        return False

    def mark_consumed(self, entry_id: str, consumed_by: str) -> bool:
        """标记为已消费"""
        entries = self._load_queue()
        for e in entries:
            if e.get("id") == entry_id:
                e["status"] = "consumed"
                e["consumed_by"] = consumed_by
                self._save_queue(entries)
                return True
        return False

    def search(self, keyword: str) -> List[Dict]:
        """标题关键词搜索"""
        entries = self._load_queue()
        keyword_lower = keyword.lower()
        results = []
        for e in entries:
            title = e.get("title", "").lower()
            consensus = e.get("consensus", "").lower()
            if keyword_lower in title or keyword_lower in consensus:
                results.append(e)
        results.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return results

    # ============ 内部方法 ============

    def _cleanup(self, keep_new: bool = True):
        """清理过期条目（consumed/dismissed 优先清理）"""
        entries = self._load_queue()

        # 按 priority_score 升序排列，最低的在最前面
        entries.sort(key=lambda x: x.get("priority_score", 0))

        # 优先删除 consumed/dismissed
        kept = [e for e in entries if e.get("status") in ("new", "reviewed")]

        # 如果还不够，删除最老的 consumed
        if len(kept) >= MAX_QUEUE_SIZE:
            kept = kept[:MAX_QUEUE_SIZE]

        self._save_queue(kept)

    def archive_old(self) -> int:
        """归档超过 ARCHIVE_AFTER_DAYS 的 consumed 条目"""
        entries = self._load_queue()
        now = datetime.now()
        to_archive = []
        to_keep = []

        for e in entries:
            if e.get("status") == "consumed":
                try:
                    created = datetime.fromisoformat(e.get("created_at", "").replace("Z", "+00:00"))
                    days = (now - created).days
                    if days >= ARCHIVE_AFTER_DAYS:
                        to_archive.append(e)
                    else:
                        to_keep.append(e)
                except Exception:
                    to_keep.append(e)
            else:
                to_keep.append(e)

        if to_archive:
            archive = self._load_archive()
            archive.extend(to_archive)
            self._save_archive(archive)
            self._save_queue(to_keep)

        return len(to_archive)

    def count(self) -> Tuple[int, int]:
        """返回 (active_count, total_count)"""
        entries = self._load_queue()
        active = len([e for e in entries if e.get("status") in ("new", "reviewed")])
        return active, len(entries)

    # ============ 归档查询 ============

    def search_archive(self, keyword: str, limit: int = 10) -> List[Dict]:
        """
        在归档中搜索关键词（标题/consensus）

        Args:
            keyword: 搜索关键词
            limit: 返回条数限制

        Returns:
            匹配的归档条目列表（按 priority_score 降序）
        """
        archive = self._load_archive()
        if not archive or not keyword:
            return []
        keyword_lower = keyword.lower()
        results = []
        for e in archive:
            title = e.get("title", "").lower()
            consensus = e.get("consensus", "").lower()
            if keyword_lower in title or keyword_lower in consensus:
                results.append(e)
        results.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return results[:limit]

    def query_trends(self, current_crack: Dict, limit: int = 5) -> List[Dict]:
        """
        趋势感知：查询归档中与当前裂缝主题相似的条目
        用于发现"这个话题是否已经同质化了"

        Args:
            current_crack: 当前裂缝条目（含 title/signals）
            limit: 返回条数限制

        Returns:
            相似的归档条目列表
        """
        archive = self._load_archive()
        if not archive:
            return []

        title = current_crack.get("title", "")
        signals = current_crack.get("signals", {})
        trend = signals.get("trend", "")

        # 简单关键词匹配
        search_terms = [title] + [trend] if trend else [title]
        results = []
        for e in archive:
            e_title = e.get("title", "")
            e_signals = e.get("signals", {})
            e_trend = e_signals.get("trend", "")
            # 标题或趋势关键词重叠
            match = any(term.lower() in e_title.lower() or e_title.lower() in term.lower()
                        for term in search_terms if term)
            if match:
                results.append(e)

        # 按创建时间降序（最新的相似话题在前）
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    # ============ 格式化输出 ============

    def format_entry(self, e: Dict, index: int) -> str:
        """格式化单个条目为可读字符串"""
        crack_type = e.get("crack_type", "未知")
        confidence = e.get("confidence", 0)
        priority = e.get("priority_score", 0)
        status = e.get("status", "new")
        tags = e.get("manual_tags", [])
        signals = e.get("signals", {})
        expression_angles = e.get("expression_angles", [])

        # 基础信息
        lines = []
        lines.append(f"[{index}] {e.get('title', '')}")
        lines.append(f"     裂缝类型: {crack_type} | 置信度: {confidence:.0%} | 优先级: {priority:.2f} | 状态: {status}")

        # 标签
        if tags:
            lines.append(f"     标签: {', '.join(tags)}")

        # signals
        if signals:
            trend = signals.get("trend", "")
            emotions = signals.get("emotion", [])
            contradiction = signals.get("contradiction", "")
            homo_alert = signals.get("homogenization_alert", "")
            if trend:
                lines.append(f"     信号: {trend}")
            if emotions:
                lines.append(f"     情绪: {'/'.join(emotions)}")
            if contradiction:
                lines.append(f"     矛盾: {contradiction}")
            if homo_alert and homo_alert != "不确定":
                lines.append(f"     同质化预警: {homo_alert}")

        # expression_angles
        if expression_angles:
            angles_str = " | ".join([f"{a.get('type','')}→{a.get('angle','')[:20]}" for a in expression_angles[:2]])
            lines.append(f"     表达入口: {angles_str}")

        return "\n".join(lines)

    def format_summary(self) -> str:
        """输出队列摘要"""
        active, total = self.count()
        lines = []
        lines.append(f"队列统计：{active} 条待消费（new/reviewed），共 {total} 条")
        return "\n".join(lines)


# ============ CLI 入口 ============


def main():
    import argparse

    parser = argparse.ArgumentParser(description="crack_queue — 选题情报员队列管理")
    subparsers = parser.add_subparsers(dest="command")

    # --list
    list_parser = subparsers.add_parser("list", help="列出队列中的条目")
    list_parser.add_argument("--status", "-s", help="按状态过滤 (new/reviewed/consumed/dismissed)")
    list_parser.add_argument("--limit", "-l", type=int, default=20, help="最大显示条数（默认20）")

    # --list-active
    subparsers.add_parser("active", help="列出待消费的条目（new + reviewed）")

    # --tag
    tag_parser = subparsers.add_parser("tag", help="给条目打标签")
    tag_parser.add_argument("id", help="条目ID")
    tag_parser.add_argument("label", help="标签内容")

    # --untag
    untag_parser = subparsers.add_parser("untag", help="移除标签")
    untag_parser.add_argument("id", help="条目ID")
    untag_parser.add_argument("label", help="标签内容")

    # --status
    status_parser = subparsers.add_parser("set-status", help="设置条目状态")
    status_parser.add_argument("id", help="条目ID")
    status_parser.add_argument("status", choices=["new", "reviewed", "consumed", "dismissed"], help="状态")

    # --dismiss
    dismiss_parser = subparsers.add_parser("dismiss", help="标记为 dismissal（直接删除）")
    dismiss_parser.add_argument("id", help="条目ID")

    # --search
    search_parser = subparsers.add_parser("search", help="搜索条目")
    search_parser.add_argument("keyword", help="搜索关键词")

    # --archive
    subparsers.add_parser("archive", help="归档过期 consumed 条目")

    # --search-archive
    search_archive_parser = subparsers.add_parser("search-archive", help="在归档中搜索关键词")
    search_archive_parser.add_argument("keyword", help="搜索关键词")
    search_archive_parser.add_argument("--limit", "-l", type=int, default=10, help="返回条数限制")

    # --trends
    trends_parser = subparsers.add_parser("trends", help="查询与给定标题相似的归档趋势")
    trends_parser.add_argument("title", help="当前裂缝标题")
    trends_parser.add_argument("--limit", "-l", type=int, default=5, help="返回条数限制")

    # --stats
    subparsers.add_parser("stats", help="显示队列统计")

    args = parser.parse_args()
    q = CrackQueue()

    if args.command == "list":
        entries = q.list_all(args.status) if args.status else q.list_all()
        if not entries:
            print("队列为空")
            return
        print(f"共 {len(entries)} 条\n")
        for i, e in enumerate(entries[: args.limit], 1):
            print(q.format_entry(e, i))
            print()

    elif args.command == "active":
        entries = q.list_active()
        if not entries:
            print("没有待消费的条目")
            return
        print(f"待消费条目 {len(entries)} 条\n")
        for i, e in enumerate(entries[: args.limit], 1):
            print(q.format_entry(e, i))
            print()

    elif args.command == "tag":
        if q.tag(args.id, args.label):
            print(f"已添加标签: {args.label}")
        else:
            print(f"未找到条目: {args.id}")

    elif args.command == "untag":
        if q.untag(args.id, args.label):
            print(f"已移除标签: {args.label}")
        else:
            print(f"未找到条目: {args.id}")

    elif args.command == "set-status":
        if q.set_status(args.id, args.status):
            print(f"已设置状态: {args.status}")
        else:
            print(f"未找到条目: {args.id}")

    elif args.command == "dismiss":
        if q.dismiss(args.id):
            print("已删除")
        else:
            print(f"未找到条目: {args.id}")

    elif args.command == "search":
        results = q.search(args.keyword)
        if not results:
            print(f"未找到包含 '{args.keyword}' 的条目")
            return
        print(f"找到 {len(results)} 条\n")
        for i, e in enumerate(results[: args.limit], 1):
            print(q.format_entry(e, i))
            print()

    elif args.command == "archive":
        count = q.archive_old()
        print(f"已归档 {count} 条")

    elif args.command == "search-archive":
        results = q.search_archive(args.keyword, limit=args.limit)
        if not results:
            print(f"归档中未找到包含 '{args.keyword}' 的条目")
            return
        print(f"归档中找到 {len(results)} 条\n")
        for i, e in enumerate(results, 1):
            title = e.get("title", "")
            crack_type = e.get("crack_type", "")
            created = e.get("created_at", "")[:10]
            print(f"[{i}] {title}")
            print(f"    类型: {crack_type} | 归档时间: {created}")
            print()

    elif args.command == "trends":
        current = {"title": args.title, "signals": {}}
        results = q.query_trends(current, limit=args.limit)
        if not results:
            print("归档中未找到相似话题")
            return
        print(f"归档中找到 {len(results)} 条相似话题\n")
        for i, e in enumerate(results, 1):
            title = e.get("title", "")
            crack_type = e.get("crack_type", "")
            signals = e.get("signals", {})
            trend = signals.get("trend", "")
            created = e.get("created_at", "")[:10]
            print(f"[{i}] {title}")
            print(f"    类型: {crack_type} | 归档时间: {created}")
            if trend:
                print(f"    趋势: {trend[:40]}...")
            print()

    elif args.command == "stats":
        print(q.format_summary())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()