#!/usr/bin/env python3
"""call_llm.py 单元测试 — 纯逻辑函数（不涉及真实 API 调用）"""

import os
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from call_llm import (
    _is_retryable_error,
    get_kimi_model,
    get_kimi_max_tokens,
    get_openrouter_models,
    OPENROUTER_FALLBACK_MODELS,
    KIMI_MODEL_MAP,
    _curl_post,
    _curl_get,
)


# To test call_llm_raw after it's added:
# from call_llm import call_llm_raw


class TestIsRetryableError(unittest.TestCase):
    def test_timeout_is_retryable(self):
        self.assertTrue(_is_retryable_error("connection timed out"))

    def test_401_is_not_retryable(self):
        self.assertFalse(_is_retryable_error("HTTP 401: Unauthorized"))

    def test_403_is_not_retryable(self):
        self.assertFalse(_is_retryable_error("Forbidden"))

    def test_502_is_retryable(self):
        self.assertTrue(_is_retryable_error("HTTP 502 Bad Gateway"))

    def test_empty_string_defaults_retryable(self):
        self.assertTrue(_is_retryable_error(""))

    def test_null_error_defaults_retryable(self):
        self.assertTrue(_is_retryable_error("unknown error"))

    def test_ssl_error_is_retryable(self):
        self.assertTrue(_is_retryable_error("SSL: UNEXPECTED_EOF_WHILE_READING"))

    def test_network_error_is_retryable(self):
        self.assertTrue(_is_retryable_error("connection reset"))


class TestGetKimiModel(unittest.TestCase):
    def test_known_scene(self):
        self.assertEqual(get_kimi_model("reasoning"), "moonshot-v1-128k")

    def test_fast_scene(self):
        self.assertEqual(get_kimi_model("fast"), "moonshot-v1-32k")

    def test_writing_cn_scene(self):
        self.assertEqual(get_kimi_model("writing-cn"), "moonshot-v1-128k")

    def test_unknown_scene_defaults(self):
        self.assertEqual(get_kimi_model("nonexistent"), "moonshot-v1-128k")

    def test_empty_scene_defaults(self):
        self.assertEqual(get_kimi_model(""), "moonshot-v1-128k")


class TestGetKimiMaxTokens(unittest.TestCase):
    def test_fast_scene(self):
        self.assertEqual(get_kimi_max_tokens("fast"), 4096)

    def test_reasoning_scene(self):
        self.assertEqual(get_kimi_max_tokens("reasoning"), 8192)

    def test_writing_cn_scene(self):
        self.assertEqual(get_kimi_max_tokens("writing-cn"), 16384)

    def test_unknown_scene_defaults(self):
        self.assertEqual(get_kimi_max_tokens("nonexistent"), 8192)


class TestOpenRouterFallbackModels(unittest.TestCase):
    def test_all_models_are_strings(self):
        for model in OPENROUTER_FALLBACK_MODELS:
            self.assertIsInstance(model, str)

    def test_list_not_empty(self):
        self.assertGreater(len(OPENROUTER_FALLBACK_MODELS), 0)

    def test_get_openrouter_models(self):
        models = get_openrouter_models()
        self.assertGreater(len(models), 0)
        self.assertEqual(models, OPENROUTER_FALLBACK_MODELS)


class TestKimiModelMap(unittest.TestCase):
    def test_all_mapped_models_are_strings(self):
        for scene, model in KIMI_MODEL_MAP.items():
            self.assertIsInstance(model, str, f"Model for {scene} should be str")

    def test_all_required_scenes_exist(self):
        required = {"reasoning", "quality", "writing-cn", "writing-en",
                    "translation", "fast", "summary", "extraction", "multimodal"}
        for scene in required:
            self.assertIn(scene, KIMI_MODEL_MAP, f"Missing scene: {scene}")


class TestCurlPost(unittest.TestCase):
    @patch('call_llm.subprocess.run')
    def test_http_error_response_returns_none(self, mock_run):
        """curl -f returns exit 22 on HTTP 4xx/5xx; error-key in response also → None"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b'{"error":{"message":"Internal Server Error"}}'
        # _curl_post now checks for "error" key in response dict → returns None
        result = _curl_post("http://fake.url/test", {}, {"Auth": "x"})
        self.assertIsNone(result)

    @patch('call_llm.subprocess.run')
    def test_nonzero_returncode_returns_none(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = b''
        result = _curl_post("http://fake.url/test", {}, {})
        self.assertIsNone(result)

    @patch('call_llm.subprocess.run')
    def test_empty_stdout_returns_none(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        result = _curl_post("http://fake.url/test", {}, {})
        self.assertIsNone(result)

    @patch('call_llm.subprocess.run')
    def test_timeout_returns_none(self, mock_run):
        mock_run.side_effect = Exception("timeout")
        result = _curl_post("http://fake.url/test", {}, {})
        self.assertIsNone(result)

    @patch('call_llm.subprocess.run')
    def test_valid_json_response(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b'{"choices":[{"message":{"content":"ok"}}]}'
        result = _curl_post("http://fake.url/test", {}, {})
        self.assertIsNotNone(result)
        self.assertIn("choices", result)


class TestCurlGet(unittest.TestCase):
    @patch('call_llm.subprocess.run')
    def test_nonzero_returncode_returns_none(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = b''
        result = _curl_get("http://fake.url/test", {})
        self.assertIsNone(result)

    @patch('call_llm.subprocess.run')
    def test_valid_json_response(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b'{"data":[{"id":"test"}]}'
        result = _curl_get("http://fake.url/test", {})
        self.assertIsNotNone(result)
        self.assertIn("data", result)


class TestCallLlmRaw(unittest.TestCase):
    @patch('call_llm.call_llm')
    def test_returns_content_on_success(self, mock_call_llm):
        from call_llm import call_llm_raw
        mock_call_llm.return_value = {"content": "Hello world", "error": None}
        result = call_llm_raw("test prompt")
        self.assertEqual(result, "Hello world")

    @patch('call_llm.call_llm')
    def test_returns_none_on_error(self, mock_call_llm):
        from call_llm import call_llm_raw
        mock_call_llm.return_value = {"content": None, "error": "timeout"}
        result = call_llm_raw("test prompt")
        self.assertIsNone(result)

    @patch('call_llm.call_llm')
    def test_sets_scene_env_var(self, mock_call_llm):
        from call_llm import call_llm_raw
        mock_call_llm.return_value = {"content": "ok", "error": None}
        call_llm_raw("test", scene="reasoning")
        self.assertEqual(os.environ.get("GATEWAY_SCENE"), "reasoning")

    @patch('call_llm.call_llm')
    def test_passes_temperature(self, mock_call_llm):
        from call_llm import call_llm_raw
        mock_call_llm.return_value = {"content": "ok", "error": None}
        call_llm_raw("test", temperature=0.3)
        mock_call_llm.assert_called_with("test", temperature=0.3)

    @patch('call_llm.call_llm')
    def test_default_scene_is_writing_cn(self, mock_call_llm):
        from call_llm import call_llm_raw
        mock_call_llm.return_value = {"content": "ok", "error": None}
        call_llm_raw("test")
        self.assertEqual(os.environ.get("GATEWAY_SCENE"), "writing-cn")


if __name__ == "__main__":
    unittest.main()
