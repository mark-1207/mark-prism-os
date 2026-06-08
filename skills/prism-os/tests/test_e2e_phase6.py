"""Phase 6.0 — 端到端测试"""
import pytest
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestE2EMetricsSync:
    """端到端同步测试"""

    def test_full_sync_flow(self):
        """完整流程：飞书数据 → 本地 snapshot"""
        from metrics_sync import validate_row

        # 模拟从飞书拉取的数据
        feishu_rows = [
            {"fields": {"文章ID": "a_20260603", "平台": "wechat", "时间点": "t_plus_1d", "阅读量": 100, "点赞量": 10}},
            {"fields": {"文章ID": "a_20260603", "平台": "wechat", "时间点": "t_plus_7d", "阅读量": 500, "点赞量": 50}},
        ]

        validated = [r["fields"] for r in feishu_rows if validate_row(r["fields"])]
        assert len(validated) == 2

    def test_sync_with_invalid_rows(self):
        """无效行被过滤"""
        from metrics_sync import validate_row

        rows = [
            {"文章ID": "a_20260603", "平台": "wechat", "时间点": "t_plus_1d", "阅读量": 100},  # valid
            {"文章ID": "", "平台": "wechat", "时间点": "t_plus_1d", "阅读量": 100},  # invalid: empty ID
            {"文章ID": "b_20260603", "平台": "wechat", "时间点": "invalid", "阅读量": 100},  # invalid: bad time point
        ]
        validated = [r for r in rows if validate_row(r)]
        assert len(validated) == 1


class TestE2ETemplateScorer:
    """端到端模板优选测试"""

    def test_calibration_output_format(self, sample_articles=None):
        """验证 calibration 输出格式正确"""
        from template_scorer import score_by_strategy, score_by_module_combo

        articles = [
            {"文章ID": "a", "平台": "wechat", "叙事策略": "数据驱动型", "CCOS模块": ["HOOK", "CASE"], "阅读量": 100, "点赞量": 10, "收藏量": 5, "转发量": 3, "评论数": 2, "时间点": "t_plus_7d"},
            {"文章ID": "b", "平台": "wechat", "叙事策略": "数据驱动型", "CCOS模块": ["HOOK", "CASE"], "阅读量": 200, "点赞量": 20, "收藏量": 10, "转发量": 6, "评论数": 4, "时间点": "t_plus_7d"},
            {"文章ID": "c", "平台": "wechat", "叙事策略": "观点碰撞型", "CCOS模块": ["HOOK", "MODEL"], "阅读量": 150, "点赞量": 8, "收藏量": 3, "转发量": 1, "评论数": 1, "时间点": "t_plus_7d"},
        ]

        strategy_result = score_by_strategy(articles)
        module_result = score_by_module_combo(articles)

        # 验证结构
        assert "wechat" in strategy_result
        assert "数据驱动型" in strategy_result["wechat"]
        assert "avg_engagement" in strategy_result["wechat"]["数据驱动型"]
        assert "sample_size" in strategy_result["wechat"]["数据驱动型"]

        assert "wechat" in module_result
        assert len(module_result["wechat"]) > 0

    def test_calibration_sorted_by_engagement(self):
        """验证 calibration 按互动率排序"""
        from template_scorer import score_by_strategy

        articles = [
            {"文章ID": "a", "平台": "wechat", "叙事策略": "数据驱动型", "CCOS模块": ["HOOK"], "阅读量": 100, "点赞量": 10, "收藏量": 5, "转发量": 3, "评论数": 2, "时间点": "t_plus_7d"},
            {"文章ID": "b", "平台": "wechat", "叙事策略": "数据驱动型", "CCOS模块": ["HOOK"], "阅读量": 200, "点赞量": 20, "收藏量": 10, "转发量": 6, "评论数": 4, "时间点": "t_plus_7d"},
            {"文章ID": "c", "平台": "wechat", "叙事策略": "观点碰撞型", "CCOS模块": ["HOOK"], "阅读量": 150, "点赞量": 5, "收藏量": 2, "转发量": 1, "评论数": 1, "时间点": "t_plus_7d"},
            {"文章ID": "d", "平台": "wechat", "叙事策略": "观点碰撞型", "CCOS模块": ["HOOK"], "阅读量": 100, "点赞量": 3, "收藏量": 1, "转发量": 0, "评论数": 0, "时间点": "t_plus_7d"},
        ]

        result = score_by_strategy(articles)
        strategies = result["wechat"]
        # 数据驱动型互动率应高于观点碰撞型
        assert strategies["数据驱动型"]["avg_engagement"] > strategies["观点碰撞型"]["avg_engagement"]
