"""Phase 6.1 — Calibration 接入 narrate 测试"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestCalibrationBoost:
    """calibration boost 计算测试"""

    def test_no_calibration_returns_zero(self):
        from content_generator import compute_calibration_boost
        assert compute_calibration_boost(None, "wechat", "数据驱动型") == 0.0

    def test_no_platform_data_returns_zero(self):
        from content_generator import compute_calibration_boost
        cal = {"by_platform_strategy": {"xiaohongshu": {}}}
        assert compute_calibration_boost(cal, "wechat", "数据驱动型") == 0.0

    def test_insufficient_sample_returns_zero(self):
        from content_generator import compute_calibration_boost
        cal = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.20, "sample_size": 2}
                }
            }
        }
        assert compute_calibration_boost(cal, "wechat", "数据驱动型") == 0.0

    def test_sufficient_sample_positive_boost(self):
        from content_generator import compute_calibration_boost
        cal = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.20, "sample_size": 5},
                    "观点碰撞型": {"avg_engagement": 0.05, "sample_size": 5}
                }
            }
        }
        boost = compute_calibration_boost(cal, "wechat", "数据驱动型")
        assert boost > 0

    def test_low_performance_negative_boost(self):
        from content_generator import compute_calibration_boost
        cal = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.02, "sample_size": 5},
                    "观点碰撞型": {"avg_engagement": 0.10, "sample_size": 5}
                }
            }
        }
        boost = compute_calibration_boost(cal, "wechat", "数据驱动型")
        assert boost < 0

    def test_large_sample_extra_boost(self):
        from content_generator import compute_calibration_boost
        cal_small = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.20, "sample_size": 5},
                    "观点碰撞型": {"avg_engagement": 0.05, "sample_size": 5}
                }
            }
        }
        cal_large = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.20, "sample_size": 15},
                    "观点碰撞型": {"avg_engagement": 0.05, "sample_size": 15}
                }
            }
        }
        boost_small = compute_calibration_boost(cal_small, "wechat", "数据驱动型")
        boost_large = compute_calibration_boost(cal_large, "wechat", "数据驱动型")
        assert boost_large > boost_small

    def test_boost_capped(self):
        """boost 有上限，避免单策略压制其他"""
        from content_generator import compute_calibration_boost
        # 极端情况：数据驱动型 50% 互动率 vs 其他 0%
        cal = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.50, "sample_size": 20},
                    "观点碰撞型": {"avg_engagement": 0.01, "sample_size": 20},
                    "人物线索型": {"avg_engagement": 0.01, "sample_size": 20}
                }
            }
        }
        boost = compute_calibration_boost(cal, "wechat", "数据驱动型")
        # 不应该超过封顶值（假设 5）
        assert boost <= 5.0


class TestStrategySelectionWithCalibration:
    """策略选择测试"""

    def test_high_performance_strategy_selected(self):
        """高表现策略应被优先选"""
        from content_generator import evaluate_narrative_strategy

        # 准备 CCOS 大纲，让关键词评分倾向"观点碰撞型"
        ccos = {
            "主结构": "认知升级型",
            "内容目标": "认知升级",
            "认知模块流": []
        }
        # 准备素材
        materials = [
            {"name": "正方观点1", "content": "认为这是一个重要的争议话题", "type": "viewpoint"},
            {"name": "反方观点1", "content": "另一方面持不同意见的人认为", "type": "viewpoint"},
        ]

        # 无 calibration：观点碰撞型可能胜出
        result_no_cal = evaluate_narrative_strategy(
            "测试命题", ccos, materials, [],
            calibration=None, platform="wechat"
        )

        # 有 calibration：数据驱动型历史表现好，应被推荐
        cal = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.25, "sample_size": 5},
                    "观点碰撞型": {"avg_engagement": 0.03, "sample_size": 5}
                }
            }
        }
        result_with_cal = evaluate_narrative_strategy(
            "测试命题", ccos, materials, [],
            calibration=cal, platform="wechat"
        )

        # 验证：加入 calibration 后，策略应该变化或分数有差异
        assert result_with_cal["scores"]["数据驱动型"] != result_no_cal["scores"]["数据驱动型"]
        assert result_with_cal["scores"]["数据驱动型"] > result_no_cal["scores"]["数据驱动型"]

    def test_no_calibration_unchanged_behavior(self):
        """无 calibration 时行为不变（向后兼容）"""
        from content_generator import evaluate_narrative_strategy

        ccos = {"主结构": "认知升级型", "内容目标": "认知升级"}
        materials = [
            {"name": "M1", "content": "故事 案例 人物", "type": "case"},
        ]

        # 多次跑，结果应一致
        r1 = evaluate_narrative_strategy("T", ccos, materials, [], calibration=None, platform="wechat")
        r2 = evaluate_narrative_strategy("T", ccos, materials, [], calibration=None, platform="wechat")
        assert r1["strategy"] == r2["strategy"]
        assert r1["scores"] == r2["scores"]


class TestE2EIntegration:
    """端到端集成测试"""

    def test_evaluate_accepts_calibration_param(self):
        """verify evaluate_narrative_strategy 接受 calibration 参数"""
        from content_generator import evaluate_narrative_strategy
        import inspect
        sig = inspect.signature(evaluate_narrative_strategy)
        assert "calibration" in sig.parameters
        assert "platform" in sig.parameters

    def test_evaluate_returns_calibration_boost_info(self):
        """结果应包含 calibration boost 信息（便于调试）"""
        from content_generator import evaluate_narrative_strategy

        cal = {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {"avg_engagement": 0.20, "sample_size": 5}
                }
            }
        }
        ccos = {"主结构": "认知升级型"}
        materials = []

        result = evaluate_narrative_strategy(
            "T", ccos, materials, [],
            calibration=cal, platform="wechat"
        )
        # 结果应包含 calibration 应用信息
        assert "calibration_applied" in result
        assert result["calibration_applied"] is True
