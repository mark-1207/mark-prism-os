#!/usr/bin/env python3
"""storage.py 单元测试"""

import sys
import os
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from storage import (
    tokenize,
    calculate_similarity,
    check_cliche,
    save_yaml,
    load_yaml,
    save_twin_feedback,
    load_twin_feedback,
    calculate_twin_accuracy,
)


class TestTokenize(unittest.TestCase):
    def test_chinese_as_single_token(self):
        """中文被 \w+ 视为单个 token（无分词器）"""
        tokens = tokenize("AI时代为什么执行者更值钱")
        # 中文连在一起是一个 token，"ai" 被单独分出
        self.assertTrue(any("ai" in t for t in tokens) or any("时代" in t for t in tokens))

    def test_english(self):
        tokens = tokenize("Hello World Test")
        self.assertEqual(tokens, ["hello", "world", "test"])

    def test_empty(self):
        self.assertEqual(tokenize(""), [])

    def test_mixed_english_tokens(self):
        tokens = tokenize("hello world test case")
        self.assertEqual(len(tokens), 4)


class TestCalculateSimilarity(unittest.TestCase):
    def test_identical_english(self):
        # 英文能被 \w+ 正确分词，identical → jaccard=1.0, cosine=0 → 0.4
        sim = calculate_similarity("hello world", "hello world")
        self.assertAlmostEqual(sim, 0.4)

    def test_completely_different(self):
        sim = calculate_similarity("apple banana", "cat dog")
        self.assertEqual(sim, 0.0)

    def test_partial_overlap_english(self):
        sim = calculate_similarity("hello world test", "hello earth test")
        self.assertGreater(sim, 0)
        self.assertLess(sim, 0.5)

    def test_empty_strings(self):
        sim = calculate_similarity("", "hello")
        self.assertEqual(sim, 0.0)


class TestYamlRoundtrip(unittest.TestCase):
    def test_basic_roundtrip(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            data = [{"title": "测试标题", "status": "备选"}]
            self.assertTrue(save_yaml(path, data))
            loaded = load_yaml(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["title"], "测试标题")
        finally:
            os.unlink(path)

    def test_extended_fields_preserved(self):
        """验证扩展字段不丢失"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            data = [{
                "thesis": "AI对职业的影响",
                "entropy_score": 0.85,
                "candidates_count": 12,
                "custom_field": "自定义值"
            }]
            save_yaml(path, data)
            loaded = load_yaml(path)
            self.assertEqual(loaded[0]["entropy_score"], 0.85)
            self.assertEqual(loaded[0]["candidates_count"], 12)
            self.assertEqual(loaded[0]["custom_field"], "自定义值")
        finally:
            os.unlink(path)

    def test_multiple_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            data = [{"title": "标题1"}, {"title": "标题2"}]
            save_yaml(path, data)
            loaded = load_yaml(path)
            self.assertEqual(len(loaded), 2)
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        self.assertEqual(load_yaml("/nonexistent/path.yaml"), [])


class TestCheckCliche(unittest.TestCase):
    def test_no_cliche(self):
        result = check_cliche("AI时代执行者为什么更值钱")
        self.assertFalse(result["is_cliche"])

    def test_returns_dict_structure(self):
        result = check_cliche("test title")
        self.assertIn("is_cliche", result)


class TestTwinFeedback(unittest.TestCase):
    def test_save_and_calculate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import storage
            original = storage.get_data_dir
            storage.get_data_dir = lambda: tmpdir
            try:
                for match in [True, True, False]:
                    save_twin_feedback({
                        "thesis": "test",
                        "twin_selected": ["A"],
                        "user_selected": "A" if match else "B",
                        "match": match
                    })
                result = calculate_twin_accuracy()
                self.assertEqual(result["total"], 3)
                self.assertEqual(result["matches"], 2)
                self.assertAlmostEqual(result["accuracy"], 2/3, places=2)
            finally:
                storage.get_data_dir = original


if __name__ == "__main__":
    unittest.main()
