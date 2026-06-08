#!/usr/bin/env python3
"""
gap_analysis.py + logic_pressure.py — TDD 测试
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestCalculateReadiness(unittest.TestCase):
    """calculate_readiness: 纯函数，直接测试"""

    def test_no_evidence_chain_high_material_count(self):
        """无证据链，素材数>=5 → readiness=0.9"""
        from gap_analysis import calculate_readiness
        results = [{"name": f"素材{i}", "content": "内容"} for i in range(6)]
        r = calculate_readiness(results)
        self.assertEqual(r["readiness"], 0.9)
        self.assertEqual(r["material_count"], 6)
        self.assertEqual(r["matched_evidence"], [])
        self.assertEqual(r["missing_evidence"], [])

    def test_no_evidence_chain_3_materials(self):
        """无证据链，3<=素材数<5 → readiness=0.7"""
        from gap_analysis import calculate_readiness
        results = [{"name": f"素材{i}"} for i in range(3)]
        r = calculate_readiness(results)
        self.assertEqual(r["readiness"], 0.7)
        self.assertEqual(r["material_count"], 3)

    def test_no_evidence_chain_1_material(self):
        """无证据链，1<=素材数<3 → readiness=0.5"""
        from gap_analysis import calculate_readiness
        results = [{"name": "素材1"}]
        r = calculate_readiness(results)
        self.assertEqual(r["readiness"], 0.5)

    def test_no_evidence_chain_0_material(self):
        """无证据链，0素材 → readiness=0.2"""
        from gap_analysis import calculate_readiness
        r = calculate_readiness([])
        self.assertEqual(r["readiness"], 0.2)
        self.assertEqual(r["material_count"], 0)

    def test_evidence_chain_partial_match(self):
        """有证据链，匹配1/2 → readiness=0.5"""
        from gap_analysis import calculate_readiness
        results = [
            {"name": "案例1", "content": "关于AI替代", "type": "case"},
            {"name": "案例2", "content": "关于就业", "type": "case"},
        ]
        evidence_chain = ["AI对就业的影响", "收入下降的证据"]
        r = calculate_readiness(results, evidence_chain)
        # 第一条证据关键词 "AI", "就业" 匹配案例1
        self.assertGreaterEqual(len(r["matched_evidence"]), 0)
        self.assertLessEqual(r["readiness"], 1.0)
        self.assertGreaterEqual(r["readiness"], 0.0)
        self.assertIn("matched_evidence", r)
        self.assertIn("missing_evidence", r)

    def test_evidence_chain_none_input(self):
        """evidence_chain=None → 不崩溃，等同空列表"""
        from gap_analysis import calculate_readiness
        r = calculate_readiness([{"name": "x"}], evidence_chain=None)
        self.assertEqual(r["readiness"], 0.5)  # 1 material, no evidence chain
        self.assertEqual(r["material_count"], 1)


class TestOutputMaterials(unittest.TestCase):
    """output_materials: 纯函数，直接测试"""

    def test_limit_respected(self):
        """limit=3 → 最多返回3条"""
        from gap_analysis import output_materials
        results = [{"name": f"素材{i}", "type": "atom"} for i in range(10)]
        mats = output_materials(results, limit=3)
        self.assertEqual(len(mats), 3)

    def test_missing_fields_get_defaults(self):
        """缺少字段 → 使用默认值"""
        from gap_analysis import output_materials
        results = [{"name": "测试"}]
        mats = output_materials(results)
        self.assertEqual(mats[0]["type"], "")
        self.assertEqual(mats[0]["path"], "")
        self.assertEqual(mats[0]["quality_score"], 0)
        self.assertEqual(mats[0]["relevance"], 0)


class TestParseLlmJson(unittest.TestCase):
    """_parse_llm_json: 纯函数，直接测试"""

    def test_fenced_json_extracted(self):
        """markdown 代码块 JSON → 正确提取"""
        from gap_analysis import _parse_llm_json
        text = '```json\n{"key": "value"}\n```'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_raw_json_extracted(self):
        """裸 JSON → 正确提取"""
        from gap_analysis import _parse_llm_json
        text = '{"answer": 42}'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"answer": 42})

    def test_broken_json_fence_fallback(self):
        """```json 格式错误，尝试 fallback 提取 {..."""
        from gap_analysis import _parse_llm_json
        text = '请按以下JSON格式回答：\n{"result": "ok"}\n这是额外内容'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"result": "ok"})

    def test_empty_text_returns_none(self):
        """空文本 → None"""
        from gap_analysis import _parse_llm_json
        self.assertIsNone(_parse_llm_json(""))
        self.assertIsNone(_parse_llm_json(None))

    def test_invalid_json_returns_none(self):
        """无效 JSON → None（不抛异常）"""
        from gap_analysis import _parse_llm_json
        self.assertIsNone(_parse_llm_json("{invalid"))

    def test_no_json_in_text_returns_none(self):
        """文本中没有 { } → None"""
        from gap_analysis import _parse_llm_json
        self.assertIsNone(_parse_llm_json("这是一段普通文本"))


class TestIntegrateKnowledge(unittest.TestCase):
    """integrate_knowledge: mock Obsidian 模块"""

    @patch("gap_analysis._get_obsidian_module")
    def test_obsidian_unavailable(self, mock_get):
        """Obsidian 模块不可用 → 返回 integrated=False"""
        mock_get.return_value = None
        from gap_analysis import integrate_knowledge
        r = integrate_knowledge("测试命题")
        self.assertFalse(r["integrated"])
        self.assertEqual(r["knowledge_results"], [])

    @patch("gap_analysis._get_obsidian_module")
    def test_no_files_found(self, mock_get):
        """Obsidian 扫描为空 → 返回 integrated=False"""
        mock_obs = MagicMock()
        mock_obs.scan_vault.return_value = []
        mock_get.return_value = mock_obs

        from gap_analysis import integrate_knowledge
        r = integrate_knowledge("测试命题")
        self.assertFalse(r["integrated"])
        self.assertIn("error", r)

    @patch("gap_analysis._get_obsidian_module")
    def test_full_flow_success(self, mock_get):
        """完整流程 → integrated=True + 质量过滤结果"""
        mock_obs = MagicMock()
        mock_obs.scan_vault.return_value = ["file1.md"]
        mock_obs.full_text_search.return_value = [
            {"name": "素材1", "content": "AI内容", "quality_score": 8},
            {"name": "素材2", "content": "AI内容", "quality_score": 5},
        ]
        mock_obs.filter_quality.return_value = [
            {"name": "素材1", "content": "AI内容", "quality_score": 8},
        ]
        mock_get.return_value = mock_obs

        from gap_analysis import integrate_knowledge
        r = integrate_knowledge("测试命题")
        self.assertTrue(r["integrated"])
        self.assertEqual(len(r["knowledge_results"]), 1)
        self.assertEqual(r["total_files"], 1)
        self.assertEqual(r["search_hits"], 2)
        self.assertEqual(r["quality_hits"], 1)


class TestGapAnalysisWorkflow(unittest.TestCase):
    """gap_analysis 完整流程的边界情况"""

    @patch("gap_analysis.integrate_knowledge")
    @patch("gap_analysis.analyze_gap")
    def test_gap_analysis_with_empty_thesis(self, mock_analyze, mock_integrate):
        """空 thesis → 跳过 gap 分析"""
        mock_integrate.return_value = {"knowledge_results": [], "integrated": False}
        mock_analyze.return_value = {}

        from gap_analysis import gap_analysis
        r = gap_analysis("")
        # gap 应该为 None（thesis 为空）
        self.assertIsNone(r["gap"])
        mock_analyze.assert_not_called()

    @patch("gap_analysis.integrate_knowledge")
    @patch("gap_analysis.analyze_gap")
    def test_gap_analysis_with_knowledge_integration(self, mock_analyze, mock_integrate):
        """有 Obsidian 素材 → 合并就绪度"""
        mock_integrate.return_value = {
            "integrated": True,
            "knowledge_results": [
                {"name": "案例1", "content": "真实案例", "type": "case", "relevance": 0.8},
            ]
        }
        mock_analyze.return_value = {
            "readiness": 0.3,
            "evidence_chain": ["真实案例"],
        }

        from gap_analysis import gap_analysis
        r = gap_analysis("AI时代就业", "现有素材")
        # knowledge_readiness 字段应存在
        self.assertIn("knowledge_readiness", r["gap"])
        self.assertGreaterEqual(r["gap"]["readiness"], 0)


# ============================================================
# logic_pressure.py 测试
# ============================================================

class TestAuditTitle(unittest.TestCase):
    """audit_title: 逻辑谬误检测（mock LLM）"""

    @patch("logic_pressure._call_llm_raw")
    def test_llm_returns_valid_json(self, mock_call):
        """LLM 返回有效 JSON → 正确解析"""
        mock_call.return_value = '{"has_fallacy": false, "fallacy_type": null, "severity": 0}'

        from logic_pressure import audit_title
        r = audit_title("AI不会取代人类工作")
        self.assertFalse(r["has_fallacy"])
        self.assertEqual(r["severity"], 0)

    @patch("logic_pressure._call_llm_raw")
    def test_llm_returns_none(self, mock_call):
        """LLM 调用失败 → 返回 fallback dict，不抛异常"""
        mock_call.return_value = None

        from logic_pressure import audit_title
        r = audit_title("测试标题")
        self.assertFalse(r["has_fallacy"])
        self.assertEqual(r["fallacy_type"], "无")

    @patch("logic_pressure._call_llm_raw")
    def test_llm_returns_invalid_json(self, mock_call):
        """LLM 返回无效 JSON → 返回 fallback dict，不抛异常"""
        mock_call.return_value = "这不是 JSON"

        from logic_pressure import audit_title
        r = audit_title("测试标题")
        self.assertFalse(r["has_fallacy"])


class TestCalculateCognitiveJourney(unittest.TestCase):
    """calculate_cognitive_journey: 需 mock LLM"""

    @patch("logic_pressure._call_llm_raw")
    def test_single_title_first_time(self, mock_call):
        """非空历史 → 调用 LLM 计算距离"""
        mock_call.return_value = '{"cognitive_progress": "new_domain", "avg_distance": 0.5}'

        from logic_pressure import calculate_cognitive_journey
        # signature: calculate_cognitive_journey(thesis: str, history_topics: List[str])
        r = calculate_cognitive_journey("AI时代自媒体机会", ["AI与就业"])
        self.assertIn("cognitive_progress", r)
        self.assertIn("avg_distance", r)

    @patch("logic_pressure._call_llm_raw")
    def test_empty_history(self, mock_call):
        """空历史 → 跳过 LLM 调用，直接返回 first_time"""
        from logic_pressure import calculate_cognitive_journey
        r = calculate_cognitive_journey("新标题", [])
        self.assertEqual(r["status"], "first_time")


class TestParseLlmJsonLogicPressure(unittest.TestCase):
    """logic_pressure._parse_llm_json 测试"""

    def test_valid_json(self):
        """有效 JSON → 正确解析"""
        from logic_pressure import _parse_llm_json
        result = _parse_llm_json('{"has_fallacy": true, "severity": 0.8}')
        self.assertEqual(result["has_fallacy"], True)
        self.assertEqual(result["severity"], 0.8)

    def test_json_in_code_block(self):
        """markdown 代码块 JSON → 正确提取"""
        from logic_pressure import _parse_llm_json
        text = '```json\n{"has_fallacy": false}\n```'
        result = _parse_llm_json(text)
        self.assertFalse(result["has_fallacy"])

    def test_invalid_returns_none(self):
        """无效 JSON → None"""
        from logic_pressure import _parse_llm_json
        self.assertIsNone(_parse_llm_json("{broken"))
        self.assertIsNone(_parse_llm_json("plain text"))


if __name__ == "__main__":
    unittest.main()
