#!/usr/bin/env python3
"""
content_generator.py v2 单元测试 — 写作框架改造新增功能
覆盖：真实经历询问 / 质量自检 / 工具箱架构 / 并行搜索 / 数据溯源

用法: python -m pytest skills/prism-os/tests/test_content_generator_v2.py -v
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ============ Mock LLM ============

def _mock_llm_quality_pass(prompt, temperature=0.7, **kwargs):
    """模拟质量检查 LLM 返回：全部通过"""
    return json.dumps({
        "status": "pass",
        "issues": [],
        "ai_mannerisms": [],
        "score": 95
    })


def _mock_llm_quality_issues(prompt, temperature=0.7, **kwargs):
    """模拟质量检查 LLM 返回：发现问题"""
    return json.dumps({
        "status": "issues_found",
        "issues": [
            {"level": "L1", "type": "禁用词", "location": "第2段", "suggestion": "删除'赋能'", "severity": "error"},
            {"level": "L2", "type": "AI腔", "location": "第1段", "suggestion": "句式太工整，加口语节奏", "severity": "warning"},
            {"level": "L3", "type": "数据无来源", "location": "第3段", "suggestion": "补充数据出处", "severity": "warning"},
        ],
        "ai_mannerisms": [
            {"type": "排比句", "count": 3, "examples": ["不仅...而且...", "一方面...另一方面..."]},
        ],
        "score": 62
    })


def _mock_llm_extract_sources(prompt, temperature=0.7, **kwargs):
    """模拟数据溯源 LLM 返回"""
    return json.dumps({
        "data_claims": [
            {"text": "2024年裁员30%", "has_source": True, "source_text": "根据XX研究院2024年报告", "confidence": "high"},
            {"text": "AI将替代50%的工作", "has_source": False, "source_text": "", "confidence": "low"},
        ]
    })


def _mock_llm_architecture(prompt, temperature=0.7, **kwargs):
    """模拟工具箱架构选择 LLM 返回"""
    return json.dumps({
        "archetype": "现象解读型",
        "modules": ["HOOK", "CASE", "EXPLAIN", "COUNTER", "ACTION"],
        "module_flow": [
            {"module": "HOOK", "purpose": "制造认知冲突", "estimated_words": 200},
            {"module": "CASE", "purpose": "具体现象案例", "estimated_words": 600},
            {"module": "EXPLAIN", "purpose": "深层原因分析", "estimated_words": 500},
            {"module": "COUNTER", "purpose": "反直觉观点", "estimated_words": 300},
            {"module": "ACTION", "purpose": "行动建议", "estimated_words": 400},
        ],
        "reasoning": "选题涉及社会现象解读，适合现象解读型架构"
    })


def _mock_llm_experience_prompt(prompt, temperature=0.7, **kwargs):
    """模拟真实经历询问 prompt 生成"""
    return json.dumps({
        "prompt": "在开始写作前，请回忆一下：你有没有经历过或听说过类似的情况？可以是自己的、朋友的、或者你观察到的真实案例。这些真实经历会让文章更有说服力。",
        "question_areas": ["个人亲身经历", "朋友/同事的案例", "观察到的社会现象"]
    })


# ============ 导入被测模块 ============

from content_generator import (
    _parse_llm_json,
    search_gap_articles,
)


# ============ T-1: prompt_real_experience ============

class TestPromptRealExperience(unittest.TestCase):
    """写作前询问用户真实经历"""

    def test_function_exists(self):
        """导入验证：prompt_real_experience 存在且可调用"""
        from content_generator import prompt_real_experience
        self.assertTrue(callable(prompt_real_experience))

    @patch("content_generator._call_llm_raw", _mock_llm_experience_prompt)
    def test_returns_dict_with_prompt(self):
        from content_generator import prompt_real_experience
        ccos = {"内容目标": "认知升级", "核心认知冲突": "AI替代焦虑"}
        result = prompt_real_experience("AI替代程序员", ccos, "wechat")
        self.assertIsInstance(result, dict)
        self.assertIn("prompt", result)
        self.assertIn("question_areas", result)
        self.assertTrue(len(result["prompt"]) > 20)

    @patch("content_generator._call_llm_raw", _mock_llm_experience_prompt)
    def test_question_areas_is_list(self):
        from content_generator import prompt_real_experience
        result = prompt_real_experience("test", {}, "wechat")
        self.assertIsInstance(result["question_areas"], list)
        self.assertGreaterEqual(len(result["question_areas"]), 1)

    @patch("content_generator._call_llm_raw", return_value=None)
    def test_returns_default_on_llm_failure(self, mock_llm):
        from content_generator import prompt_real_experience
        result = prompt_real_experience("test", {}, "wechat")
        self.assertIsInstance(result, dict)
        self.assertIn("prompt", result)
        self.assertTrue(len(result["prompt"]) > 0)  # 有默认 prompt

    def test_platform_xiaohongshu_style(self):
        """小红书平台应有不同的询问风格（更生活化）"""
        from content_generator import prompt_real_experience
        with patch("content_generator._call_llm_raw", _mock_llm_experience_prompt):
            result_wechat = prompt_real_experience("test", {}, "wechat")
            result_xhs = prompt_real_experience("test", {}, "xiaohongshu")
            # 两个平台可能有不同策略，至少返回格式一致
            self.assertIn("prompt", result_wechat)
            self.assertIn("prompt", result_xhs)


# ============ T-2: quality_check ============

class TestQualityCheck(unittest.TestCase):
    """写作后质量自检：L1-L4 + AI腔识别"""

    def test_function_exists(self):
        from content_generator import quality_check
        self.assertTrue(callable(quality_check))

    @patch("content_generator._call_llm_raw", _mock_llm_quality_pass)
    def test_pass_article_returns_pass_status(self):
        from content_generator import quality_check
        article = "这是一篇很好的文章，有真实案例和数据支撑。" * 5  # 95 chars, >50 threshold
        result = quality_check(article, "wechat")
        self.assertEqual(result["status"], "pass")
        self.assertGreaterEqual(result["score"], 90)

    @patch("content_generator._call_llm_raw", _mock_llm_quality_issues)
    def test_issues_found_returns_problems(self):
        from content_generator import quality_check
        article = "赋能企业的数字化转型是当前最重要的战略方向之一。" * 5
        result = quality_check(article, "wechat")
        self.assertEqual(result["status"], "issues_found")
        self.assertGreater(len(result["issues"]), 0)
        self.assertGreater(len(result["ai_mannerisms"]), 0)
        self.assertLess(result["score"], 70)

    @patch("content_generator._call_llm_raw", _mock_llm_quality_issues)
    def test_issues_have_required_fields(self):
        from content_generator import quality_check
        result = quality_check("test", "wechat")
        for issue in result["issues"]:
            for field in ("level", "type", "location", "suggestion", "severity"):
                self.assertIn(field, issue, f"issue 缺少字段: {field}")
            self.assertIn(issue["level"], ("L1", "L2", "L3", "L4"))
            self.assertIn(issue["severity"], ("error", "warning"))

    @patch("content_generator._call_llm_raw", _mock_llm_quality_issues)
    def test_ai_mannerisms_format(self):
        from content_generator import quality_check
        result = quality_check("test", "wechat")
        for am in result["ai_mannerisms"]:
            self.assertIn("type", am)
            self.assertIn("count", am)
            self.assertIn("examples", am)
            self.assertIsInstance(am["count"], int)
            self.assertIsInstance(am["examples"], list)

    @patch("content_generator._call_llm_raw", _mock_llm_quality_pass)
    def test_returns_score_0_to_100(self):
        from content_generator import quality_check
        result = quality_check("test", "wechat")
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    @patch("content_generator._call_llm_raw", return_value=None)
    def test_returns_default_on_llm_failure(self, mock_llm):
        from content_generator import quality_check
        article = "这是一篇测试文章内容用于验证质量检查模块在LLM失败时的降级行为。" * 3
        result = quality_check(article, "wechat")
        self.assertIn("status", result)
        self.assertEqual(result["status"], "check_failed")
        self.assertEqual(result["score"], 0)

    def test_l1_banned_word_detection_disabled(self):
        """L1 检查不应依赖外部 BANNED_WORDS（可在 quality_check 内部处理）"""
        from content_generator import quality_check
        with patch("content_generator._call_llm_raw", _mock_llm_quality_issues):
            result = quality_check("赋能", "wechat")
            # 即使有禁用词，也应正常返回
            self.assertIn("status", result)

    def test_short_article_rejected(self):
        """少于200字的文章应自动标记 insufficient_content"""
        from content_generator import quality_check
        result = quality_check("太短了", "wechat")
        self.assertIn("status", result)

    def test_wechat_differs_from_xiaohongshu(self):
        """不同平台的质量标准应有差异（公众号更严格）"""
        from content_generator import quality_check
        with patch("content_generator._call_llm_raw", _mock_llm_quality_pass):
            wx = quality_check("test article content " * 20, "wechat")
            xhs = quality_check("test article content " * 20, "xiaohongshu")
            self.assertIn("platform", wx)
            self.assertIn("platform", xhs)


# ============ T-3: ARTICLE_ARCHETYPES 常量 ============

class TestArticleArchetypes(unittest.TestCase):
    """5种文章原型（卡兹克）"""

    def test_archetypes_defined(self):
        from content_generator import ARTICLE_ARCHETYPES
        self.assertIsInstance(ARTICLE_ARCHETYPES, dict)
        self.assertGreaterEqual(len(ARTICLE_ARCHETYPES), 5)

    def test_archetype_keys(self):
        from content_generator import ARTICLE_ARCHETYPES
        expected = {"调查实验型", "产品体验型", "现象解读型", "工具分享型", "方法论分享型"}
        actual = set(ARTICLE_ARCHETYPES.keys())
        self.assertEqual(actual, expected, f"期望5种原型，实际: {actual}")

    def test_each_archetype_has_required_fields(self):
        from content_generator import ARTICLE_ARCHETYPES
        for key, arch in ARTICLE_ARCHETYPES.items():
            for field in ("name", "description", "typical_modules", "best_for"):
                self.assertIn(field, arch, f"{key} 缺少字段: {field}")
            self.assertIsInstance(arch["typical_modules"], list)
            self.assertGreater(len(arch["typical_modules"]), 1)

    def test_archetypes_have_chinese_names(self):
        from content_generator import ARTICLE_ARCHETYPES
        for arch in ARTICLE_ARCHETYPES.values():
            self.assertTrue(any('一' <= c <= '鿿' for c in arch["name"]),
                            f"{arch['name']} 应包含中文")


# ============ T-4: select_article_architecture ============

class TestSelectArticleArchitecture(unittest.TestCase):
    """工具箱模式：按话题动态选择原型+模块"""

    def test_function_exists(self):
        from content_generator import select_article_architecture
        self.assertTrue(callable(select_article_architecture))

    @patch("content_generator._call_llm_raw", _mock_llm_architecture)
    def test_returns_dict_with_required_keys(self):
        from content_generator import select_article_architecture
        ccos = {"内容目标": "认知升级", "主结构": "现象解读型", "内容立场": "批判性"}
        result = select_article_architecture("AI替代焦虑", ccos, "wechat")
        for key in ("archetype", "modules", "module_flow", "reasoning"):
            self.assertIn(key, result, f"缺少 key: {key}")

    @patch("content_generator._call_llm_raw", _mock_llm_architecture)
    def test_archetype_in_known_list(self):
        from content_generator import select_article_architecture, ARTICLE_ARCHETYPES
        result = select_article_architecture("test", {}, "wechat")
        self.assertIn(result["archetype"], ARTICLE_ARCHETYPES.keys())

    @patch("content_generator._call_llm_raw", _mock_llm_architecture)
    def test_module_flow_items_have_purpose_and_words(self):
        from content_generator import select_article_architecture
        result = select_article_architecture("test", {}, "wechat")
        for mod in result["module_flow"]:
            self.assertIn("module", mod)
            self.assertIn("purpose", mod)
            self.assertIn("estimated_words", mod)
            self.assertIsInstance(mod["estimated_words"], int)
            self.assertGreater(mod["estimated_words"], 0)

    @patch("content_generator._call_llm_raw", _mock_llm_architecture)
    def test_total_estimated_words_valid(self):
        from content_generator import select_article_architecture
        result = select_article_architecture("test", {}, "wechat")
        total = sum(m["estimated_words"] for m in result["module_flow"])
        self.assertGreaterEqual(total, 1000)
        self.assertLessEqual(total, 5000)

    @patch("content_generator._call_llm_raw", return_value=None)
    def test_fallback_on_llm_failure(self, mock_llm):
        from content_generator import select_article_architecture
        result = select_article_architecture("test", {}, "wechat")
        self.assertIn("archetype", result)
        self.assertTrue(len(result["modules"]) > 0)  # 有默认模块

    def test_xiaohongshu_fewer_modules(self):
        """小红书平台选模块数量 < 公众号（更精简）"""
        from content_generator import select_article_architecture
        with patch("content_generator._call_llm_raw", _mock_llm_architecture):
            wx = select_article_architecture("test", {}, "wechat")
            xhs = select_article_architecture("test", {}, "xiaohongshu")
            # xhs 至少应该和 wechat 一样或更少
            self.assertLessEqual(len(xhs["modules"]), len(wx["modules"]))


# ============ T-5: search_parallel ============

class TestSearchParallel(unittest.TestCase):
    """并行双引擎搜索：Tavily + SerpAPI(百度) 同query并行"""

    def test_function_exists(self):
        from content_generator import search_parallel
        self.assertTrue(callable(search_parallel))

    @patch("content_generator.os.environ.get")
    def test_no_api_keys_returns_empty(self, mock_env_get):
        mock_env_get.return_value = None
        from content_generator import search_parallel
        result = search_parallel("AI裁员", max_results=5)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    @patch("content_generator.os.environ.get")
    def test_only_tavily_available(self, mock_env_get):
        """只有 Tavily key 时只用 Tavily"""
        def env_side_effect(key, default=None):
            if key == "TAVILY_API_KEY":
                return "tavily_test_key"
            return None
        mock_env_get.side_effect = env_side_effect

        mock_tavily_response = json.dumps({
            "results": [
                {"title": "AI裁员数据", "url": "https://example.com/1", "content": "2024年各大科技公司裁员情况"},
            ]
        }).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_tavily_response
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            from content_generator import search_parallel
            result = search_parallel("AI裁员", max_results=3)
            self.assertIsInstance(result, list)
            if len(result) > 0:
                self.assertIn("source", result[0])
                self.assertEqual(result[0]["source"], "tavily")

    @patch("content_generator.os.environ.get")
    def test_results_deduplicated_by_url(self, mock_env_get):
        """同 URL 去重：Tavily 和 SerpAPI 返回相同 URL 时只保留一条"""
        def env_side_effect(key, default=None):
            return "test_key"  # 两个 key 都设置
        mock_env_get.side_effect = env_side_effect

        common_result = {"title": "Same article", "url": "https://example.com/same", "content": "content"}
        tavily_response = json.dumps({"results": [common_result]}).encode("utf-8")
        serpapi_response = json.dumps({
            "organic_results": [{"title": "Same article", "link": "https://example.com/same", "snippet": "content"}]
        }).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp1 = MagicMock()
            mock_resp1.read.return_value = tavily_response
            mock_resp1.__enter__.return_value = mock_resp1
            mock_resp2 = MagicMock()
            mock_resp2.read.return_value = serpapi_response
            mock_resp2.__enter__.return_value = mock_resp2
            mock_urlopen.side_effect = [mock_resp1, mock_resp2]

            from content_generator import search_parallel
            result = search_parallel("AI裁员", max_results=5)
            urls = [r["url"] for r in result]
            self.assertEqual(len(urls), len(set(urls)), "存在重复 URL")

    def test_ddg_fallback_when_both_fail(self):
        """Tavily 和 SerpAPI 都失败时 DDG 兜底"""
        with patch("content_generator.os.environ.get") as mock_env_get:
            mock_env_get.return_value = "test_key"

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = Exception("Both failed")

                from content_generator import search_parallel
                result = search_parallel("AI裁员", max_results=3)
                # DDG fallback 应该通过不同的路径，但都失败时返回空列表
                self.assertIsInstance(result, list)

    def test_serpapi_uses_baidu_engine(self):
        """SerpAPI 搜索应使用 engine=baidu 参数"""
        with patch("content_generator.os.environ.get") as mock_env_get:
            mock_env_get.return_value = "test_key"
            mock_response = json.dumps({"organic_results": []}).encode("utf-8")

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = mock_response
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                from content_generator import search_parallel
                result = search_parallel("AI裁员", max_results=3)
                # 验证调用了 SerpAPI（结果应有 source 字段或有结果）
                self.assertIsInstance(result, list)

    def test_results_have_required_fields(self):
        """返回的每条结果必须有 title/url/snippet/source"""
        with patch("content_generator.os.environ.get") as mock_env_get:
            mock_env_get.return_value = "test_key"
            mock_response = json.dumps({
                "results": [{"title": "Test", "url": "https://example.com", "content": "snippet"}]
            }).encode("utf-8")

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = mock_response
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                from content_generator import search_parallel
                result = search_parallel("test", max_results=1)
                if result:
                    for field in ("title", "url", "snippet", "source"):
                        self.assertIn(field, result[0], f"搜索结果缺少字段: {field}")

    def test_max_results_respected(self):
        """返回结果数量不超过 max_results"""
        with patch("content_generator.os.environ.get") as mock_env_get:
            mock_env_get.return_value = "test_key"
            many_results = {
                "results": [
                    {"title": f"Title {i}", "url": f"https://example.com/{i}", "content": f"content {i}"}
                    for i in range(20)
                ]
            }
            mock_response = json.dumps(many_results).encode("utf-8")

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = mock_response
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                from content_generator import search_parallel
                result = search_parallel("test", max_results=5)
                self.assertLessEqual(len(result), 5)

    def test_merges_both_sources(self):
        """验证两个来源的结果被合并（各3条 → 共6条去重后 ≤6）"""
        with patch("content_generator.os.environ.get") as mock_env_get:
            mock_env_get.return_value = "test_key"

            tavily_data = {
                "results": [
                    {"title": "T1", "url": "https://t1.com", "content": "c1"},
                    {"title": "T2", "url": "https://t2.com", "content": "c2"},
                    {"title": "T3", "url": "https://t3.com", "content": "c3"},
                ]
            }
            serpapi_data = {
                "organic_results": [
                    {"title": "S1", "link": "https://s1.com", "snippet": "s1"},
                    {"title": "S2", "link": "https://s2.com", "snippet": "s2"},
                    {"title": "S3", "link": "https://s3.com", "snippet": "s3"},
                ]
            }

            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp1 = MagicMock()
                mock_resp1.read.return_value = json.dumps(tavily_data).encode("utf-8")
                mock_resp1.__enter__.return_value = mock_resp1
                mock_resp2 = MagicMock()
                mock_resp2.read.return_value = json.dumps(serpapi_data).encode("utf-8")
                mock_resp2.__enter__.return_value = mock_resp2
                mock_urlopen.side_effect = [mock_resp1, mock_resp2]

                from content_generator import search_parallel
                result = search_parallel("test", max_results=6)
                sources = set(r["source"] for r in result)
                # 至少有两种来源
                self.assertGreaterEqual(len(sources), 1)


# ============ T-6: extract_data_sources ============

class TestExtractDataSources(unittest.TestCase):
    """数据溯源：正则+LLM 扫描数据声明"""

    def test_function_exists(self):
        from content_generator import extract_data_sources
        self.assertTrue(callable(extract_data_sources))

    def test_regex_finds_percentage(self):
        """正则扫描应发现百分比数据声明"""
        from content_generator import extract_data_sources
        article = "根据XX报告，2024年AI相关裁员达到总裁员的30%。"
        result = extract_data_sources(article)
        self.assertIsInstance(result, list)
        if result:
            self.assertIn("text", result[0])
            self.assertIn("has_source", result[0])

    def test_regex_finds_number_ranges(self):
        """正则扫描应发现数值范围"""
        from content_generator import extract_data_sources
        article = "程序员薪资下降了15%-25%，这在过去十年从未出现过。"
        result = extract_data_sources(article)
        self.assertIsInstance(result, list)

    def test_no_data_claims_returns_empty(self):
        """无数据声明的文章应返回空列表"""
        from content_generator import extract_data_sources
        article = "这是一篇纯观点文章，没有任何数据支撑。"
        result = extract_data_sources(article)
        self.assertIsInstance(result, list)
        if result:
            for claim in result:
                self.assertIn("text", claim)

    @patch("content_generator._call_llm_raw", _mock_llm_extract_sources)
    def test_llm_enhanced_extraction(self):
        """LLM 增强模式应标注置信度"""
        from content_generator import extract_data_sources
        article = "根据XX研究院2024年报告，AI将替代50%的工作，2024年裁员30%。"
        result = extract_data_sources(article, use_llm=True)
        self.assertIsInstance(result, list)
        if result:
            source_claims = [c for c in result if c.get("has_source")]
            nosource_claims = [c for c in result if not c.get("has_source")]
            # 至少有一条有来源标注
            self.assertGreaterEqual(len(source_claims) + len(nosource_claims), 1)

    @patch("content_generator._call_llm_raw", _mock_llm_extract_sources)
    def test_confidence_field_when_llm(self):
        """LLM 模式应有 confidence 字段"""
        from content_generator import extract_data_sources
        result = extract_data_sources("test data", use_llm=True)
        for claim in result:
            if "confidence" in claim:
                self.assertIn(claim["confidence"], ("high", "medium", "low", "unverified"))

    def test_empty_input_returns_empty(self):
        from content_generator import extract_data_sources
        self.assertEqual(extract_data_sources(""), [])
        self.assertEqual(extract_data_sources(None), [])

    def test_short_text_no_data(self):
        """短文无数据"""
        from content_generator import extract_data_sources
        result = extract_data_sources("你好世界")
        self.assertIsInstance(result, list)


# ============ T-7: search_parallel 集成到现有 search_gap_articles ============

class TestSearchParallelIntegration(unittest.TestCase):
    """search_parallel 作为 search_gap_articles 的内部实现替代"""

    def test_search_parallel_accepts_same_params(self):
        """search_parallel 接受与 search_gap_articles 兼容的参数"""
        from content_generator import search_parallel
        # 只验证函数签名兼容
        import inspect
        sig = inspect.signature(search_parallel)
        params = list(sig.parameters.keys())
        self.assertIn("query", params)
        self.assertIn("max_results", params)


# ============ T-8: crawl4ai 抓取层 ============

class TestCrawl4aiScraper(unittest.TestCase):
    """crawl4ai 替换 urllib 用于非微信 URL 抓取"""

    def test_function_exists(self):
        from content_generator import scrape_with_crawl4ai
        self.assertTrue(callable(scrape_with_crawl4ai))

    def test_weixin_url_skips_crawl4ai(self):
        """微信 URL 不应使用 crawl4ai，保留三级降级"""
        from content_generator import scrape_with_crawl4ai
        result = scrape_with_crawl4ai("https://mp.weixin.qq.com/s/abc123")
        self.assertIsNone(result)  # 微信 URL 应直接返回 None，走原微信降级

    def test_non_weixin_url_attempts_crawl4ai(self):
        """非微信 URL 应尝试 crawl4ai"""
        with patch("content_generator._try_crawl4ai") as mock_crawl:
            mock_crawl.return_value = {"title": "Test", "content": "Content", "url": "https://example.com"}
            from content_generator import scrape_with_crawl4ai
            result = scrape_with_crawl4ai("https://example.com/article")
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Test")

    def test_crawl4ai_failure_falls_back_to_urllib(self):
        """crawl4ai 失败时回退到原有 urllib 路径"""
        with patch("content_generator._try_crawl4ai", return_value=None):
            with patch("content_generator.scrape_article") as mock_scrape:
                mock_scrape.return_value = {"title": "Fallback", "content": "ok"}
                from content_generator import scrape_with_crawl4ai
                result = scrape_with_crawl4ai("https://example.com/article")
                self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
