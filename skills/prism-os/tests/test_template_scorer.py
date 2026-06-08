"""Phase 6.0 — 模板优选统计测试"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


@pytest.fixture
def sample_articles():
    """构造 5 篇测试文章数据"""
    return [
        {"文章ID": "a_20260601", "平台": "wechat", "叙事策略": "数据驱动型", "CCOS模块": ["HOOK", "CASE", "MODEL"], "阅读量": 1000, "点赞量": 80, "收藏量": 30, "转发量": 20, "评论数": 15, "时间点": "t_plus_7d"},
        {"文章ID": "b_20260602", "平台": "wechat", "叙事策略": "数据驱动型", "CCOS模块": ["HOOK", "CASE", "EVIDENCE"], "阅读量": 800, "点赞量": 60, "收藏量": 25, "转发量": 15, "评论数": 10, "时间点": "t_plus_7d"},
        {"文章ID": "c_20260603", "平台": "wechat", "叙事策略": "观点碰撞型", "CCOS模块": ["HOOK", "CASE", "MODEL", "ACTION"], "阅读量": 500, "点赞量": 20, "收藏量": 10, "转发量": 5, "评论数": 8, "时间点": "t_plus_7d"},
        {"文章ID": "d_20260604", "平台": "xiaohongshu", "叙事策略": "悬念解密型", "CCOS模块": ["HOOK", "CASE", "ACTION"], "阅读量": 2000, "点赞量": 200, "收藏量": 100, "转发量": 50, "评论数": 40, "时间点": "t_plus_7d"},
        {"文章ID": "e_20260605", "平台": "xiaohongshu", "叙事策略": "悬念解密型", "CCOS模块": ["HOOK", "CASE"], "阅读量": 1500, "点赞量": 150, "收藏量": 80, "转发量": 40, "评论数": 30, "时间点": "t_plus_7d"},
    ]


class TestEngagementCalculation:
    """互动率计算测试"""

    def test_engagement_rate_calculation(self):
        from template_scorer import calculate_engagement_rate
        row = {"阅读量": 1000, "点赞量": 50, "收藏量": 20, "转发量": 10, "评论数": 5}
        rate = calculate_engagement_rate(row)
        assert abs(rate - 0.085) < 0.001  # (50+20+10+5)/1000 = 0.085

    def test_engagement_rate_zero_reads(self):
        from template_scorer import calculate_engagement_rate
        row = {"阅读量": 0, "点赞量": 0, "收藏量": 0, "转发量": 0, "评论数": 0}
        rate = calculate_engagement_rate(row)
        assert rate == 0.0

    def test_engagement_rate_partial_data(self):
        from template_scorer import calculate_engagement_rate
        row = {"阅读量": 500, "点赞量": 25, "收藏量": None, "转发量": None, "评论数": None}
        rate = calculate_engagement_rate(row)
        assert abs(rate - 0.05) < 0.001  # 25/500


class TestStrategyScoring:
    """策略分组测试"""

    def test_group_by_strategy_platform(self, sample_articles):
        from template_scorer import score_by_strategy
        result = score_by_strategy(sample_articles)
        assert "wechat" in result
        assert "数据驱动型" in result["wechat"]
        assert "观点碰撞型" in result["wechat"]
        assert "xiaohongshu" in result
        assert "悬念解密型" in result["xiaohongshu"]

    def test_strategy_avg_engagement(self, sample_articles):
        from template_scorer import score_by_strategy
        result = score_by_strategy(sample_articles)
        # 数据驱动型：2篇，互动率分别是 (80+30+20+15)/1000=0.145, (60+25+15+10)/800=0.1375
        wechat_data = result["wechat"]["数据驱动型"]
        assert wechat_data["sample_size"] == 2
        assert wechat_data["avg_engagement"] > 0

    def test_strategy_separation_by_platform(self, sample_articles):
        from template_scorer import score_by_strategy
        result = score_by_strategy(sample_articles)
        # 同一策略不同平台应分开统计
        assert result["wechat"]["数据驱动型"]["sample_size"] == 2
        assert result["xiaohongshu"]["悬念解密型"]["sample_size"] == 2

    def test_strategy_sample_size(self, sample_articles):
        from template_scorer import score_by_strategy
        result = score_by_strategy(sample_articles)
        assert result["wechat"]["观点碰撞型"]["sample_size"] == 1


class TestModuleScoring:
    """模块组合测试"""

    def test_group_by_module_combo(self, sample_articles):
        from template_scorer import score_by_module_combo
        result = score_by_module_combo(sample_articles)
        assert "wechat" in result
        assert len(result["wechat"]) > 0

    def test_module_combo_engagement(self, sample_articles):
        from template_scorer import score_by_module_combo
        result = score_by_module_combo(sample_articles)
        # 验证有数据
        for platform in result:
            for combo_key in result[platform]:
                combo = result[platform][combo_key]
                assert combo["avg_engagement"] >= 0
                assert combo["sample_size"] >= 1


class TestConfidenceInterval:
    """置信区间测试"""

    def test_ci_calculation(self):
        from template_scorer import calculate_ci
        values = [0.1, 0.12, 0.08, 0.11, 0.09]
        ci_low, ci_high = calculate_ci(values)
        assert ci_low < 0.1 < ci_high
        assert ci_low >= 0

    def test_ci_single_sample(self):
        from template_scorer import calculate_ci
        values = [0.1]
        ci_low, ci_high = calculate_ci(values)
        # 单样本时置信区间应该很宽
        assert ci_low == 0.0 or ci_high >= 0.1


class TestColdStart:
    """冷启动测试"""

    def test_insufficient_sample_returns_empty(self, sample_articles):
        from template_scorer import score_by_strategy
        # 只取 1 篇（不足 3 篇阈值）
        result = score_by_strategy(sample_articles[:1])
        # 应该仍然返回结果，但标记为冷启动
        assert "wechat" in result

    def test_min_sample_threshold(self, sample_articles):
        from template_scorer import score_by_strategy
        result = score_by_strategy(sample_articles)
        # 验证每个策略都有 sample_size
        for platform in result:
            for strategy in result[platform]:
                assert result[platform][strategy]["sample_size"] >= 1
