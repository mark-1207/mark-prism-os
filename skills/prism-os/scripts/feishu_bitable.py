"""Phase 6.0 — 飞书多维表格 Open API 封装（通过 lark-cli，内置鉴权）"""
import json
import os
import subprocess
from typing import Dict, List, Optional

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "feishu_config.yaml")


class FeishuBitable:
    """飞书多维表格客户端（通过 lark-cli 调用，lark-cli 内置鉴权）"""

    def __init__(self, base_token: str, table_id: str):
        self.base_token = base_token
        self.table_id = table_id

    @classmethod
    def from_config(cls, config_path=None) -> "FeishuBitable":
        """从配置文件创建客户端"""
        path = config_path or CONFIG_PATH
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except ImportError:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)

        return cls(
            base_token=config.get("base_token", ""),
            table_id=config.get("table_id", ""),
        )

    def _run_lark_cli(self, args: List[str]) -> Dict:
        """运行 lark-cli 命令"""
        try:
            proc = subprocess.run(
                ["lark-cli"] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return json.loads(proc.stdout) if proc.stdout else {"ok": False, "error": {"message": proc.stderr}}
        except json.JSONDecodeError:
            return {"ok": False, "error": {"message": f"JSON parse error: {proc.stdout}"}}
        except FileNotFoundError:
            return {"ok": False, "error": {"message": "lark-cli not found in PATH"}}
        except Exception as e:
            return {"ok": False, "error": {"message": str(e)}}

    def list_records(self, modified_after: str = None) -> List[Dict]:
        """列出所有记录（自动分页）"""
        all_records = []
        offset = 0

        while True:
            result = self._run_lark_cli([
                "base", "+record-list",
                "--base-token", self.base_token,
                "--table-id", self.table_id,
                "--limit", "200",
                "--offset", str(offset),
            ])

            if not result.get("ok"):
                raise Exception(f"列出记录失败: {result.get('error', {}).get('message', 'unknown')}")

            data = result.get("data", {})
            fields = data.get("fields", [])
            records = data.get("data", [])

            if not records:
                break

            # lark-cli 返回数组格式：{fields: [...], data: [[...], [...]]}
            # 转换为字典格式
            for record_values in records:
                if isinstance(record_values, list) and fields:
                    record_dict = dict(zip(fields, record_values))
                    all_records.append(record_dict)
                elif isinstance(record_values, dict):
                    all_records.append(record_values)

            if not data.get("has_more", False):
                break
            offset += len(records)

        return all_records

    def create_record(self, fields: Dict) -> Dict:
        """创建记录"""
        result = self._run_lark_cli([
            "base", "+record-upsert",
            "--base-token", self.base_token,
            "--table-id", self.table_id,
            "--json", json.dumps(fields, ensure_ascii=False),
        ])
        if not result.get("ok"):
            raise Exception(f"创建记录失败: {result.get('error', {}).get('message', 'unknown')}")
        return result.get("data", {}).get("record", {})

    def batch_upsert(self, records: List[Dict]) -> List[Dict]:
        """批量创建记录"""
        results = []
        for record in records:
            try:
                result = self.create_record(record)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "fields": record})
        return results
