"""GAP-1: run 命令应解析 --platform 参数并透传到 run_prism_os"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_run_accepts_platform_arg(monkeypatch):
    """GAP-1: run --platform wechat 应透传 platform=wechat 到 run_prism_os"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "run", "测试命题", "--platform", "wechat"],
    )
    from prism_os import main

    captured = {}

    def fake_run(*args, **kwargs):
        captured["platform"] = kwargs.get("platform")
        return {"status": "success", "phase": "init"}

    monkeypatch.setattr("prism_os.run_prism_os", fake_run)
    main()
    assert captured["platform"] == "wechat"


def test_run_platform_defaults_to_both(monkeypatch):
    """不传 --platform 时默认 platform='both'"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "run", "测试命题"],
    )
    from prism_os import main

    captured = {}

    def fake_run(*args, **kwargs):
        captured["platform"] = kwargs.get("platform")
        return {"status": "success", "phase": "init"}

    monkeypatch.setattr("prism_os.run_prism_os", fake_run)
    main()
    assert captured["platform"] == "both"


def test_run_platform_xiaohongshu(monkeypatch):
    """GAP-1: run --platform xiaohongshu 应透传 platform=xiaohongshu"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "run", "测试命题", "--platform", "xiaohongshu"],
    )
    from prism_os import main

    captured = {}

    def fake_run(*args, **kwargs):
        captured["platform"] = kwargs.get("platform")
        return {"status": "success", "phase": "init"}

    monkeypatch.setattr("prism_os.run_prism_os", fake_run)
    main()
    assert captured["platform"] == "xiaohongshu"
