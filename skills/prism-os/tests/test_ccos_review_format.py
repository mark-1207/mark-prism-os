"""CCOS 审核格式测试"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_ccos_review_includes_stance():
    """_format_ccos_review 应包含立场字段"""
    from prism_os import _format_ccos_review
    outline = {
        "内容目标": "认知升级",
        "内容立场": "AI时代下裁员为何会成为常态化潜规则？",
        "核心认知冲突": "实际裁员可能是个别现象",
        "主结构": "认知升级型",
        "推进方式": "拆解推进",
        "认知模块流": [
            {"模块": "HOOK", "功能": "制造停留", "内容摘要": "测试摘要"}
        ],
        "情绪曲线": ["好奇", "震惊", "共鸣"],
    }
    result = _format_ccos_review(outline, "测试标题", "wechat")
    assert "立场" in result or "内容立场" in result
    assert "冲突" in result or "核心认知冲突" in result


def test_ccos_review_includes_emotion_curve():
    """_format_ccos_review 应包含情绪曲线"""
    from prism_os import _format_ccos_review
    outline = {
        "内容目标": "认知升级",
        "内容立场": "测试立场",
        "核心认知冲突": "测试冲突",
        "主结构": "认知升级型",
        "推进方式": "拆解推进",
        "认知模块流": [],
        "情绪曲线": ["好奇", "震惊", "共鸣", "清晰", "行动"],
    }
    result = _format_ccos_review(outline, "测试标题", "wechat")
    assert "情绪" in result or "好奇" in result
