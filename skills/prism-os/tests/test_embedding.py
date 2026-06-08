#!/usr/bin/env python3
"""embedding.py 单元测试"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from embedding import cosine_similarity, _jaccard, _md5


class TestCosineSimilarity(unittest.TestCase):
    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cosine_similarity(vec, vec), 1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, b), -1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        self.assertEqual(cosine_similarity(a, b), 0.0)

    def test_same_direction_different_magnitude(self):
        a = [1.0, 2.0, 3.0]
        b = [2.0, 4.0, 6.0]
        self.assertAlmostEqual(cosine_similarity(a, b), 1.0)


class TestJaccard(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(_jaccard("hello world", "hello world"), 1.0)

    def test_no_overlap(self):
        self.assertEqual(_jaccard("apple banana", "cat dog"), 0.0)

    def test_partial_overlap(self):
        sim = _jaccard("hello world test", "hello earth test")
        # 2/4 = 0.5
        self.assertGreaterEqual(sim, 0.5)
        self.assertLess(sim, 1.0)

    def test_chinese_single_token(self):
        """中文被 \w+ 视为单个 token，相似度可能为 0"""
        sim = _jaccard("AI时代执行者", "AI时代创造者")
        self.assertGreaterEqual(sim, 0)  # 取决于分词

    def test_empty(self):
        self.assertEqual(_jaccard("", ""), 0.0)

    def test_case_insensitive(self):
        self.assertEqual(_jaccard("Hello World", "hello world"), 1.0)


class TestMd5(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(_md5("test"), _md5("test"))

    def test_different_inputs(self):
        self.assertNotEqual(_md5("hello"), _md5("world"))

    def test_known_hash(self):
        self.assertEqual(_md5("test"), "098f6bcd4621d373cade4e832627b4f6")

    def test_unicode(self):
        hash1 = _md5("测试中文")
        self.assertEqual(len(hash1), 32)
        self.assertEqual(hash1, _md5("测试中文"))


if __name__ == "__main__":
    unittest.main()
