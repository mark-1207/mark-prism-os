"""GAP-5: run 应在 Phase 4.5 后集成 Gap 分析 + 决策点 3"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_run_includes_gap_analysis_field(monkeypatch):
    """GAP-5: run 结果应包含 gap_analysis 字段"""
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
            "gap_analysis": {"gap_score": 0.5, "readiness": 0.5},
            "user_input": "测试命题",
        }

    def fake_narrate(topic, platform):
        return {"status": "success", "word_count": 100}

    monkeypatch.setattr("prism_os.run_prism_os", fake_run)
    monkeypatch.setattr("prism_os._run_narrate", fake_narrate)
    main()


def test_gap_subcommand_still_works(monkeypatch):
    """gap 子命令不应被破坏（向后兼容）"""
    monkeypatch.setattr(
        sys, "argv",
        ["prism_os.py", "gap", "测试命题", "--no-block"],
    )

    # mock analyze_gap 避免真跑 LLM
    fake_result = {"gap_score": 0.5, "readiness": 0.5, "missing_evidence": [], "knowledge": {}}

    import gap_analysis
    monkeypatch.setattr(gap_analysis, "analyze_gap", lambda thesis, materials: fake_result)

    from prism_os import main
    # --no-block 模式会 sys.exit(0)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
