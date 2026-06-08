"""GAP-2: run 成功后应自动接力 narrate"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_run_chains_narrate_after_success(monkeypatch):
    """GAP-2: run 成功后应自动调 _run_narrate"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "run", "测试命题", "--platform", "wechat",
         "--no-interactive", "--skip-gateway", "--no-ext"],
    )
    from prism_os import main

    narrate_called = {}

    def fake_run(*args, **kwargs):
        return {
            "status": "success",
            "phase": "complete",
            "ccos_outline": {"wechat_cognitive_outline": {}},
            "user_input": "测试命题",
        }

    def fake_narrate(topic, platform):
        narrate_called["topic"] = topic
        narrate_called["platform"] = platform
        return {"status": "success", "word_count": 100}

    monkeypatch.setattr("prism_os.run_prism_os", fake_run)
    monkeypatch.setattr("prism_os._run_narrate", fake_narrate)
    main()
    assert narrate_called.get("topic") == "测试命题"
    assert narrate_called.get("platform") == "wechat"


def test_run_narrate_failure_does_not_kill_run(monkeypatch, capsys):
    """narrate 失败不应让 run 报错退出"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "run", "测试命题", "--no-interactive",
         "--skip-gateway", "--no-ext"],
    )
    from prism_os import main

    def fake_run(*args, **kwargs):
        return {
            "status": "success",
            "phase": "complete",
            "ccos_outline": {"wechat_cognitive_outline": {}},
            "user_input": "测试命题",
        }

    def fake_narrate_fail(topic, platform):
        raise RuntimeError("narrate crashed")

    monkeypatch.setattr("prism_os.run_prism_os", fake_run)
    monkeypatch.setattr("prism_os._run_narrate", fake_narrate_fail)
    # 不应该崩
    main()
    captured = capsys.readouterr()
    assert "narrate" in captured.err.lower() or "warning" in captured.err.lower()
