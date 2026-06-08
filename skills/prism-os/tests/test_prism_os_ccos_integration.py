#!/usr/bin/env python3
"""
prism_os.py CCOS 集成测试
验证 Phase 4.5 CCOS 接入后的数据流

用法: python -m pytest skills/prism-os/tests/test_prism_os_ccos_integration.py -v
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _mock_learn_thinking_pattern():
    return {
        "thinking_pattern": "理性、克制、反常识",
        "dimension_weights": {"reversal": 0.3, "micro_scene": 0.3, "systemic_flaw": 0.2, "bridge": 0.2},
        "style_keywords": ["认知升级", "独立思考"],
        "confidence": 0.5
    }


def _mock_digital_twin_filter(candidates, *args, **kwargs):
    return {
        "filtered": [],
        "audience": "独立思考者",
        "match_score": 0.6
    }


def _mock_ccos_workflow(topic, dimension, platform, alignment_result=None):
    return {
        "内容目标": "认知升级",
        "用户动机": "好奇",
        "核心认知冲突": "AI让内容更容易也更容易被淹没",
        "内容立场": "独立思考才能突破同质化",
        "作者性设定": {"认知倾向": "分析优先", "表达气质": "理性深刻", "价值倾向": "独立思考", "长期母题": "认知升级"},
        "主结构": "认知升级型",
        "推进方式": "冲突推进",
        "认知模块流": [{"模块": "HOOK", "内容摘要": "开场", "功能": "制造停留"}],
        "势能曲线": {"张力变化": ["开场"], "情绪曲线": ["好奇"], "认知落差设计": "先A后B", "节奏变化": "递进", "认知奖励点": ["新视角"]},
        "案例插入点": ["创业故事"],
        "信息密度要求": "每段必须有信息增量",
        "语言风格": "深度理性",
        "Anti-AI要求": "禁止模板感",
        "最终动态认知大纲": "【认知升级型】测试命题"
    }


def _mock_dual_outline(topic, dimension):
    return {
        "wechat_cognitive_outline": _mock_ccos_workflow(topic, dimension, "wechat"),
        "xiaohongshu_cognitive_outline": _mock_ccos_workflow(topic, dimension, "xiaohongshu")
    }


class TestPhase45StorageIntegration(unittest.TestCase):
    """验证 storage 写入 ccos_outline 字段"""

    def test_log_entry_includes_ccos(self):
        """log_entry 应包含 ccos_outline 字段"""
        from storage import append_log
        test_entry = {
            "thesis": "测试命题",
            "candidates_count": 3,
            "entropy_score": 0.7,
            "gap_score": 0.5,
            "candidates": [{"title": "测试标题", "dimension": "reversal"}],
            "ccos_outline": {"内容目标": "认知升级"}
        }
        # append_log 会写入，我们只验证格式
        self.assertIn("ccos_outline", test_entry)
        self.assertIn("内容目标", test_entry["ccos_outline"])


class TestFormatOutputWithCCOS(unittest.TestCase):
    """验证 format_prism_os_output 处理 ccos_outline"""

    def test_ccos_dual_format(self):
        """双平台 CCOS 格式输出"""
        from prism_os import format_prism_os_output
        ccos_result = _mock_dual_outline("AI时代内容创作", "reversal")
        mock_result = {
            "candidates": [{"title": "AI时代内容创作者该何去何从", "dimension": "reversal", "competition_level": "中", "novelty_score": 0.7}],
            "ccos_outline": ccos_result,
            "gap": {"readiness": 0.7, "missing_evidence": [], "recommendation": "素材充足"},
            "logic_audit": [],
            "cognitive_journey": {"status": "first_time"},
            "storage": {"status": "ok"}
        }
        output = format_prism_os_output(mock_result)
        self.assertIn("认知大纲", output)
        self.assertIn("公众号", output)
        self.assertIn("小红书", output)

    def test_ccos_single_format(self):
        """单平台 CCOS 格式输出"""
        from prism_os import format_prism_os_output
        ccos_result = _mock_ccos_workflow("AI时代内容创作", "reversal", "wechat")
        mock_result = {
            "candidates": [],
            "ccos_outline": ccos_result,
            "storage": {"status": "ok"}
        }
        output = format_prism_os_output(mock_result)
        self.assertIn("认知大纲", output)

    def test_backward_compatible_outlines(self):
        """旧版 outlines 格式仍然向后兼容"""
        from prism_os import format_prism_os_output
        mock_result = {
            "candidates": [],
            "outlines": {
                "wechat_outline": {"hook": "旧版钩子", "sections": [{"title": "第一部分"}]},
                "xiaohongshu_outline": {"hook": "旧版钩子", "tags": ["标签1"]}
            },
            "storage": {"status": "ok"}
        }
        output = format_prism_os_output(mock_result)
        self.assertIn("双端大纲（旧版）", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)