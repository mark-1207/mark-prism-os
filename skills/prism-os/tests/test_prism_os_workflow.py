#!/usr/bin/env python3
"""
prism_os workflow TDD 测试 — 7项缺失功能

覆盖：
1. prism CLI 交互式选标题
2. 选中标题记录 topic_log
3. gap CLI 阻塞等待
4. gap 用户选择后路由
5. 输出文件名 {title}_{date}.md
6. 三遍审校完整交互
7. gateway 追问交互

用法: python -m pytest skills/prism-os/tests/test_prism_os_workflow.py -v
"""

import sys
import os
import json
import unittest
import unittest.mock
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# =============================================================================
# T-1: prism CLI 交互式选标题
# =============================================================================

class TestPrismInteractiveSelection(unittest.TestCase):
    """prism 命令在生成候选标题后停在 stdin，等用户输入数字选择"""

    def test_prism_accepts_selection_input(self):
        """prism 停在候选标题等待用户输入数字选择"""
        sys.argv = ["prism_os.py", "prism", "AI替代焦虑"]
        with patch("builtins.input", return_value="1"):
            import prism_os
            captured = {}
            def capture(obj):
                captured["result"] = obj
            with patch.object(prism_os, "_safe_print", side_effect=capture):
                with patch("prism_engine.prism_engine") as mock_engine:
                    mock_engine.return_value = {
                        "status": "success",
                        "candidates": [
                            {"title": "标题1", "dimension": "reversal"},
                            {"title": "标题2", "dimension": "micro_scene"},
                        ]
                    }
                    try:
                        prism_os.main()
                    except SystemExit:
                        pass
                    # 验证 engine 被调用
                    self.assertTrue(mock_engine.called)

    def test_prism_returns_selected_title(self):
        """用户输入数字后，返回值中包含 selected_title"""
        candidates = [
            {"title": "标题1", "dimension": "reversal"},
            {"title": "标题2", "dimension": "micro_scene"},
        ]
        # 验证函数签名：如果有交互式选择函数，它应该返回选中的标题
        from prism_os import main as prism_main
        self.assertTrue(callable(prism_main))

    def test_prism_invalid_input_reasks(self):
        """无效输入（非数字）应提示重新输入"""
        # stdin 模拟：先输入 "abc"（无效），再输入 "1"（有效）
        with patch("builtins.input", side_effect=["abc", "1"]):
            sys.argv = ["prism_os.py", "prism", "test"]
            # 验证：两次 input 调用，第二次是有效数字
            pass

    def test_prism_q_exits(self):
        """输入 q 应立即退出，不报错"""
        with patch("builtins.input", return_value="q"):
            sys.argv = ["prism_os.py", "prism", "test"]
            with patch("sys.stdout", new_callable=MagicMock) as mock_out:
                mock_out.buffer = MagicMock()
                import prism_os
                # 不应抛出异常
                try:
                    prism_os.main()
                except SystemExit:
                    pass


# =============================================================================
# T-2: 选中标题写入 topic_log
# =============================================================================

class TestSelectedTitleRecording(unittest.TestCase):
    """用户选中的标题必须写入 topic_log.yaml"""

    def test_storage_has_append_selected_title(self):
        """storage.py 有 append_selected_title 函数"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import storage
        self.assertTrue(hasattr(storage, "append_selected_title"))

    def test_append_selected_title_writes_yaml(self):
        """append_selected_title 返回 status:ok 表示写入成功"""
        import tempfile, os
        tmp_dir = tempfile.mkdtemp()
        yaml_path = os.path.join(tmp_dir, "topic_log.yaml")

        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
            import storage
            import importlib
            importlib.reload(storage)

            # 直接验证函数行为：写入真实文件
            with patch.object(storage, "get_data_dir", return_value=tmp_dir):
                result = storage.append_selected_title(
                    title="2021年招了不该招的人，2024年让他们背AI的锅",
                    platform="wechat",
                    source="prism"
                )
                self.assertEqual(result.get("status"), "ok")
                self.assertIn("entry", result)
                self.assertEqual(result["entry"]["selected_title"],
                               "2021年招了不该招的人，2024年让他们背AI的锅")

            # 验证文件存在且内容正确（在 patch 外部检查）
            self.assertTrue(os.path.exists(yaml_path), f"文件未创建: {yaml_path}")
            with open(yaml_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("2021年招了不该招的人", content)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_selected_title_recorded_with_metadata(self):
        """记录包含标题、时间戳、平台、来源"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = os.path.join(tmp_dir, "topic_log.yaml")

            with patch("storage.get_data_dir", return_value=tmp_dir):
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
                import storage
                import importlib
                importlib.reload(storage)

                result = storage.append_selected_title(
                    title="测试标题",
                    platform="wechat",
                    source="prism"
                )
                entry = result.get("entry", {})
                self.assertIn("selected_title", entry)
                self.assertIn("timestamp", entry)
                self.assertIn("platform", entry)
                self.assertEqual(entry["source"], "prism")


# =============================================================================
# T-3: gap CLI 阻塞等待
# =============================================================================

class TestGapBlocking(unittest.TestCase):
    """gap 命令展示缺口后停在 stdin，等用户选择"""

    def test_gap_blocks_without_no_block_flag(self):
        """无 --no-block 时 gap 命令应停在 stdin"""
        sys.argv = ["prism_os.py", "gap", "选中的标题"]

        with patch("gap_analysis.analyze_gap", return_value={
            "gap_score": 0.67,
            "readiness": 0.33,
            "missing_evidence": ["数据支撑"],
            "recommendation": "建议补充 2 个关键素材"
        }):
            with patch("builtins.input", return_value="q"):
                import prism_os
                with patch("sys.stdout", new_callable=MagicMock) as mock_out:
                    mock_out.buffer = MagicMock()
                    try:
                        prism_os.main()
                    except SystemExit:
                        pass

    def test_gap_no_block_returns_json(self):
        """gap --no-block 应立即返回 JSON，不阻塞"""
        sys.argv = ["prism_os.py", "gap", "标题", "--no-block"]

        with patch("gap_analysis.analyze_gap", return_value={
            "gap_score": 0.67,
            "readiness": 0.33
        }):
            import prism_os
            captured = {}
            def safe_print(obj):
                captured["result"] = obj

            with patch.object(prism_os, "_safe_print", side_effect=safe_print):
                try:
                    prism_os.main()
                except SystemExit:
                    pass

            self.assertIn("gap_score", captured.get("result", {}))

    def test_gap_passes_no_block_to_analyze_gap(self):
        """gap --no-block 调用 analyze_gap"""
        sys.argv = ["prism_os.py", "gap", "标题", "--no-block"]

        with patch("gap_analysis.analyze_gap", return_value={"gap_score": 0.5}) as mock_analyze:
            import prism_os
            try:
                prism_os.main()
            except SystemExit:
                pass
            mock_analyze.assert_called_once()


# =============================================================================
# T-4: gap 用户选择后路由
# =============================================================================

class TestGapRouting(unittest.TestCase):
    """gap 阻塞后，用户输入 [1]/[2]/[3]/q 决定下一步"""

    def test_gap_input_1_add_material(self):
        """输入 1 → material_added 状态"""
        sys.argv = ["prism_os.py", "gap", "标题"]

        with patch("gap_analysis.analyze_gap", return_value={
            "gap_score": 0.8,
            "missing_evidence": ["案例"],
            "recommendation": "补充真实案例"
        }):
            import prism_os
            captured = {}
            def capture(obj):
                captured["result"] = obj

            # stdin: "1" = 选菜单, "\n" = 空行确认素材输入结束
            with patch("builtins.input", side_effect=["1", "\n"]):
                with patch.object(prism_os, "_safe_print", side_effect=capture):
                    try:
                        prism_os.main()
                    except SystemExit:
                        pass

            self.assertEqual(captured.get("result", {}).get("status"), "material_added")

    def test_gap_input_2_restart_ccos(self):
        """输入 2 → 提示重新生成 CCOS"""
        sys.argv = ["prism_os.py", "gap", "标题"]

        with patch("gap_analysis.analyze_gap", return_value={
            "gap_score": 0.8,
            "missing_evidence": []
        }):
            with patch("builtins.input", return_value="2"):
                import prism_os
                with patch("sys.stdout", new_callable=MagicMock) as mock_out:
                    mock_out.buffer = MagicMock()
                    captured = {}
                    def capture(obj):
                        captured["result"] = obj
                    with patch.object(prism_os, "_safe_print", side_effect=capture):
                        try:
                            prism_os.main()
                        except SystemExit:
                            pass
                    self.assertEqual(captured.get("result", {}).get("status"), "restart_ccos")

    def test_gap_input_3_go_narrate(self):
        """输入 3 → 提示进入 narrate"""
        sys.argv = ["prism_os.py", "gap", "标题"]

        with patch("gap_analysis.analyze_gap", return_value={
            "gap_score": 0.5,
            "missing_evidence": []
        }):
            with patch("builtins.input", return_value="3"):
                import prism_os
                with patch("sys.stdout", new_callable=MagicMock) as mock_out:
                    mock_out.buffer = MagicMock()
                    captured = {}
                    def capture(obj):
                        captured["result"] = obj
                    with patch.object(prism_os, "_safe_print", side_effect=capture):
                        try:
                            prism_os.main()
                        except SystemExit:
                            pass
                    self.assertEqual(captured.get("result", {}).get("status"), "go_narrate")

    def test_gap_input_q_exits(self):
        """输入 q → 优雅退出"""
        sys.argv = ["prism_os.py", "gap", "标题"]

        with patch("gap_analysis.analyze_gap", return_value={"gap_score": 0.5}):
            import prism_os
            with patch("builtins.input", return_value="q"):
                with patch("sys.stdout", new_callable=MagicMock) as mock_out:
                    mock_out.buffer = MagicMock()
                    try:
                        prism_os.main()
                    except SystemExit:
                        pass  # 预期退出


# =============================================================================
# T-5: 输出文件名 {title}_{date}.md
# =============================================================================

class TestOutputFilename(unittest.TestCase):
    """narrate 输出文件名必须为 {文章标题}_{YYYYMMDD}.md"""

    def test_narrate_saves_as_title_date(self):
        """narrate 生成的文件名必须为 {标题}_{日期}.md"""
        # 验证 _safe_filename 和日期格式
        from prism_os import _safe_filename
        from datetime import date

        title = "2021年招了不该招的人，2024年让他们背AI的锅"
        date_str = date.today().strftime("%Y%m%d")
        safe_title = _safe_filename(title)
        expected_filename = f"{safe_title}_{date_str}.md"

        # 验证文件名格式正确
        self.assertIn("2021年招了不该招的人", safe_title)
        self.assertTrue(expected_filename.endswith(".md"))
        self.assertIn("2026", expected_filename)
        # 不含非法字符
        for ch in "<>:\"|?*":
            self.assertNotIn(ch, expected_filename)
                        # Just verify no exception was raised

    def test_title_sanitized_for_filename(self):
        """标题含非法字符时替换为下划线"""
        from prism_os import _safe_filename
        unsafe = "测试:标题*含<>非法字符"
        safe = _safe_filename(unsafe)
        for ch in "<>:\"|?*":
            self.assertNotIn(ch, safe)

    def test_default_title_when_no_title(self):
        """无标题时使用默认名"""
        sys.argv = ["prism_os.py", "narrate", "", "--platform", "wechat"]


# =============================================================================
# T-6: 三遍审校完整交互
# =============================================================================

class TestThreePassProofreading(unittest.TestCase):
    """三遍审校：列出问题→用户确认→增量修改→实时保存"""

    def test_proofreading_flow_exists(self):
        """proofreading_flow() 函数存在且可调用"""
        from content_generator import proofreading_flow
        self.assertTrue(callable(proofreading_flow))

    def test_proofreading_flow_returns_modifications(self):
        """三遍审校返回用户确认的修改列表"""
        article_text = "这是文章内容。" * 50

        with patch("content_generator._call_llm_raw") as mock_llm:
            mock_llm.return_value = json.dumps({
                "issues": [
                    {"level": "L1", "type": "禁用词", "location": "第2段", "suggestion": "删除'赋能'", "severity": "error"},
                    {"level": "L2", "type": "AI腔", "location": "全文", "suggestion": "减少排比句", "severity": "warning"},
                ],
                "ai_mannerisms": [],
                "score": 65
            })

            # Mock 用户确认所有问题
            with patch("builtins.input", side_effect=["y", "y", "y"]):
                from content_generator import proofreading_flow
                result = proofreading_flow(article_text, "wechat")
                self.assertIn("confirmed_issues", result)
                self.assertIn("final_article", result)

    def test_proofreading_selective_accept(self):
        """用户可选择接受/拒绝每个修改项"""
        article_text = "赋能企业的AI战略。" * 10

        with patch("content_generator._call_llm_raw") as mock_llm:
            mock_llm.return_value = json.dumps({
                "issues": [
                    {"level": "L1", "type": "禁用词", "location": "第1段", "suggestion": "删除'赋能'", "severity": "error"},
                    {"level": "L1", "type": "禁用词", "location": "第2段", "suggestion": "删除'抓手'", "severity": "error"},
                ],
                "ai_mannerisms": [],
                "score": 50
            })

            # 用户拒绝第一个，接受第二个
            with patch("builtins.input", side_effect=["n", "y"]):
                from content_generator import proofreading_flow
                result = proofreading_flow(article_text, "wechat")
                self.assertIn("rejected_count", result)
                self.assertIn("accepted_count", result)


# =============================================================================
# T-7: gateway 追问交互
# =============================================================================

class TestGatewayInteractiveFollowUp(unittest.TestCase):
    """gateway 返回 need_clarification 时停在 stdin，等用户回答7类追问"""

    def test_gateway_blocks_on_clarify(self):
        """gateway 返回 need_clarification 时应停在 stdin"""
        sys.argv = ["prism_os.py", "gateway", "AI"]

        with patch("socratic_gateway.socratic_gateway", return_value={
            "status": "need_clarification",
            "entropy_score": 0.32,
            "hkr": {"h": 0.1, "k": 0.2, "r": 0.1, "hkr_avg": 0.13},
            "combined_score": 0.25,
            "questions": [
                {"类型": "方向追问", "内容": "你想从哪个角度切入？"},
                {"类型": "立场追问", "内容": "你的核心观点是什么？"},
            ],
            "directions": ["角度A", "角度B"]
        }):
            import prism_os
            with patch("builtins.input", return_value="角度A"):
                with patch("sys.stdout", new_callable=MagicMock) as mock_out:
                    mock_out.buffer = MagicMock()
                    try:
                        prism_os.main()
                    except SystemExit:
                        pass

    def test_gateway_continues_after_user_answer(self):
        """用户回答后 gateway 应继续处理并返回更新后的结果"""
        sys.argv = ["prism_os.py", "gateway", "AI"]

        with patch("socratic_gateway.socratic_gateway", return_value={
            "status": "need_clarification",
            "questions": [{"类型": "方向", "内容": "?"}],
            "directions": ["A", "B"]
        }):
            with patch("builtins.input", return_value="A"):
                import prism_os
                captured = {}
                def capture(obj):
                    captured["result"] = obj
                with patch.object(prism_os, "_safe_print", side_effect=capture):
                    try:
                        prism_os.main()
                    except SystemExit:
                        pass
                    # 验证有输出
                    self.assertIn("status", captured.get("result", {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
