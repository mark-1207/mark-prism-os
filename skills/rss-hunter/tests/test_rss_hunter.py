#!/usr/bin/env python3
"""
RSS-Hunter 单元测试
覆盖纯逻辑函数，不依赖外部服务
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 设置路径
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from obsidian_writer import (
    _sanitize_filename,
    _build_frontmatter,
    write_crack,
    write_item,
)
from rss_hunter import _build_push_message, _get_source_tags


# ============ obsidian_writer 测试 ============

class TestSanitizeFilename:
    def test_normal_title(self):
        assert _sanitize_filename("AI 让程序员失业") == "AI 让程序员失业"

    def test_windows_forbidden_chars(self):
        result = _sanitize_filename('Test: <invalid> chars?')
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '?' not in result
        assert 'Test' in result
        assert 'invalid' in result

    def test_long_title_truncated(self):
        long_title = "A" * 200
        result = _sanitize_filename(long_title, max_len=80)
        assert len(result) <= 80

    def test_empty_title(self):
        assert _sanitize_filename("") == "untitled"

    def test_whitespace_normalized(self):
        result = _sanitize_filename("  hello   world  ")
        assert result == "hello world"

    def test_newline_removed(self):
        result = _sanitize_filename("hello\nworld")
        assert "\n" not in result
        assert "hello" in result


class TestBuildFrontmatter:
    def test_basic_fields(self):
        fm = _build_frontmatter({"type": "insight", "status": "active"})
        assert "---" in fm
        assert "type: insight" in fm
        assert "status: active" in fm

    def test_list_field(self):
        fm = _build_frontmatter({"topics": ["AI", "科技"]})
        assert "topics: [AI, 科技]" in fm

    def test_int_field(self):
        fm = _build_frontmatter({"confidence": 8})
        assert "confidence: 8" in fm


class TestWriteObsidian:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_crack_creates_file(self):
        result = write_crack(
            title="Test Crack",
            summary="Test summary",
            source="36氪",
            category="ai",
            tags=["AI"],
            url="https://example.com",
            crack_type="数据裂缝",
            confidence=0.85,
            consensus="AI 会创造就业",
            reality="AI 导致失业",
            vault_path=self.tmpdir,
        )
        assert result is not None
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "数据裂缝" in content
        assert "Test Crack" in content
        assert "AI 会创造就业" in content
        assert "type: insight" in content
        assert "confidence: 8" in content  # 0.85 * 10 = 8.5, round(8.5) = 8 (banker's rounding)
        assert "核心观点" in content
        assert "洞察来源" in content
        assert "洞察形成逻辑" in content

    def test_write_item_creates_file(self):
        result = write_item(
            title="Test Item",
            summary="Test summary",
            source="36氪",
            category="ai",
            tags=["AI"],
            url="https://example.com",
            vault_path=self.tmpdir,
        )
        assert result is not None
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "Test Item" in content
        assert "type: atom" in content
        assert "subtype: viewpoint" in content
        assert "原子内容" in content
        assert "来源" in content
        assert "source_note: 36氪" in content
        assert "source_url: https://example.com" in content

    def test_write_creates_directory(self):
        nested = self.tmpdir / "deep" / "nested" / "path"
        result = write_item(
            title="Test",
            summary="Test",
            source="test",
            category="test",
            tags=[],
            url="",
            vault_path=nested,
        )
        assert result is not None
        assert result.exists()


# ============ rss_hunter 测试 ============

class TestBuildPushMessage:
    def test_basic_message(self):
        crack_info = {
            "consensus": "AI 会创造就业",
            "reality": "AI 导致失业",
            "crack_type": "数据裂缝",
            "confidence": 0.85,
            "title_suggestions": ["为什么AI就业数据是错的？"],
        }
        msg = _build_push_message(crack_info, "36氪", "Test Title", "https://example.com")
        assert "数据裂缝" in msg
        assert "85%" in msg
        assert "36氪" in msg
        assert "Test Title" in msg
        assert "AI 会创造就业" in msg
        assert "为什么AI就业数据是错的" in msg

    def test_no_suggestions(self):
        crack_info = {
            "consensus": "test",
            "reality": "test",
            "crack_type": "逻辑裂缝",
            "confidence": 0.75,
            "title_suggestions": [],
        }
        msg = _build_push_message(crack_info, "source", "title", "")
        assert "建议选题" not in msg

    def test_empty_link(self):
        crack_info = {
            "consensus": "test",
            "reality": "test",
            "crack_type": "时效裂缝",
            "confidence": 0.8,
        }
        msg = _build_push_message(crack_info, "source", "title", "")
        assert "链接" not in msg


class TestGetSourceTags:
    def test_with_category_and_tags(self):
        source = {"name": "36氪", "category": "ai", "tags": ["AI", "科技"]}
        cat, tags = _get_source_tags(source)
        assert cat == "ai"
        assert tags == ["AI", "科技"]

    def test_fallback_to_region(self):
        source = {"name": "HN", "region": "intl"}
        cat, tags = _get_source_tags(source)
        assert cat == "intl"
        assert tags == ["intl"]

    def test_empty_source(self):
        source = {"name": "test"}
        cat, tags = _get_source_tags(source)
        assert cat == "general"
        assert tags == ["general"]


# ============ 运行 ============

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
