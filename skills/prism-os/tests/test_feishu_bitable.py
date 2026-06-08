"""Phase 6.0 — 飞书多维表格 API 封装测试"""
import pytest
import json
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestFeishuAuth:
    """鉴权测试（lark-cli 内置鉴权，无需手动 token）"""

    def test_client_creation(self):
        from feishu_bitable import FeishuBitable
        fb = FeishuBitable("base_token", "table_id")
        assert fb.base_token == "base_token"
        assert fb.table_id == "table_id"

    def test_from_config(self):
        from feishu_bitable import FeishuBitable
        import tempfile
        import os
        config_content = "base_token: test_base\ntable_id: test_table\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        try:
            fb = FeishuBitable.from_config(config_path)
            assert fb.base_token == "test_base"
            assert fb.table_id == "test_table"
        finally:
            os.unlink(config_path)


class TestFeishuRecords:
    """记录 CRUD 测试"""

    @patch("subprocess.run")
    def test_list_records(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({
                "ok": True,
                "data": {
                    "fields": ["文章ID", "阅读量"],
                    "data": [
                        ["test_20260603", 100],
                        ["test_20260604", 200],
                    ],
                    "has_more": False,
                },
            }),
            returncode=0,
        )
        from feishu_bitable import FeishuBitable

        fb = FeishuBitable("base_token", "table_id")
        records = fb.list_records()
        assert len(records) == 2
        assert records[0]["阅读量"] == 100

    @patch("subprocess.run")
    def test_list_records_pagination(self, mock_run):
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MagicMock(
                    stdout=json.dumps({
                        "ok": True,
                        "data": {
                            "fields": ["文章ID"],
                            "data": [["a"]],
                            "has_more": True,
                        },
                    }),
                    returncode=0,
                )
            else:
                return MagicMock(
                    stdout=json.dumps({
                        "ok": True,
                        "data": {
                            "fields": ["文章ID"],
                            "data": [["b"]],
                            "has_more": False,
                        },
                    }),
                    returncode=0,
                )

        mock_run.side_effect = side_effect
        from feishu_bitable import FeishuBitable

        fb = FeishuBitable("base_token", "table_id")
        records = fb.list_records()
        assert len(records) == 2

    @patch("subprocess.run")
    def test_create_record(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"ok": True, "data": {"record": {"record_id": "rec_new"}}}),
            returncode=0,
        )
        from feishu_bitable import FeishuBitable

        fb = FeishuBitable("base_token", "table_id")
        result = fb.create_record({"文章ID": "new_20260603", "阅读量": 50})
        assert result["record_id"] == "rec_new"

    @patch("subprocess.run")
    def test_batch_upsert(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"ok": True, "data": {"record": {"record_id": "r1"}}}),
            returncode=0,
        )
        from feishu_bitable import FeishuBitable

        fb = FeishuBitable("base_token", "table_id")
        records = [
            {"文章ID": "a_20260603", "时间点": "t_plus_1d", "阅读量": 100},
            {"文章ID": "a_20260603", "时间点": "t_plus_7d", "阅读量": 500},
        ]
        results = fb.batch_upsert(records)
        assert len(results) == 2
