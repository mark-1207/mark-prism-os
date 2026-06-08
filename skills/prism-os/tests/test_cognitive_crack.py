#!/usr/bin/env python3
"""cognitive_crack.py 单元测试"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cognitive_crack import format_push_message, _parse_llm_json


class TestFormatPushMessage(unittest.TestCase):
    def test_with_crack(self):
        crack_result = {
            "has_crack": True,
            "crack_type": "数据裂缝",
            "consensus": "AI会取代所有工作",
            "reality": "AI只取代重复性工作",
            "confidence": 0.85,
            "suggested_topic": "AI时代哪些工作反而更值钱"
        }
        message = format_push_message(crack_result)
        self.assertIn("数据裂缝", message)
        self.assertIn("AI会取代所有工作", message)
        self.assertIn("85%", message)
        self.assertIn("PRISM-OS", message)

    def test_no_crack(self):
        self.assertEqual(format_push_message({"has_crack": False}), "")

    def test_missing_fields(self):
        message = format_push_message({"has_crack": True})
        self.assertIn("PRISM-OS", message)
        self.assertIn("0%", message)

    def test_zero_confidence(self):
        crack_result = {
            "has_crack": True,
            "crack_type": "逻辑裂缝",
            "consensus": "test",
            "reality": "test",
            "confidence": 0.0,
            "suggested_topic": "test"
        }
        message = format_push_message(crack_result)
        self.assertIn("0%", message)


class TestParseLlmJson(unittest.TestCase):
    def test_plain_json(self):
        result = _parse_llm_json('{"has_crack": true}')
        self.assertTrue(result["has_crack"])

    def test_code_block(self):
        result = _parse_llm_json('```json\n{"has_crack": false}\n```')
        self.assertFalse(result["has_crack"])

    def test_with_text(self):
        result = _parse_llm_json('结果：\n{"has_crack": true}\n以上。')
        self.assertTrue(result["has_crack"])

    def test_invalid(self):
        self.assertIsNone(_parse_llm_json("not json"))

    def test_none(self):
        self.assertIsNone(_parse_llm_json(None))


if __name__ == "__main__":
    unittest.main()
