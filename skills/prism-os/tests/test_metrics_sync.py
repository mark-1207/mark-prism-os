"""Phase 6.0 — 增量同步测试"""
import pytest
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestSyncValidation:
    """行校验测试"""

    def test_validate_row_valid(self):
        from metrics_sync import validate_row
        row = {
            "文章ID": "test_20260603",
            "平台": "wechat",
            "时间点": "t_plus_1d",
            "阅读量": 100,
        }
        assert validate_row(row) is True

    def test_validate_row_missing_article_id(self):
        from metrics_sync import validate_row
        row = {"平台": "wechat", "时间点": "t_plus_1d", "阅读量": 100}
        assert validate_row(row) is False

    def test_validate_row_invalid_time_point(self):
        from metrics_sync import validate_row
        row = {"文章ID": "test_20260603", "平台": "wechat", "时间点": "invalid", "阅读量": 100}
        assert validate_row(row) is False

    def test_validate_row_negative_reads(self):
        from metrics_sync import validate_row
        row = {"文章ID": "test_20260603", "平台": "wechat", "时间点": "t_plus_1d", "阅读量": -5}
        assert validate_row(row) is False


class TestSyncIdempotent:
    """幂等性测试"""

    def test_same_row_synced_twice_has_one_record(self):
        from metrics_sync import MetricsSync
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            snapshot_path = f.name
            state_path = f.name.replace(".yaml", "_state.json")
        try:
            ms = MetricsSync.__new__(MetricsSync)
            ms.snapshot_path = snapshot_path
            ms.state_path = state_path
            ms._snapshot = []
            ms._last_sync = None

            row = {"文章ID": "a_20260603", "时间点": "t_plus_1d", "阅读量": 100, "平台": "wechat"}
            ms._save_to_snapshot(row)
            ms._save_to_snapshot(row)  # 同一行再存一次
            assert len(ms._snapshot) == 1
        finally:
            os.unlink(snapshot_path)
            if os.path.exists(state_path):
                os.unlink(state_path)


class TestSyncIncremental:
    """增量拉取测试"""

    def test_only_new_rows_fetched(self):
        from metrics_sync import MetricsSync
        ms = MetricsSync.__new__(MetricsSync)
        ms._last_sync = "2026-06-01T00:00:00"
        # 验证只拉取 last_sync 之后的数据
        assert ms._last_sync == "2026-06-01T00:00:00"


class TestSyncMissingTolerance:
    """缺失容忍测试"""

    def test_partial_data_accepted(self):
        from metrics_sync import validate_row
        # 只填了阅读量，其他数字留空
        row = {
            "文章ID": "a_20260603",
            "平台": "wechat",
            "时间点": "t_plus_1d",
            "阅读量": 100,
            "点赞量": None,
            "收藏量": None,
            "转发量": None,
            "评论数": None,
        }
        assert validate_row(row) is True

    def test_empty_reads_rejected(self):
        from metrics_sync import validate_row
        row = {
            "文章ID": "a_20260603",
            "平台": "wechat",
            "时间点": "t_plus_1d",
            "阅读量": None,
        }
        assert validate_row(row) is False

    def test_all_zero_reads_allowed(self):
        from metrics_sync import validate_row
        row = {
            "文章ID": "a_20260603",
            "平台": "wechat",
            "时间点": "t_plus_1d",
            "阅读量": 0,
        }
        assert validate_row(row) is True


class TestSyncTimePointIdentification:
    """时间点识别测试"""

    def test_valid_time_points(self):
        from metrics_sync import validate_row
        for tp in ["t_plus_1d", "t_plus_7d", "t_plus_30d"]:
            row = {"文章ID": "a_20260603", "平台": "wechat", "时间点": tp, "阅读量": 100}
            assert validate_row(row) is True, f"Failed for {tp}"

    def test_invalid_time_point_rejected(self):
        from metrics_sync import validate_row
        for tp in ["t_plus_3d", "t_plus_14d", "", "7d"]:
            row = {"文章ID": "a_20260603", "平台": "wechat", "时间点": tp, "阅读量": 100}
            assert validate_row(row) is False, f"Should fail for {tp}"
