#!/usr/bin/env python3
"""
RSS-Hunter Obsidian 写入模块
将 RSS 条目（有裂缝/无裂缝）写入 Obsidian vault
格式严格遵循 99_系统/Template/ 中的模板规范

用法:
    from obsidian_writer import write_crack, write_item
"""

import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ============ 配置 ============

DEFAULT_VAULT_PATH = r"D:\软件\obsidian笔记\内容素材库"
CRACK_SUBDIR = "40_知识库/洞察库/rss-cracks"
ITEM_SUBDIR = "40_知识库/原子库/rss-items"


def _safe_print(text: str):
    """Windows GBK 安全输出"""
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")


def _get_vault_path() -> Path:
    """获取 Obsidian vault 路径（环境变量优先）"""
    import os
    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path)
    return Path(DEFAULT_VAULT_PATH)


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """将标题转为安全文件名"""
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    safe = re.sub(r'\s+', ' ', safe).strip()
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip()
    return safe or "untitled"


def _confidence_to_score(confidence: float) -> int:
    """将 0.0-1.0 置信度转为 1-10 整数评分"""
    return max(1, min(10, round(confidence * 10)))


def _build_frontmatter(fields: Dict) -> str:
    """生成 YAML frontmatter"""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
            else:
                lines.append(f"{key}: []")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def write_crack(
    title: str,
    summary: str,
    source: str,
    category: str,
    tags: List[str],
    url: str,
    crack_type: str,
    confidence: float,
    consensus: str,
    reality: str,
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """
    将有裂缝的条目写入 Obsidian 洞察库
    遵循 Insight_洞察模板.md 的 frontmatter 和 body 格式

    Args:
        title: 文章标题
        summary: 摘要内容
        source: 信源名称
        category: 分类
        tags: 标签列表
        url: 原文链接
        crack_type: 裂缝类型
        confidence: 置信度 (0.0-1.0)
        consensus: 共识
        reality: 现实
        vault_path: vault 路径（默认从环境变量或默认值）

    Returns:
        写入的文件路径，失败返回 None
    """
    if vault_path is None:
        vault_path = _get_vault_path()

    crack_dir = vault_path / CRACK_SUBDIR
    crack_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{_sanitize_filename(title)}.md"
    filepath = crack_dir / filename

    # topics: 合并 category + tags，去重
    topics = list(dict.fromkeys([category] + tags))

    # frontmatter 遵循洞察模板
    frontmatter = _build_frontmatter({
        "type": "insight",
        "status": "active",
        "topics": topics,
        "sub_topics": [crack_type],
        "source_file": source,
        "atoms_used": [],
        "linked_insights": [],
        "linked_goldens": [],
        "confidence": _confidence_to_score(confidence),
        "usage_count": 0,
        "created": today,
        "updated": today,
    })

    # body 遵循洞察模板结构
    content = f"""{frontmatter}
# {title}

## 核心观点
> {consensus} → {reality}

## 洞察来源
| 来源类型 | 来源ID | 说明 |
|---------|--------|------|
| RSS | {source} | [{title}]({url}) |

## 洞察形成逻辑
1. **前提**：{consensus}
2. **真相**：{reality}
3. **裂缝类型**：{crack_type}
4. **置信度**：{confidence * 100:.0f}%

## 内容摘要
{summary}

---
## 元信息
- 成熟度：active（新发现）
- 置信度：{_confidence_to_score(confidence)}/10
- 使用次数：0
"""

    try:
        filepath.write_text(content, encoding="utf-8")
        _safe_print(f"[写入] 洞察 → {filepath.name}")
        return filepath
    except Exception as e:
        _safe_print(f"[Error] 写入失败 {filepath}: {e}")
        return None


def write_item(
    title: str,
    summary: str,
    source: str,
    category: str,
    tags: List[str],
    url: str,
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """
    将无裂缝的条目写入 Obsidian 原子库
    遵循 Atom_原子模板.md 的 frontmatter 和 body 格式

    Args:
        title: 文章标题
        summary: 摘要内容
        source: 信源名称
        category: 分类
        tags: 标签列表
        url: 原文链接
        vault_path: vault 路径（默认从环境变量或默认值）

    Returns:
        写入的文件路径，失败返回 None
    """
    if vault_path is None:
        vault_path = _get_vault_path()

    item_dir = vault_path / ITEM_SUBDIR
    item_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{_sanitize_filename(title)}.md"
    filepath = item_dir / filename

    # topics: 合并 category + tags，去重
    topics = list(dict.fromkeys([category] + tags))

    # frontmatter 遵循原子模板
    frontmatter = _build_frontmatter({
        "type": "atom",
        "subtype": "viewpoint",
        "status": "active",
        "topics": topics,
        "source_note": source,
        "source_url": url,
        "linked_insights": [],
        "linked_goldens": [],
        "quality_score": 7,
        "usage_count": 0,
        "created": today,
        "updated": today,
    })

    # body 遵循原子模板结构
    content = f"""{frontmatter}
# {title}

## 原子内容
> {summary}

## 来源
- 信源：{source}
- 链接：[{title}]({url})
- 日期：{today}
"""

    try:
        filepath.write_text(content, encoding="utf-8")
        _safe_print(f"[写入] 原子 → {filepath.name}")
        return filepath
    except Exception as e:
        _safe_print(f"[Error] 写入失败 {filepath}: {e}")
        return None


# ============ CLI 测试 ============

if __name__ == "__main__":
    _safe_print("obsidian_writer.py - Obsidian 写入模块测试")

    _safe_print("\n[测试] _sanitize_filename...")
    _safe_print(f"  'AI 让程序员失业？' -> '{_sanitize_filename('AI 让程序员失业？')}'")
    _safe_print(f"  'Test: <invalid> chars' -> '{_sanitize_filename('Test: <invalid> chars')}'")

    _safe_print("\n[测试] _confidence_to_score...")
    _safe_print(f"  0.85 -> {_confidence_to_score(0.85)}")
    _safe_print(f"  0.5 -> {_confidence_to_score(0.5)}")
    _safe_print(f"  1.0 -> {_confidence_to_score(1.0)}")

    _safe_print("\n[测试] _build_frontmatter (洞察格式)...")
    fm = _build_frontmatter({
        "type": "insight",
        "status": "active",
        "topics": ["AI", "科技"],
        "confidence": 8,
        "usage_count": 0,
        "created": "2026-05-14",
        "updated": "2026-05-14",
    })
    _safe_print(fm)

    _safe_print("\n[测试] _build_frontmatter (原子格式)...")
    fm2 = _build_frontmatter({
        "type": "atom",
        "subtype": "viewpoint",
        "status": "active",
        "topics": ["AI", "科技"],
        "quality_score": 7,
        "created": "2026-05-14",
        "updated": "2026-05-14",
    })
    _safe_print(fm2)

    _safe_print("\n测试完成！")
