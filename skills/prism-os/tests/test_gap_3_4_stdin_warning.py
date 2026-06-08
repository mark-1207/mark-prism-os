"""GAP-3+4: stdin 不可用时应打印 explicit warning + --interactive-only flag"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_stdin_unavailable_warning_printed_decision_point_1(monkeypatch, capsys):
    """GAP-3: stdin 不可用时决策点 1 应打印 WARNING 到 stderr"""
    from prism_os import _stdin_unavailable_warning

    # mock stdin.isatty() 返回 False
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    result = _stdin_unavailable_warning("1")
    assert result is True
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "stdin" in captured.err.lower()


def test_stdin_unavailable_warning_printed_decision_point_2(monkeypatch, capsys):
    """GAP-4: stdin 不可用时决策点 2 应打印 WARNING 到 stderr"""
    from prism_os import _stdin_unavailable_warning

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    result = _stdin_unavailable_warning("2")
    assert result is True
    captured = capsys.readouterr()
    assert "WARNING" in captured.err


def test_stdin_available_returns_false(monkeypatch, capsys):
    """stdin 可用时 helper 应返回 False，不打印 warning"""
    from prism_os import _stdin_unavailable_warning

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    result = _stdin_unavailable_warning("1")
    assert result is False
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_interactive_only_flag_parses(monkeypatch):
    """--interactive-only flag 应被 argv 循环解析，stdin 不可用时 sys.exit(2)"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "run", "测试命题", "--interactive-only"],
    )
    # stdin 在 pytest 中通常不是 tty
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    from prism_os import main

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
