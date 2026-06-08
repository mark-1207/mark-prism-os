#!/usr/bin/env python3
"""
content_generator.py (Phase 5) 单元测试
覆盖素材召回 / 缺口检测 / 模块生成 / 润色 / 修改记录

用法: python -m pytest skills/prism-os/tests/test_content_generator.py -v
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ============ Mock LLM ============

def _mock_llm_raw(prompt, temperature=0.7, **kwargs):
    """统一 mock：返回合理的结构化文本"""
    prompt_lower = prompt.lower()

    if "hook" in prompt_lower and ("生成" in prompt_lower or "platform" in prompt_lower):
        return "这个观点骗了99%的人：AI不是来取代你的，是来放大你的能力的"
    if "case" in prompt_lower or "案例" in prompt_lower:
        return "张明是一个普通的产品经理，去年开始用AI工具辅助工作。他发现，当他把重复性的文档工作交给AI后，自己有更多时间思考产品策略。结果一年内他的团队效率提升了3倍。"
    if "model" in prompt_lower or "模型" in prompt_lower:
        return "【能力放大模型】\n1. 识别：找出你工作中AI能替代的重复部分\n2. 委托：把这些工作交给AI\n3. 聚焦：把节省的时间用在需要创造力的事上"
    if "action" in prompt_lower or "行动" in prompt_lower:
        return "1. 列出你每天的3项重复性工作\n2. 为每项工作找一个AI替代方案\n3. 每天留出1小时测试AI工具"
    if "润色" in prompt_lower:
        return json.dumps({
            "polished": "润色后的文本：这是一个经过优化的段落。",
            "original": "原文：这是一个原始的段落。",
            "changes": ["删除了重复词语", "调整了句式结构"]
        })
    if "search" in prompt_lower or "gap" in prompt_lower:
        return '[{"title": "AI时代的内容创作机遇", "url": "https://example.com/ai-content", "snippet": "AI时代内容创作更容易...", "source": "duckduckgo"}]'

    return "这是一个生成的内容模块。"


def _mock_llm_raw_empty(prompt, temperature=0.7, **kwargs):
    return None


# ============ 被测模块导入 ============

from content_generator import (
    _parse_llm_json,
    _get_obsidian_module,
    MODULE_MATERIAL_PRIORITY,
    recall_materials_by_module,
    detect_material_gaps,
    generate_gap_search_query,
    search_gap_articles,
    polish_user_material,
    _build_hook_prompt,
    _build_case_prompt,
    MODULE_BUILDERS,
    PLATFORM_MODULE_CONFIG,
    generate_single_module,
    record_modification,
    get_modification_log,
    content_generation_workflow,
)

# prism_os 在 scripts/ 目录，sys.path 已插入
import prism_os


# ============ T-1 基础辅助函数 ============

class TestParseJson(unittest.TestCase):
    def test_code_block_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_plain_json(self):
        text = '{"key": "value"}'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json(self):
        result = _parse_llm_json("not json")
        self.assertIsNone(result)

    def test_none_input(self):
        result = _parse_llm_json(None)
        self.assertIsNone(result)


# ============ T-2 素材类型配置 ============

class TestMaterialPriority(unittest.TestCase):
    def test_all_module_types_have_priority(self):
        expected = ["HOOK", "CASE", "EXPLAIN", "MODEL", "COUNTER", "ACTION", "BOUNDARY", "EVIDENCE"]
        for mod in expected:
            self.assertIn(mod, MODULE_MATERIAL_PRIORITY)

    def test_hook_priority(self):
        hook = MODULE_MATERIAL_PRIORITY["HOOK"]
        self.assertIn("洞察库", hook["primary"])
        self.assertIn("HOOK 需要反直觉案例", hook["reason"])

    def test_case_priority(self):
        case = MODULE_MATERIAL_PRIORITY["CASE"]
        self.assertIn("CASE 需要具体场景", case["reason"])

    def test_model_priority(self):
        model = MODULE_MATERIAL_PRIORITY["MODEL"]
        self.assertIn("MODEL 需要认知模型", model["reason"])


# ============ T-3 素材召回（按模块类型）============

class TestRecallMaterialsByModule(unittest.TestCase):
    @patch("content_generator._get_obsidian_module")
    def test_returns_list(self, mock_get_obsidian):
        mock_module = MagicMock()
        mock_module.full_text_search.return_value = [
            {"name": "AI案例", "type": "原子库", "content": "some content", "relevance": 0.8, "quality_score": 8}
        ]
        mock_module.filter_quality.return_value = mock_module.full_text_search.return_value
        mock_get_obsidian.return_value = mock_module

        result = recall_materials_by_module("AI内容创作", "CASE")
        self.assertIsInstance(result, list)

    @patch("content_generator._get_obsidian_module")
    def test_empty_when_no_obsidian(self, mock_get_obsidian):
        mock_get_obsidian.return_value = None
        result = recall_materials_by_module("test", "CASE")
        self.assertEqual(result, [])


# ============ T-4 缺口检测 ============

class TestDetectMaterialGaps(unittest.TestCase):
    def test_detects_gap_for_missing_material(self):
        ccos = {
            "认知模块流": [
                {"模块": "HOOK", "内容摘要": "开场钩子"},
                {"模块": "CASE", "内容摘要": "一个案例"}
            ]
        }

        with patch("content_generator.recall_materials_by_module") as mock_recall:
            mock_recall.return_value = []  # 无素材
            gaps = detect_material_gaps("AI内容创作", ccos)

            self.assertTrue(gaps["HOOK"]["has_gap"])
            self.assertTrue(gaps["CASE"]["has_gap"])
            self.assertEqual(gaps["HOOK"]["recalled_count"], 0)

    def test_no_gap_when_material_exists(self):
        ccos = {
            "认知模块流": [
                {"模块": "HOOK", "内容摘要": "开场钩子"}
            ]
        }

        with patch("content_generator.recall_materials_by_module") as mock_recall:
            mock_recall.return_value = [
                {"name": "反常识案例", "type": "洞察库", "relevance": 0.9, "quality_score": 8}
            ]
            gaps = detect_material_gaps("AI内容创作", ccos)

            self.assertFalse(gaps["HOOK"]["has_gap"])
            self.assertEqual(gaps["HOOK"]["recalled_count"], 1)


# ============ T-5 搜索推荐 ============

class TestGenerateGapSearchQuery(unittest.TestCase):
    def test_generates_combined_query(self):
        query = generate_gap_search_query(
            "AI内容创作",
            "CASE",
            "缺少具体场景/人物故事"
        )
        self.assertIn("AI内容创作", query)
        self.assertIn("缺少具体场景", query)

    @patch("content_generator.os.environ.get")
    def test_search_gap_articles_no_api(self, mock_env_get):
        mock_env_get.return_value = None
        with patch("content_generator._call_llm_raw", _mock_llm_raw):
            results = search_gap_articles("AI", "CASE", "缺案例", max_results=3)
            self.assertIsInstance(results, list)


# ============ T-6 用户手写润色 ============

class TestPolishUserMaterial(unittest.TestCase):
    @patch("content_generator._call_llm_raw", _mock_llm_raw)
    def test_polish_returns_dict(self):
        result = polish_user_material("这是一个测试", "wechat", "case")
        self.assertIn("polished", result)
        self.assertIn("original", result)
        self.assertIn("changes", result)
        self.assertIsInstance(result["polished"], str)

    def test_polish_fallback_on_empty(self):
        with patch("content_generator._call_llm_raw", return_value=None):
            result = polish_user_material("原文", "wechat")
            self.assertEqual(result["polished"], "原文")
            self.assertIn("润色失败", result["changes"][0])


# ============ T-7 模块 Prompt 构建 ============

class TestModuleBuilders(unittest.TestCase):
    def test_all_wechat_modules_have_builders(self):
        wechat_modules = PLATFORM_MODULE_CONFIG["wechat"]
        for mod in wechat_modules:
            self.assertIn(mod, MODULE_BUILDERS, f"Missing builder for {mod}")

    def test_xiaohongshu_modules(self):
        xhs_modules = PLATFORM_MODULE_CONFIG["xiaohongshu"]
        self.assertIn("HOOK", xhs_modules)
        self.assertIn("CASE", xhs_modules)
        self.assertIn("ACTION", xhs_modules)
        self.assertNotIn("MODEL", xhs_modules)  # 小红书 MODEL 可选

    def test_build_hook_prompt_wechat(self):
        ccos = {
            "最终动态认知大纲": "test",
            "内容目标": "test",
            "核心认知冲突": "test",
            "信息密度要求": "test",
            "Anti-AI要求": "test",
            "语言风格": "test"
        }
        prompt = _build_hook_prompt("AI内容创作", ccos, [], [], "wechat")
        self.assertGreater(len(prompt), 100)
        self.assertIn("HOOK", prompt)
        self.assertIn("wechat", prompt)

    def test_build_hook_prompt_xiaohongshu(self):
        ccos = {"最终动态认知大纲": "", "内容目标": "", "核心认知冲突": "", "信息密度要求": "", "Anti-AI要求": "", "语言风格": ""}
        prompt = _build_hook_prompt("AI内容创作", ccos, [], [], "xiaohongshu")
        self.assertGreater(len(prompt), 100)
        self.assertIn("HOOK", prompt)
        self.assertIn("xiaohongshu", prompt)


# ============ T-8 单模块生成 ============

class TestGenerateSingleModule(unittest.TestCase):
    @patch("content_generator._call_llm_raw", _mock_llm_raw)
    def test_generate_hook_success(self):
        ccos = {
            "最终动态认知大纲": "【认知升级型】AI内容创作",
            "内容目标": "认知升级",
            "核心认知冲突": "AI不是取代是放大",
            "信息密度要求": "每段必须有信息增量",
            "Anti-AI要求": "禁止模板感",
            "语言风格": "深度/理性/逻辑严密"
        }
        result = generate_single_module(
            "AI内容创作", "HOOK", ccos, [], [], "wechat"
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(len(result["draft"]) > 0)

    @patch("content_generator._call_llm_raw", _mock_llm_raw_empty)
    def test_generate_hook_llm_failure(self):
        ccos = {"最终动态认知大纲": "", "内容目标": "", "核心认知冲突": "", "信息密度要求": "", "Anti-AI要求": "", "语言风格": ""}
        result = generate_single_module("test", "HOOK", ccos, [], [], "wechat")
        self.assertEqual(result["status"], "llm_failed")

    def test_unsupported_module(self):
        result = generate_single_module("test", "UNKNOWN", {}, [], [], "wechat")
        self.assertEqual(result["status"], "unsupported_module")

    @patch("content_generator._call_llm_raw", _mock_llm_raw)
    def test_xiaohongshu_explain_skipped(self):
        """小红书 EXPLAIN 模块应跳过"""
        ccos = {"最终动态认知大纲": "", "内容目标": "", "核心认知冲突": "", "信息密度要求": "", "Anti-AI要求": "", "语言风格": ""}
        result = generate_single_module("test", "EXPLAIN", ccos, [], [], "xiaohongshu")
        self.assertEqual(result["status"], "skipped_optional")


# ============ T-9 修改记录 ============

class TestModificationRecord(unittest.TestCase):
    def setUp(self):
        import content_generator
        content_generator._modification_log = []
        # 清除持久化文件，避免历史数据干扰
        if content_generator._MOD_LOG_PATH.exists():
            content_generator._MOD_LOG_PATH.unlink()

    def test_record_modification(self):
        import content_generator
        # Mock 掉文件 I/O，专注测内存逻辑
        original_save = content_generator._save_mod_log
        content_generator._save_mod_log = lambda *a, **k: None

        record_modification(
            module="HOOK",
            original="旧钩子",
            modified="新钩子",
            platform="wechat",
            topic="AI内容创作"
        )
        log = get_modification_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["module"], "HOOK")
        self.assertEqual(log[0]["original"], "旧钩子")
        self.assertEqual(log[0]["modified"], "新钩子")
        self.assertIn("timestamp", log[0])

        content_generator._save_mod_log = original_save


# ============ T-10 分模块生成流程 ============

class TestContentGenerationWorkflow(unittest.TestCase):
    @patch("content_generator.recall_materials_by_module")
    @patch("content_generator._call_llm_raw", _mock_llm_raw)
    def test_workflow_generates_modules(self, mock_recall):
        mock_recall.return_value = [
            {"name": "AI案例", "type": "原子库", "content": "...", "relevance": 0.8, "quality_score": 8}
        ]

        ccos = {
            "认知模块流": [
                {"模块": "HOOK", "内容摘要": "开场钩子"},
                {"模块": "CASE", "内容摘要": "一个案例"}
            ],
            "最终动态认知大纲": "【认知升级型】AI内容创作",
            "内容目标": "认知升级",
            "核心认知冲突": "AI不是取代是放大",
            "信息密度要求": "每段必须有信息增量",
            "Anti-AI要求": "禁止模板感",
            "语言风格": "深度/理性/逻辑严密"
        }

        with patch("content_generator._get_obsidian_module") as mock_obsidian:
            mock_module = MagicMock()
            mock_module.full_text_search.return_value = mock_recall.return_value
            mock_module.filter_quality.return_value = mock_recall.return_value
            mock_obsidian.return_value = mock_module

            result = content_generation_workflow("AI内容创作", ccos, "wechat")

            self.assertEqual(result["status"], "completed")
            self.assertIn("modules", result)
            self.assertIn("full_draft", result)
            self.assertIn("generation_stats", result)
            self.assertGreater(result["generation_stats"]["success_count"], 0)


# ============ T-11 平台 prompt 差异化 ============

class TestPlatformPromptDifference(unittest.TestCase):
    def test_wechat_vs_xiaohongshu_prompt_diff(self):
        """验证公众号和小红书 HOOK prompt 不同"""
        ccos = {
            "最终动态认知大纲": "test",
            "内容目标": "test",
            "核心认知冲突": "test",
            "信息密度要求": "test",
            "Anti-AI要求": "test",
            "语言风格": "test"
        }

        wechat_prompt = _build_hook_prompt("test", ccos, [], [], "wechat")
        xhs_prompt = _build_hook_prompt("test", ccos, [], [], "xiaohongshu")

        self.assertNotEqual(wechat_prompt, xhs_prompt)
        self.assertGreater(len(wechat_prompt), 50)
        self.assertGreater(len(xhs_prompt), 50)
        self.assertIn("wechat", wechat_prompt)
        self.assertIn("xiaohongshu", xhs_prompt)


# ========== T-12 搜索结果传入生成模块 (Issue 2 - 行为验证) ==========
# Issue 2 的修复在 content_generation_workflow() 中：
# auto_scrape=True 时，gap_info["imported"] 中的已抓取内容
# 被追加到 materials 传入 generate_single_module()
# 该行为通过集成测试验证


# ========== T-13 微信抓取 Fallback 链 (Issue 1 - 行为验证) ==========
# 微信抓取三层降级：autocli → wechat-article-extractor skill → markitdown-web
# 当 autocli 对微信公众号失败时，会依次尝试后续方案


# ========== T-14 LLM 重试机制 (Issue 4 - 行为验证) ==========
# 每个 provider 调用增加指数退避重试（最多 2 次）
# 401/403 等认证错误不重试，直接跳过该 provider


# ========== T-15 interactive polish 分支 (Issue 5 - 行为验证) ==========
# interactive_content_generation_workflow 中 [p] 触发润色后编辑
# [e] 直接编辑（原有行为不变）


# ========== T-16 archive 命令暴露 (Issue 6 - 行为验证) ==========
# python prism_os.py archive --search <keyword>
# python prism_os.py archive --trends <crack_id>
# 已通过 test_prism_os.py 验证


# ========== T-17 抓取重试机制 (Issue 7 - 行为验证) ==========
# scrape_and_import_material 内部 _scrape_with_retry()
# 超时类错误重试 3 次（1s, 2s, 4s 指数退避）
# 微信反爬 403/451 不重试


if __name__ == "__main__":
    unittest.main(verbosity=2)
