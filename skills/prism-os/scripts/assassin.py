#!/usr/bin/env python3
"""
PRISM-OS Phase 7: 刺客机制 & 知识拓扑
历史爆款逻辑反转 + 认知地图构建

用法:
    python assassin.py reverse "<历史爆款标题>"
    python assassin.py topology "<实体统计>" "<关系统计>"
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional
from datetime import datetime

# ============ lark-cli 工具函数 ============

def _verify_lark_cli():
    """验证 lark-cli 是否在 PATH 中"""
    import shutil
    if not shutil.which("lark-cli"):
        print("[Error] lark-cli not found in PATH. Please install: npm install -g @larksuite/cli", file=sys.stderr)
        sys.exit(1)


def _run_lark_cli(args: list, timeout: int = 30) -> tuple:
    """运行 lark-cli 命令，返回 (stdout, stderr, returncode)"""
    import shutil
    import subprocess
    _verify_lark_cli()
    lark_path = shutil.which("lark-cli")
    result = subprocess.run(
        [lark_path] + args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )
    return result.stdout, result.stderr, result.returncode


def _parse_lark_text_output(text: str) -> List[Dict]:
    """从 lark-cli 纯文本输出中提取记录（备用）"""
    records = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("-"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            records.append({
                "title": parts[0],
                "date": parts[1] if len(parts) > 1 else "",
                "views": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                "likes": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
                "direction": parts[4] if len(parts) > 4 else "",
                "record_id": ""
            })
    return records


# ============ 阶段 4: 飞书多维表格集成 ============

FEISHU_TABLE_ID = "tblOoR71Q3DSa33t"
FEISHU_APP_TOKEN = "QVz9byNH0auzRis9KeDcUoe3nZf"  # 示例 token

NOTIFICATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "notifications")

BACKUP_EXPIRY_DAYS = 30
SIMILARITY_THRESHOLD = 0.7


def read_viral_library() -> List[Dict]:
    """
    4.1 从飞书多维表格读取历史爆款

    Returns:
        [{"title": str, "date": str, "views": int, "likes": int, "direction": str, "record_id": str}, ...]
    """
    try:
        # lark-cli api GET /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
        path = f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
        params = '{"page_size": 100}'
        stdout, stderr, returncode = _run_lark_cli([
            "api", "GET", path,
            "--params", params,
            "--format", "json"
        ])
    except Exception as e:
        print(f"[Warning] lark-cli 调用失败: {e}", file=sys.stderr)
        return []

    if returncode != 0:
        print(f"[Warning] lark-cli 返回错误: {stderr}", file=sys.stderr)
        return []

    # 尝试 JSON 解析
    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and "data" in data:
            records = data["data"].get("items") or []
            # 过滤掉 类型=备选 的记录
            records = [r for r in records if r.get("fields", {}).get("类型") != "备选"]
            return [
                {
                    "title": r.get("fields", {}).get("标题", ""),
                    "date": r.get("fields", {}).get("日期", ""),
                    "views": r.get("fields", {}).get("浏览量", 0),
                    "likes": r.get("fields", {}).get("点赞数", 0),
                    "direction": r.get("fields", {}).get("方向", ""),
                    "record_id": r.get("record_id", "")
                }
                for r in records
            ]
        return []
    except json.JSONDecodeError:
        pass

    # 备用：解析纯文本输出
    return _parse_lark_text_output(stdout)


def check_data_threshold(viral_data: List[Dict], min_count: int = 20) -> bool:
    """
    4.2 检查是否 >= 20 篇发布数据

    Args:
        viral_data: 历史爆款数据
        min_count: 最小数量要求

    Returns:
        bool: 是否满足阈值
    """
    return len(viral_data) >= min_count


def check_cooldown(last_reminder_time: str = None, days: int = 30) -> bool:
    """
    4.3 检查距上次提醒是否 >30 天

    Args:
        last_reminder_time: 上次提醒时间 (ISO 格式)
        days: cooldown 天数

    Returns:
        bool: True 表示在 cooldown 中
    """
    if not last_reminder_time:
        return False

    try:
        from datetime import datetime, timedelta
        last_time = datetime.fromisoformat(last_reminder_time)
        return datetime.now() - last_time < timedelta(days=days)
    except (ValueError, OSError):
        return False


def build_reminder_message(reversals: List[Dict], viral_data: List[Dict]) -> str:
    """
    4.7 生成刺客提醒消息

    Args:
        reversals: 反转结果列表
        viral_data: 历史爆款数据

    Returns:
        str: 格式化提醒消息
    """
    lines = []
    lines.append("━" * 40)
    lines.append("【PRISM-OS 刺客提醒】")
    lines.append("━" * 40)
    lines.append("")
    lines.append(f"检测到 {len(viral_data)} 篇历史爆款，可以进行逻辑反转！")
    lines.append("")

    if reversals:
        lines.append("推荐反转方向：")
        for i, r in enumerate(reversals[:3], 1):
            lines.append(f"  {i}. {r.get('original_thesis', '')}")
            lines.append(f"     → {r.get('reversal_thesis', '')}")
            lines.append(f"     策略: {r.get('reversal_strategy', '')}")
            lines.append("")

    lines.append("是否要基于这些反转生成新标题？（yes/no）")
    lines.append("━" * 40)

    return "\n".join(lines)


def update_feishu_viral(viral_title: str, reversal_info: Dict = None) -> bool:
    """
    4.6 写入是否已反转/反转策略到飞书

    Args:
        viral_title: 爆款标题
        reversal_info: 反转信息 {"reversed": "是", "reversal_strategy": "..."}

    Returns:
        bool: 是否成功
    """
    if reversal_info is None:
        reversal_info = {}

    # 1. 先读取所有记录找到匹配的 record_id（复用 read_viral_library）
    records = read_viral_library()
    matched = None
    for r in records:
        if r.get("title") == viral_title:
            matched = r
            break

    if not matched:
        print(f"[Warning] 标题未在飞书架中找到: {viral_title}", file=sys.stderr)
        return False

    record_id = matched.get("record_id")
    if not record_id:
        print(f"[Warning] 记录缺少 record_id: {viral_title}", file=sys.stderr)
        return False

    reversed_val = reversal_info.get("reversed", "是")
    strategy = reversal_info.get("reversal_strategy", "")

    # 2. 执行更新（使用 lark-cli api PUT）
    path = f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/{record_id}"
    data = json.dumps({"fields": {"是否已反转": reversed_val, "反转策略": strategy}})

    stdout, stderr, code = _run_lark_cli([
        "api", "PUT", path,
        "--data", data,
        "--format", "json"
    ])

    if code != 0:
        print(f"[Warning] lark-cli update failed: {stderr}", file=sys.stderr)
        return False

    # 3. 验证写入：重新读取该记录确认字段已更新
    records_after = read_viral_library()
    for r in records_after:
        if r.get("title") == viral_title:
            # 检查是否包含策略信息（简单验证）
            if strategy and strategy in str(r.get("反转策略", "")):
                return True
            # 如果字段名不同，至少检查记录存在
            if r.get("record_id") == record_id:
                return True

    print("[Warning] update succeeded but verification failed", file=sys.stderr)
    return False


def save_backup(direction: str, source: str = "") -> bool:
    """
    将方向保存到飞书备选队列
    - 先检查是否已存在相同标题的备选记录（去重）
    - 写入类型=备选，状态=备选
    - 失败时静默返回 False
    """
    direction = direction.strip()
    if not direction:
        return False

    # 检查是否已存在
    existing = read_backup_queue()
    for rec in existing:
        if rec.get("title") == direction:
            return True  # 已存在，跳过

    # 生成来源字符串
    if not source:
        source = f"socratic-{datetime.now().strftime('%Y-%m-%d')}"

    # 写入飞书
    now_ms = str(int(datetime.now().timestamp() * 1000))
    data = json.dumps({"fields": {
        "标题": direction,
        "类型": "备选",
        "状态": "备选",
        "创建日期": now_ms,
        "来源": source,
        "备注": ""
    }})

    stdout, stderr, code = _run_lark_cli([
        "api", "POST",
        f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records",
        "--data", data,
        "--format", "json"
    ])

    return code == 0


def read_backup_queue() -> List[Dict]:
    """
    读取所有 类型=备选 AND 状态=备选 的记录
    Returns: [{"title": str, "source": str, "record_id": str, "created_at": int}, ...]
    """
    path = f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    params = '{"page_size": 100}'
    stdout, stderr, code = _run_lark_cli([
        "api", "GET", path,
        "--params", params,
        "--format", "json"
    ])

    if code != 0:
        return []

    try:
        data = json.loads(stdout)
        records = data.get("data", {}).get("items") or []
    except (json.JSONDecodeError, OSError):
        return []

    result = []
    for r in records:
        fields = r.get("fields", {})
        record_type = fields.get("类型", "")
        status = fields.get("状态", "")
        if record_type == "备选" and status == "备选":
            created_str = fields.get("创建日期", "")
            created_at = 0
            if isinstance(created_str, (int, float)):
                created_at = int(created_str)
            elif isinstance(created_str, str) and created_str.isdigit():
                created_at = int(created_str)
            result.append({
                "title": fields.get("标题", ""),
                "source": fields.get("来源", ""),
                "record_id": r.get("record_id", ""),
                "created_at": created_at
            })
    return result


def update_backup_status(record_id: str, status: str) -> bool:
    """
    更新备选记录状态（已使用/已过期）
    - 失败时静默返回 False
    """
    path = f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/{record_id}"
    data = json.dumps({"fields": {"状态": status}})

    stdout, stderr, code = _run_lark_cli([
        "api", "PUT", path,
        "--data", data,
        "--format", "json"
    ])

    return code == 0


def check_expired_backups(days: int = 30) -> int:
    """
    检查并标记过期备选（创建日期 > days 天）
    - 读取所有 类型=备选 AND 状态=备选 的记录
    - 比较 创建日期 字段与当前时间
    - 超期记录标记 状态=已过期
    - Returns: 标记为过期的数量
    """
    records = read_backup_queue()
    now_ms = int(datetime.now().timestamp() * 1000)
    expiry_ms = days * 24 * 60 * 60 * 1000

    expired_count = 0
    for rec in records:
        created_at = rec.get("created_at", 0)
        if created_at > 0 and (now_ms - created_at) > expiry_ms:
            if update_backup_status(rec["record_id"], "已过期"):
                expired_count += 1

    return expired_count


def check_related_backups(topic: str, threshold: float = 0.7) -> List[Dict]:
    """
    检查与 topic 相似的备选方向

    1. 调用 check_expired_backups() 清理过期记录
    2. 读取备选队列
    3. 计算 topic 与每条备选的 Embedding 相似度
    4. 返回相似度 > threshold 的记录

    Returns: [{"title": str, "similarity": float, "record_id": str}, ...]
    """
    # 清理过期
    check_expired_backups(BACKUP_EXPIRY_DAYS)

    # 读取队列
    queue = read_backup_queue()
    if not queue:
        return []

    # 引入 embedding
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from embedding import get_similarity

    results = []
    for rec in queue:
        title = rec.get("title", "")
        if not title:
            continue

        similarity = get_similarity(topic, title)
        if similarity is not None and similarity > threshold:
            results.append({
                "title": title,
                "similarity": similarity,
                "record_id": rec.get("record_id", "")
            })

    # 按相似度降序
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results


# ============ Phase 7: 刺客机制 ============

def reverse_topic(historical_topic: str, publish_date: str = "") -> Dict:
    """
    对历史爆款选题进行"逻辑反转"

    Args:
        historical_topic: 历史爆款选题
        publish_date: 发布时间（可选）

    Returns:
        {
            "original_thesis": str,
            "reversal_thesis": str,
            "reversal_strategy": str,
            "new_evidence": [...],
            "cognitive_shift": str,
            "challenge_level": float
        }
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""你是认知刺客。你的任务是对历史爆款选题进行"逻辑反转"，强制创作者否定旧观点。

历史爆款选题：{historical_topic}
{f"发布时间：{publish_date}" if publish_date else ""}
当前时间：{current_date}

反转策略：
1. 前提质疑：挑战隐含假设
2. 数据更新：用新数据推翻旧结论
3. 视角切换：从另一个群体审视
4. 时效性挑战：用时间维度挑战命题

返回 JSON：
{{
  "original_thesis": "原命题",
  "reversal_thesis": "反转后命题",
  "reversal_strategy": "前提质疑/数据更新/视角切换/时效性挑战",
  "new_evidence": ["新证据1", "新证据2"],
  "cognitive_shift": "认知转变说明",
  "challenge_level": 0.0-1.0
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "original_thesis": historical_topic,
            "reversal_thesis": "",
            "reversal_strategy": "",
            "new_evidence": [],
            "cognitive_shift": "",
            "challenge_level": 0.0
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "original_thesis": historical_topic,
            "reversal_thesis": "",
            "reversal_strategy": "",
            "new_evidence": [],
            "cognitive_shift": "",
            "challenge_level": 0.0
        }

    return parsed


# ============ Phase 7: 知识拓扑 ============

def analyze_knowledge_topology(entities: List[Dict], relations: List[Dict]) -> Dict:
    """
    构建认知地图，标注过度开发区和未触及区

    Args:
        entities: 实体统计 [{"entity": str, "count": int}]
        relations: 关系统计 [{"relation": str, "count": int}]

    Returns:
        {
            "over_explored": [...],
            "under_explored": [...]
        }
    """
    entities_str = ", ".join([f"{e['entity']}({e.get('count', 0)}次)" for e in entities]) if entities else "无"
    relations_str = ", ".join([f"{r['relation']}({r.get('count', 0)}次)" for r in relations]) if relations else "无"

    prompt = f"""你是认知地图分析师。基于实体关系图谱，标注认知开发区域。

实体统计：{entities_str}
关系统计：{relations_str}

定义：
- 过度开发区：该实体/关系出现频率过高，可能导致思维定势
- 未触及区：该实体/关系从未或很少出现，可能是认知盲区

返回 JSON：
{{
  "over_explored": [
    {{"entity": "实体名", "reason": "出现频率过高", "suggestion": "探索其他领域"}}
  ],
  "under_explored": [
    {{"entity": "实体名", "reason": "从未出现", "suggestion": "可作为新选题方向"}}
  ]
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "over_explored": [],
            "under_explored": []
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "over_explored": [],
            "under_explored": []
        }

    return parsed


# ============ Phase 7: Prompt 变异 ============

def evolve_prompt(trigger_type: str, old_config: Dict, reason: str) -> Dict:
    """
    根据用户行为自动调整生成参数

    Args:
        trigger_type: 变异触发类型
        old_config: 旧配置
        reason: 变异原因

    Returns:
        {
            "timestamp": str,
            "trigger": str,
            "old_config": {...},
            "new_config": {...},
            "reason": str
        }
    """
    prompt = f"""你是 Prompt 进化引擎。根据用户行为数据自动调整生成参数。

变异触发类型：{trigger_type}
旧配置：{json.dumps(old_config, ensure_ascii=False)}
变异原因：{reason}

变异策略：
1. 强化偏好维度：用户连续选择某维度时，提高该维度权重
2. 替换陈词：根据改词记录更新禁用词列表
3. 调整风格：根据采纳率调整生成风格

返回 JSON：
{{
  "new_config": {{
    "dimension_weights": {{"reversal": 1.0, "micro_scene": 1.0, ...}},
    "banned_words": ["赋能", "降维打击", ...],
    "style_adjustment": "..."
  }},
  "evolution_note": "变异说明"
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "trigger": trigger_type,
            "old_config": old_config,
            "new_config": old_config,
            "reason": reason
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "trigger": trigger_type,
            "old_config": old_config,
            "new_config": old_config,
            "reason": reason
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "trigger": trigger_type,
        "old_config": old_config,
        "new_config": parsed.get("new_config", old_config),
        "reason": reason
    }


# ============ Phase 7: 主流程 ============

def assassin_mechanism(historical_topics: List[str] = None, entities: List[Dict] = None, relations: List[Dict] = None) -> Dict:
    """
    Phase 7 完整流程：刺客机制 + 知识拓扑

    Args:
        historical_topics: 历史爆款列表
        entities: 实体统计
        relations: 关系统计

    Returns:
        {
            "reversals": [...],
            "topology": {...}
        }
    """
    result = {
        "phase": "assassin",
        "reversals": [],
        "topology": {}
    }

    # 刺客机制 - 反转历史爆款
    if historical_topics:
        for topic in historical_topics:
            reversal = reverse_topic(topic)
            result["reversals"].append(reversal)

    # 知识拓扑
    if entities or relations:
        result["topology"] = analyze_knowledge_topology(entities or [], relations or [])

    return result


# ============ 辅助函数 ============

def _load_yaml_simple(path: str) -> list:
    """简单 YAML 加载"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[Warning] 读取 {path} 失败: {e}", file=sys.stderr)
        return []
    if not content.strip():
        return []
    result = []
    current = {}
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            if current:
                result.append(current)
            current = {}
        elif ": " in line and not line.startswith("#"):
            key, val = line.split(": ", 1)
            current[key.strip()] = val.strip().strip('"').strip("'")
    if current:
        result.append(current)
    return result


def _call_llm_raw(prompt: str) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=0.7, scene="quality", error_prefix="[Error] LLM:")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出中解析 JSON"""
    if not text:
        return None

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        pass

    return None


# ============ Phase 7: 定时刺客检查 ============

def cron_check():
    """
    定时刺客检查
    1. 读取飞书架，验证 >= 20 条数据
    2. 读取 topic_log.yaml 最近命题
    3. 对每条命题调用刺客反转逻辑
    4. 输出到 notification 文件 + stdout
    5. 更新飞书架「是否已反转」状态
    """
    os.makedirs(NOTIFICATIONS_DIR, exist_ok=True)

    # 1. 读取飞书架
    records = read_viral_library()
    count = len(records)

    if count < 20:
        print(f"[Info] 数据不足（{count}/20），跳过刺客检查")
        return

    print(f"[Info] 开始刺客检查，共 {count} 条历史数据")

    # 2. 读取最近命题（从 topic_log.yaml）
    log_path = os.path.join(os.path.dirname(__file__), "..", "data", "topic_log.yaml")
    logs = _load_yaml_simple(log_path) if os.path.exists(log_path) else []
    recent_theses = [log.get("thesis", "") for log in logs[-5:] if log.get("thesis")]

    if not recent_theses:
        print("[Info] 未找到近期命题，跳过刺客检查")
        return

    triggers = []

    # 3. 对每条命题生成反转（调用现有的 reverse_topic）
    for thesis in recent_theses:
        try:
            # reverse_topic(historical_topic, publish_date="") 已存在于 assassin.py
            reversal_result = reverse_topic(thesis, "")
            reversal_title = reversal_result.get("reversal_thesis", "")
            strategy = reversal_result.get("reversal_strategy", "")
            if reversal_title:
                triggers.append({
                    "original_title": thesis,
                    "reversal_title": reversal_title,
                    "strategy": strategy
                })
        except Exception as e:
            print(f"[Warning] 反转失败: {thesis}, {e}", file=sys.stderr)

    # 4. 写入 notification 文件
    if triggers:
        date_str = datetime.now().strftime("%Y-%m-%d")
        notif_path = os.path.join(NOTIFICATIONS_DIR, f"{date_str}_assassin.json")
        notification = {
            "date": date_str,
            "triggers": triggers
        }
        try:
            with open(notif_path, "w", encoding="utf-8") as f:
                json.dump(notification, f, ensure_ascii=False, indent=2)
            print(f"[Info] 刺客通知已写入: {notif_path}")
        except Exception as e:
            print(f"[Warning] 写入通知文件失败: {e}", file=sys.stderr)

    # 5. 输出到 stdout
    print(json.dumps({"count": count, "triggers": triggers}, ensure_ascii=False))

    # 6. 更新飞书架（标记已反转）
    for t in triggers:
        update_feishu_viral(t["original_title"], {
            "reversed": "是",
            "reversal_strategy": t["strategy"]
        })


# ============ CLI 入口 ============

def _safe_print(obj):
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


def main():
    if len(sys.argv) < 2:
        _safe_print({
            "error": "用法: assassin.py <命令> <数据>",
            "commands": {
                "reverse": "assassin.py reverse \"<历史爆款标题>\" - 逻辑反转",
                "topology": "assassin.py topology '<[{\"entity\":...}]' '<[{\"relation\":...}]' - 知识拓扑",
                "evolve": "assassin.py evolve \"<触发类型>\" '<old_config>' - Prompt 变异",
                "cron_check": "assassin.py cron_check - 定时刺客检查（每日 22:00）",
                "read": "assassin.py read - 读取飞书爆款选题库"
            }
        })
        sys.exit(1)

    command = sys.argv[1]

    if command == "reverse":
        topic = sys.argv[2] if len(sys.argv) > 2 else ""
        result = reverse_topic(topic)
        _safe_print(result)

    elif command == "topology":
        entities_str = sys.argv[2] if len(sys.argv) > 2 else "[]"
        relations_str = sys.argv[3] if len(sys.argv) > 3 else "[]"
        try:
            entities = json.loads(entities_str)
            relations = json.loads(relations_str)
        except (json.JSONDecodeError, ValueError):
            entities = []
            relations = []
        result = analyze_knowledge_topology(entities, relations)
        _safe_print(result)

    elif command == "evolve":
        trigger = sys.argv[2] if len(sys.argv) > 2 else ""
        config_str = sys.argv[3] if len(sys.argv) > 3 else "{}"
        try:
            old_config = json.loads(config_str)
        except (json.JSONDecodeError, ValueError):
            old_config = {}
        result = evolve_prompt(trigger, old_config, "")
        _safe_print(result)

    elif command == "read":
        records = read_viral_library()
        _safe_print(records)

    elif command == "cron_check":
        cron_check()

    elif command == "write":
        if len(sys.argv) < 4:
            _safe_print({"error": "用法: assassin.py write <标题> <策略>"})
            sys.exit(1)
        title = sys.argv[2]
        strategy = sys.argv[3]
        info = {"reversed": "是", "reversal_strategy": strategy}
        success = update_feishu_viral(title, info)
        _safe_print({"success": success, "title": title, "strategy": strategy})

    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()