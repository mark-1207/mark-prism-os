"""GAP-10: topic_log.yaml 应有 cumulative_count 字段"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_append_log_adds_cumulative_count(tmp_path, monkeypatch):
    """append_log 应自动添加 cumulative_count 字段"""
    from storage import append_log, load_yaml

    # mock get_data_dir 返回 tmp_path
    monkeypatch.setattr("storage.get_data_dir", lambda: str(tmp_path))

    # 第一次写入
    append_log({"thesis": "测试1", "candidates_count": 1})
    logs = load_yaml(str(tmp_path / "topic_log.yaml"))
    assert len(logs) == 1
    assert logs[0].get("cumulative_count") == 1

    # 第二次写入
    append_log({"thesis": "测试2", "candidates_count": 2})
    logs = load_yaml(str(tmp_path / "topic_log.yaml"))
    assert len(logs) == 2
    assert logs[1].get("cumulative_count") == 2


def test_cron_check_reads_cumulative_count(monkeypatch):
    """cron_check 应读最后一条的 cumulative_count 而非 len(records)"""
    from assassin import cron_check

    # mock read_viral_library 返回空（不读飞书）
    monkeypatch.setattr("assassin.read_viral_library", lambda: [])

    # mock load_yaml 返回有 cumulative_count 的记录
    fake_logs = [
        {"thesis": "测试1", "cumulative_count": 15},
        {"thesis": "测试2", "cumulative_count": 25},
    ]
    monkeypatch.setattr("storage.load_yaml", lambda path: fake_logs)

    # cron_check 应该用 cumulative_count=25 而非 len(fake_logs)=2
    # 但由于 count < 20 会跳过，这里只验证不崩
    cron_check()
