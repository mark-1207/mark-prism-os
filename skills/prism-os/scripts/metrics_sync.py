"""Phase 6.0 — 飞书多维表格增量同步到本地 snapshot"""
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "metrics_snapshot.yaml")
STATE_PATH = os.path.join(DATA_DIR, "metrics_sync_state.json")

VALID_TIME_POINTS = {"t_plus_1d", "t_plus_7d", "t_plus_30d"}


def validate_row(row: Dict) -> bool:
    """校验一行数据是否有效

    校验规则：
    - 文章ID 必填且非空
    - 平台 必填
    - 时间点 必须在 t_plus_1d/t_plus_7d/t_plus_30d 中
    - 阅读量 必须为非负整数（0 允许，None 允许表示缺失）
    """
    article_id = row.get("文章ID")
    if not article_id or not str(article_id).strip():
        return False

    platform = row.get("平台")
    if not platform:
        return False

    time_point = row.get("时间点")
    # 处理 select 字段可能是列表的情况
    if isinstance(time_point, list):
        time_point = time_point[0] if time_point else ''
    if time_point not in VALID_TIME_POINTS:
        return False

    reads = row.get("阅读量")
    if reads is None:
        return False  # 阅读量必填（允许为 0）
    try:
        if int(reads) < 0:
            return False
    except (ValueError, TypeError):
        return False

    # 其他数字字段：如果有值，必须非负
    for field in ["点赞量", "收藏量", "转发量", "评论数"]:
        val = row.get(field)
        if val is not None:
            try:
                if int(val) < 0:
                    return False
            except (ValueError, TypeError):
                return False

    return True


class MetricsSync:
    """飞书多维表格同步器"""

    def __init__(self, feishu_client=None, snapshot_path=None, state_path=None):
        self.feishu = feishu_client
        self.snapshot_path = snapshot_path or SNAPSHOT_PATH
        self.state_path = state_path or STATE_PATH
        self._snapshot = self._load_snapshot()
        self._last_sync = self._load_state()

    def _load_snapshot(self) -> List[Dict]:
        if not os.path.exists(self.snapshot_path):
            return []
        try:
            import yaml
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or []
        except (ImportError, Exception):
            try:
                with open(self.snapshot_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []

    def _load_state(self) -> Optional[str]:
        if not os.path.exists(self.state_path):
            return None
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                return state.get("last_synced_at")
        except Exception:
            return None

    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"last_synced_at": self._last_sync}, f, ensure_ascii=False)

    def _make_row_key(self, row: Dict) -> str:
        """生成行的唯一键：文章ID + 时间点"""
        article_id = row.get('文章ID', '')
        time_point = row.get('时间点', '')
        # 处理 select 字段可能是列表的情况
        if isinstance(time_point, list):
            time_point = time_point[0] if time_point else ''
        return f"{article_id}_{time_point}"

    def _save_to_snapshot(self, row: Dict):
        """保存到 snapshot（幂等：相同 key 不重复添加）"""
        key = self._make_row_key(row)
        # 检查是否已存在
        for i, existing in enumerate(self._snapshot):
            if self._make_row_key(existing) == key:
                # 更新现有记录
                self._snapshot[i] = row
                return
        # 新记录
        self._snapshot.append(row)

    def _save_snapshot_to_disk(self):
        os.makedirs(os.path.dirname(self.snapshot_path), exist_ok=True)
        try:
            import yaml
            with open(self.snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(self._snapshot, f, allow_unicode=True, default_flow_style=False)
        except ImportError:
            with open(self.snapshot_path, "w", encoding="utf-8") as f:
                json.dump(self._snapshot, f, ensure_ascii=False, indent=2)

    def sync(self) -> Dict:
        """执行增量同步

        Returns:
            {"new_rows": N, "invalid_rows": N, "status": "ok"}
        """
        if not self.feishu:
            return {"new_rows": 0, "invalid_rows": 0, "status": "no_client", "error": "未配置飞书客户端"}

        # 拉取飞书数据（增量）
        try:
            raw_records = self.feishu.list_records(modified_after=self._last_sync)
        except Exception as e:
            return {"new_rows": 0, "invalid_rows": 0, "status": "error", "error": str(e)}

        new_count = 0
        invalid_count = 0

        for record in raw_records:
            fields = record.get("fields", record)
            if validate_row(fields):
                self._save_to_snapshot(fields)
                new_count += 1
            else:
                invalid_count += 1

        # 保存到磁盘
        self._snapshot = [r for r in self._snapshot]  # 确保去重后的列表
        self._save_snapshot_to_disk()

        # 更新同步状态
        self._last_sync = datetime.now().isoformat()
        self._save_state()

        return {"new_rows": new_count, "invalid_rows": invalid_count, "status": "ok"}


def run_sync(feishu_client=None) -> Dict:
    """便捷入口"""
    syncer = MetricsSync(feishu_client=feishu_client)
    return syncer.sync()


if __name__ == "__main__":
    # CLI 入口
    print(json.dumps({
        "status": "ok",
        "message": "请通过 prism_os.py metrics sync 调用，或在代码中调用 run_sync(feishu_client)",
    }, ensure_ascii=False))
