#!/usr/bin/env python3
"""
剩余 4 个 medium 问题 — TDD 测试

Issue 1 (HTTP handler): HTTP handler must pass `platform` to run_prism_os
Issue 2 (dead gap ref): format_prism_os_output must not reference result["gap"]
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock, MagicMock
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from prism_os import format_prism_os_output


class TestHttpHandlerPlatformParam(unittest.TestCase):
    """Issue: HTTP handler reads platform but doesn't pass it to run_prism_os"""

    def test_http_handler_source_passes_platform_to_run_prism_os(self):
        """
        验收标准：HTTP handler 的 do_POST 方法在调用 run_prism_os 时
        必须传递 platform 参数。当前代码读到了 platform 但没有传给 run_prism_os。
        """
        import prism_os as _prism_os
        import inspect

        # 获取 main 函数源码
        source = inspect.getsource(_prism_os.main)

        # 在 do_POST 的 run_prism_os 调用附近找
        # 正确行为：run_prism_os(..., platform=platform, ...)
        # 错误行为：run_prism_os(...)  # platform 缺失

        # 找 do_POST 区块中的 run_prism_os 调用（用 result = run_prism_os 定位，避免重名干扰）
        do_post_start = source.find("def do_POST(self)")
        if do_post_start < 0:
            self.skipTest("do_POST not found")
            return

        # 用 result = run_prism_os 定位
        result_call_start = source.find("result = run_prism_os", do_post_start)
        if result_call_start < 0:
            self.fail("run_prism_os call not found in HTTP handler")
            return

        # 找匹配括号，完整提取调用块
        fn_start = source.find("run_prism_os", result_call_start)
        depth = 0
        call_end = fn_start
        for i, c in enumerate(source[fn_start:]):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    call_end = fn_start + i + 1
                    break
        call_block = source[result_call_start:call_end]

        # 验收标准：platform= 必须出现在 run_prism_os 调用中
        self.assertIn("platform=", call_block,
                      f"run_prism_os 调用必须包含 platform= 参数。当前调用：{call_block}")


class TestFormatOutputNoDeadGapRef(unittest.TestCase):
    """Issue: format_prism_os_output reads result["gap"] (dead from gap_analysis migration)"""

    def test_format_output_no_gap_field(self):
        """format_prism_os_output must not reference result['gap']"""
        # This test verifies the source doesn't reference result["gap"]
        import prism_os as _prism_os
        import inspect

        source = inspect.getsource(_prism_os.format_prism_os_output)

        # Should NOT contain result.get("gap") or result["gap"]
        self.assertNotIn('result.get("gap")', source,
                         "format_prism_os_output must not reference result['gap'] (gap_analysis migrated to ccos)")
        self.assertNotIn("result['gap']", source,
                         "format_prism_os_output must not reference result['gap'] (gap_analysis migrated to ccos)")

    def test_format_output_with_ccos_not_gap(self):
        """format output with ccos_outline works, gap is irrelevant"""
        result = {
            "status": "success",
            "candidates": [
                {"title": "测试", "dimension": "reversal",
                 "competition_level": "蓝海", "novelty_score": 0.8}
            ],
            "ccos_outline": {
                "内容目标": "认知升级",
                "核心认知冲突": "自媒体不是万能钥匙"
            }
            # Note: no "gap" key — this is the normal state
        }
        output = format_prism_os_output(result)
        self.assertIsInstance(output, str)
        # Should show CCOS info, not crash on missing gap
        self.assertIn("测试", output)


if __name__ == "__main__":
    unittest.main()
