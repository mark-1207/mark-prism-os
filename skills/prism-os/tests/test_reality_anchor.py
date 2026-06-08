#!/usr/bin/env python3
"""reality_anchor.py 单元测试 — 纯逻辑函数"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from reality_anchor import (
    calculate_jaccard,
    evaluate_competition_level,
    tokenize_chinese,
    calculate_duplicate_rate,
)


class TestTokenizeChinese(unittest.TestCase):
    def test_basic_chinese(self):
        tokens = tokenize_chinese("AI时代")
        self.assertIsInstance(tokens, set)
        self.assertGreater(len(tokens), 0)

    def test_whitespace_filtered(self):
        tokens = tokenize_chinese("AI 时代")
        self.assertNotIn(" ", tokens)

    def test_empty_string(self):
        tokens = tokenize_chinese("")
        self.assertEqual(len(tokens), 0)

    def test_pure_whitespace(self):
        tokens = tokenize_chinese("   \t\n  ")
        self.assertEqual(len(tokens), 0)

    def test_case_insensitive_handled_by_caller(self):
        # tokenize_chinese does NOT lowercase — callers handle that
        # verify it preserves case
        tokens = tokenize_chinese("AI")
        self.assertIn("A", tokens)
        self.assertIn("I", tokens)


class TestJaccard(unittest.TestCase):
    def test_identical_chinese(self):
        self.assertEqual(calculate_jaccard("AI时代", "AI时代"), 1.0)

    def test_disjoint_chinese(self):
        self.assertEqual(calculate_jaccard("AI时代", "不相干"), 0.0)

    def test_partial_overlap(self):
        score = calculate_jaccard("AI时代的学习", "AI时代工作")
        self.assertGreater(score, 0)
        self.assertLess(score, 1.0)

    def test_empty_both(self):
        self.assertEqual(calculate_jaccard("", ""), 0.0)

    def test_empty_one(self):
        self.assertEqual(calculate_jaccard("AI时代", ""), 0.0)

    def test_single_char(self):
        self.assertEqual(calculate_jaccard("A", "A"), 1.0)
        self.assertEqual(calculate_jaccard("A", "B"), 0.0)

    def test_english_case_insensitive(self):
        self.assertEqual(calculate_jaccard("Hello", "hello"), 1.0)


class TestCompetitionLevel(unittest.TestCase):
    def test_blue_ocean(self):
        self.assertEqual(evaluate_competition_level(0.1), "蓝海")

    def test_yellow_ocean(self):
        self.assertEqual(evaluate_competition_level(0.5), "黄海")

    def test_red_ocean(self):
        self.assertEqual(evaluate_competition_level(0.8), "红海")

    def test_boundary_blue_to_yellow(self):
        self.assertEqual(evaluate_competition_level(0.299), "蓝海")
        self.assertEqual(evaluate_competition_level(0.3), "黄海")

    def test_boundary_yellow_to_red(self):
        self.assertEqual(evaluate_competition_level(0.699), "黄海")
        self.assertEqual(evaluate_competition_level(0.7), "红海")

    def test_zero(self):
        self.assertEqual(evaluate_competition_level(0.0), "蓝海")

    def test_one(self):
        self.assertEqual(evaluate_competition_level(1.0), "红海")


class TestDuplicateRate(unittest.TestCase):
    def test_no_results(self):
        self.assertEqual(calculate_duplicate_rate("AI时代", []), 0.0)

    def test_identical_title(self):
        results = [{"title": "AI时代"}]
        self.assertEqual(calculate_duplicate_rate("AI时代", results), 1.0)

    def test_different_title(self):
        results = [{"title": "完全不同的标题"}]
        rate = calculate_duplicate_rate("AI时代的学习", results)
        self.assertLess(rate, 0.3)

    def test_empty_titles_in_results(self):
        results = [{"title": ""}, {"title": "AI时代"}]
        rate = calculate_duplicate_rate("AI时代", results)
        self.assertEqual(rate, 1.0)

    def test_takes_max_similarity(self):
        results = [
            {"title": "不相关标题"},
            {"title": "AI时代的变革"},
        ]
        rate = calculate_duplicate_rate("AI时代的学习", results)
        self.assertGreater(rate, 0)


if __name__ == "__main__":
    unittest.main()
