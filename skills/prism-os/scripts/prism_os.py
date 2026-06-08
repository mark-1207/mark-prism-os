#!/usr/bin/env python3
"""
PRISM-OS 主流程脚本
逐阶段 CLI：每阶段独立命令，AI 按 SKILL.md 对话流逐步调用

用法:
    python prism_os.py run "<用户输入>"            # 完整流程（JSON输出）
    python prism_os.py run "<用户输入>" --format    # 完整流程（可读格式）
    python prism_os.py run "<用户输入>" --no-ext     # 仅 Phase 0-3
    python prism_os.py classify "<用户输入>"         # Phase 0: 意图识别
    python prism_os.py gateway "<用户输入>"          # Phase 1: 苏格拉底网关
    python prism_os.py prism "<命题>"               # Phase 2: 棱镜引擎
    python prism_os.py anchor --input <file>        # Phase 3: 现实校验锚
    python prism_os.py twin --input <file>          # Phase 3.5: 数字分身筛选
    python prism_os.py gap "<命题>"                  # Phase 4.6: Gap Analysis
    python prism_os.py logic --input <file>         # Phase 5: 逻辑压力测试
    python prism_os.py save --thesis "<命题>"        # Phase 6: 数据持久化
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import subprocess
import shutil

# ============ 终端 UTF-8 编码（修复 Windows 中文乱码）============

if sys.platform == "win32":
    # Windows 终端默认 GBK，强制 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Python < 3.7 降级
        import io
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ============ stdin 检测 helper ============

def _stdin_unavailable_warning(decision_point: str) -> bool:
    """检测 stdin 不可用 + 打印 explicit warning；返回 True 表示不可用"""
    if sys.stdin.isatty():
        return False
    print(
        f"[WARNING] 决策点 {decision_point} 需要 stdin 输入但 stdin 不可用。"
        f"建议前台重跑，或加 --no-interactive 跳过人工决策。",
        file=sys.stderr,
    )
    return True

# ============ lark-cli 工具函数 ============

FEISHU_TABLE_ID = "tblOoR71Q3DSa33t"
FEISHU_APP_TOKEN = "QVz9byNH0auzRis9KeDcUoe3nZf"

def _verify_lark_cli():
    """验证 lark-cli 是否在 PATH 中"""
    if not shutil.which("lark-cli"):
        print("[Error] lark-cli not found in PATH", file=sys.stderr)
        sys.exit(1)

def _run_lark_cli(args: list, timeout: int = 30) -> tuple:
    """运行 lark-cli 命令"""
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

# ============ Phase 0: 意图识别 ============

def classify_intent(user_input: str) -> Dict:
    """
    意图识别 - 判断是否触发 PRISM-OS
    LLM 二分类：这段话是否构成内容选题/写作意图？
    """
    # 疑问句模式：短句末尾带"吗/么/吧/呀"，或含"怎么/如何/有没有"
    text = user_input.strip()
    short_question = (
        len(text) < 40
        and any(text.endswith(p) for p in ["吗", "么", "吧", "呀", "吗？", "么？", "吧？", "呀？", "？"])
        and not any(kw in text for kw in ["写", "文章", "选题", "帮我", "生成", "策划", "创作"])
    )

    # 强意图词
    strong_intent = any(kw in text for kw in ["帮我写", "帮我做", "生成标题", "策划", "写一篇", "写一篇", "做个", "创作"])

    # 闲聊/纯事实性问题（明确不触发）
    small_talk = any(kw in text for kw in ["你好", "天气", "几号", "今天", "明天", "叫什么名字", "你是谁"])

    if small_talk:
        return {"trigger": False, "confidence": 0.9, "reason": "闲聊/纯事实，不触发"}
    if strong_intent:
        return {"trigger": True, "confidence": 0.95, "reason": "包含明确写作意图"}
    if short_question:
        return {"trigger": True, "confidence": 0.7, "reason": "话题疑问句，视为隐式选题"}

    # 调用 LLM 做意图分类
    try:
        from call_llm import call_llm
        prompt = f"""判断以下用户输入是否构成内容选题或写作意图。

判断标准（满足任一即为是）：
- 用户想写/做/创作内容（文章、短视频、选题策划等）
- 用户想讨论一个值得做成内容的话题方向
- 用户在问一个关于趋势、商业、职业、认知等值得探讨的问题

不符合的例子：
- 纯闲聊（你好、天气怎么样）
- 用户只是分享心情不想做内容
- 用户在问一个纯事实性问题（今天几号）

输入："{text}"

返回 JSON：
{{"trigger": true或false, "reason": "判断理由（10字内）"}}
"""
        result = call_llm(prompt)
        if result and not result.get("error") and result.get("content"):
            import re
            content = result["content"]
            # 先尝试提取 code block 中的内容（有捕获组 → group(1)）
            code_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
            if code_match:
                text_to_parse = code_match.group(1)
            else:
                # 否则直接找 JSON 对象
                brace_match = re.search(r'\{.*\}', content, re.DOTALL)
                if brace_match:
                    text_to_parse = brace_match.group(0)
                else:
                    text_to_parse = content
            parsed = json.loads(text_to_parse)
            return {
                "trigger": parsed.get("trigger", False),
                "confidence": 0.6,
                "reason": parsed.get("reason", "")
            }
    except (ImportError, json.JSONDecodeError, AttributeError, KeyError, TypeError, IndexError) as e:
        print(f"[Warning] classify_intent LLM 解析失败: {e}", file=sys.stderr)

    # fallback：LLM 不可用时默认触发（安全侧，宁放过不错杀）
    return {"trigger": True, "confidence": 0.3, "reason": "无法判断，默认触发PRISM-OS"}


# ============ 辅助函数 ============

def _load_yaml_simple(path: str) -> list:
    """简单 YAML 加载"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
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

def confirm_title(user_title: str) -> Dict:
    """
    将用户选择的标题写入飞书爆款选题库
    写入字段：标题、发布日期、命题逻辑、核心论点、内容方向、备注
    """
    # 输入校验
    title = user_title.strip()
    if not title:
        return {"success": False, "error": "标题不能为空"}
    if len(title) > 200:
        title = title[:200]

    # 从 topic_log.yaml 读取最近命题
    thesis = "（未记录）"
    core_argument = "（未记录）"

    log_path = os.path.join(os.path.dirname(__file__), "..", "data", "topic_log.yaml")
    if os.path.exists(log_path):
        try:
            logs = _load_yaml_simple(log_path)
            if logs:
                last = logs[-1]
                thesis = last.get("thesis", "（未记录）")
                if "gateway" in last and isinstance(last.get("gateway"), dict):
                    core_argument = last["gateway"].get("thesis", "（未记录）")
        except Exception as e:
            print(f"[Warning] 读取 topic_log.yaml 失败: {e}", file=sys.stderr)

    # 生成 lark-cli 写入命令
    # 飞书 datetime 字段需要 Unix 时间戳（毫秒）
    now = str(int(datetime.now().timestamp()))
    stdout, stderr, code = _run_lark_cli([
        "api", "POST",
        f"/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records",
        "--data", json.dumps({"fields": {
            "标题": title,
            "命题逻辑": thesis,
            "核心论点": core_argument,
            "内容方向": "（未分类）",
            "备注": ""
        }}),
        "--format", "json"
    ])

    if code != 0:
        print(f"[Error] lark-cli create failed: {stderr}", file=sys.stderr)
        return {"success": False, "error": stderr, "title": title}

    # 验证写入
    try:
        resp_data = json.loads(stdout)
        record_id = resp_data.get("data", {}).get("record", {}).get("record_id", "")
        return {"success": True, "title": title, "record_id": record_id}
    except json.JSONDecodeError:
        return {"success": True, "title": title, "note": "写入成功但无法解析返回ID"}


# ============ PRISM-OS 主流程（Pipeline 重构版） ============

def run_prism_os(
    user_input: str,
    identity_role: str = "",
    audience: str = "",
    include_phase_4_8: bool = True,
    materials: str = "",
    history_topics: List[str] = None,
    skip_gateway: bool = False,
    platform: str = "both",
    interactive: bool = True,
    user_clarification: str = None,
    ccos_review: bool = True,
    _state = None,
    panic_on_error: bool = False,
    dry_run: bool = False,
) -> Dict:
    """
    PRISM-OS 完整工作流程（Pipeline 版）

    Args:
        user_input: 用户输入
        identity_role: 用户身份（可选）
        audience: 目标受众（可选）
        include_phase_4_8: 是否包含 Phase 4-8（默认 True）
        materials: 现有素材（可选）
        history_topics: 历史选题列表（可选）
        skip_gateway: 跳过 Phase 1 熵值判断（默认 False）

    Returns:
        完整流程结果
    """
    from phases import FullPrismPipeline, PipelineConfig, PhaseResult

    config = PipelineConfig(
        platform=platform,
        interactive=interactive,
        skip_gateway=skip_gateway,
        skip_ccos_review=not ccos_review,
        include_phase_4_8=include_phase_4_8,
        include_narrate=True,
        user_clarification=user_clarification,
        history_topics=history_topics or [],
        panic_on_error=panic_on_error,
        dry_run=dry_run,
    )
    pipeline = FullPrismPipeline(config)

    # 如果调用方传了 _state 进来（恢复状态），从 state 恢复
    if _state is not None:
        pipeline.state = _state

    state = pipeline.run(user_input)
    result = state.to_dict()

    # need_input 状态：把 prompt 加入返回结果，方便调用方处理
    if state.status == "need_input":
        result["status"] = "need_input"
        result["current_phase"] = state.phase
        result["_prompt"] = getattr(state, "_pending_prompt", "")
        result["_input_type"] = getattr(state, "_pending_input_type", "")

    # 始终返回 current_phase_index 以便 continue 时恢复
    result["current_phase_index"] = state.current_phase_index
    return result


def run_prism_os_continue(user_reply: str, previous_state: dict, **kwargs) -> dict:
    """继续执行 pipeline（用户回复决策点后调用）

    Args:
        user_reply: 用户的回复内容
        previous_state: 之前 run_prism_os 返回的完整结果字典
        **kwargs: 同 run_prism_os 的参数

    Returns:
        新的 run_prism_os 结果字典
    """
    from phases import FullPrismPipeline, PipelineConfig, PipelineState

    config = PipelineConfig(
        platform=kwargs.get("platform", previous_state.get("platform", "both")),
        interactive=kwargs.get("interactive", True),
        skip_gateway=kwargs.get("skip_gateway", False),
        skip_ccos_review=not kwargs.get("ccos_review", True),
        include_phase_4_8=kwargs.get("include_phase_4_8", True),
        include_narrate=True,
        user_clarification=kwargs.get("user_clarification"),
        history_topics=kwargs.get("history_topics") or [],
    )
    pipeline = FullPrismPipeline(config)

    # 从 previous_state 恢复 state
    state = PipelineState(
        thesis=previous_state.get("user_input", ""),
        platform=config.platform,
        interactive=config.interactive,
    )
    state.current_phase_index = previous_state.get("current_phase_index", 0)
    state.intent = previous_state.get("intent")
    state.gateway = previous_state.get("gateway")
    state.candidates = previous_state.get("candidates", [])
    state.selected_candidate = previous_state.get("selected_candidate")
    state.user_selected_candidate = previous_state.get("user_selected_candidate", False)
    state.ccos_outline = previous_state.get("ccos_outline")
    state.ccos_review_passed = previous_state.get("ccos_review_passed", False)
    state.gap_analysis = previous_state.get("gap_analysis")
    state.gap_decision = previous_state.get("gap_decision")

    state.user_reply = user_reply
    state.status = "running"

    # Pipeline 继续执行时需要从 current_phase_index 开始
    new_state = pipeline.run(state.thesis, resume_state=state)
    result = new_state.to_dict()

    if new_state.status == "need_input":
        result["status"] = "need_input"
        result["current_phase"] = new_state.phase
        result["_prompt"] = getattr(new_state, "_pending_prompt", "")
        result["_input_type"] = getattr(new_state, "_pending_input_type", "")

    # 始终返回 current_phase_index 以便下次继续
    result["current_phase_index"] = new_state.current_phase_index
    return result


# ============ 辅助函数 ============

def _run_narrate(topic: str, platform: str) -> dict:
    """内部 narrate 调用：加载 CCOS → 生成内容 → 落盘文件。失败抛异常。"""
    from content_generator import (
        narrative_generation_workflow,
        _load_ccos_for_topic,
    )

    ccos_outline = _load_ccos_for_topic(topic, platform)
    if not ccos_outline:
        raise RuntimeError(f'未找到命题 "{topic}" 的 CCOS 大纲')

    from template_scorer import load_calibration
    calibration = load_calibration()
    result = narrative_generation_workflow(topic, ccos_outline, platform, auto_scrape=False, calibration=calibration)

    # 落盘
    draft = result.get("full_draft", "")
    if draft:
        safe_title = _safe_filename(topic)
        from datetime import date
        date_str = date.today().strftime("%Y%m%d")
        out_path = Path(f"{safe_title}_{date_str}.md")
        out_path.write_text(f"# {topic}\n\n---\n\n" + draft, encoding="utf-8")
        print(f"[输出] 草稿已保存至 {out_path.resolve()}", file=sys.stderr)
        result["output_file"] = str(out_path.resolve())

    return result


def _run_gap_decision_loop(thesis: str, gap_result: dict, platform: str = "wechat") -> str:
    """展示 Gap 结果 + 4 选项循环。返回 'go_narrate' | 'restart_ccos' | 'add_material' | 'exit'"""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
    print("【素材就绪度分析】", file=sys.stderr)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
    gap_score = gap_result.get("gap_score", 0)
    readiness = gap_result.get("readiness", 0)
    print(f"  Gap Score:   {gap_score:.2f} {'(缺口较大)' if gap_score > 0.5 else '(缺口较小)'}", file=sys.stderr)
    print(f"  就绪度:      {readiness:.0%}", file=sys.stderr)
    missing = gap_result.get("missing_evidence", [])
    if missing:
        print(f"  缺失证据:   {', '.join(missing[:5])}", file=sys.stderr)
    search_results = gap_result.get("knowledge", {}).get("knowledge_results", [])
    if search_results:
        print(f"  搜索命中:   {len(search_results)} 条", file=sys.stderr)
    print("", file=sys.stderr)

    print("请选择下一步操作：", file=sys.stderr)
    print("  [1] 补充手写素材入库", file=sys.stderr)
    print("  [2] 调整大纲方向（重新生成CCOS）", file=sys.stderr)
    print("  [3] 直接使用搜到的数据生成草稿", file=sys.stderr)
    print("  [q] 退出", file=sys.stderr)
    print("", file=sys.stderr)

    while True:
        print("请输入选项（1/2/3/q）：", file=sys.stderr)
        try:
            choice = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            _stdin_unavailable_warning("3（Gap 决策）")
            return "exit"

        if choice.lower() == "q":
            print("退出", file=sys.stderr)
            return "exit"

        if choice == "1":
            print("请输入素材内容（输入空行结束）：", file=sys.stderr)
            lines = []
            try:
                while True:
                    line = input()
                    if not line.strip():
                        break
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                lines = []
            user_material = "\n".join(lines).strip()
            if user_material:
                print(f"[素材入库] 已记录 {len(user_material)} 字素材", file=sys.stderr)
            return "add_material"

        elif choice == "2":
            print("[操作] 重新生成 CCOS 大纲", file=sys.stderr)
            return "restart_ccos"

        elif choice == "3":
            print("[操作] 进入叙事生成", file=sys.stderr)
            return "go_narrate"

        else:
            print("无效选项，请输入 1、2、3 或 q", file=sys.stderr)


def _safe_filename(title: str) -> str:
    """将标题转为合法的文件名（去除 <>:"|?* 等非法字符）"""
    safe = title
    for ch in "<>:\"|?*":
        safe = safe.replace(ch, "_")
    # 去除连续下划线和首尾空格
    while "__" in safe:
        safe = safe.replace("__", "_")
    safe = safe.strip("_ ")
    return safe or "untitled"


def _format_ccos_review(ccos_outline: Dict, title: str, platform: str) -> str:
    """
    格式化 CCOS 大纲审核显示：每个模块的"模块名 + 功能 + 篇幅"
    目的是让用户理解"为何是这个模块用这个"
    """
    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "【CCOS 大纲审核】",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"标题: {title}",
        f"平台: {platform}",
        "",
    ]

    # 核心信息
    content_goal = ccos_outline.get("内容目标", "未指定")
    main_structure = ccos_outline.get("主结构", "未指定")
    progression = ccos_outline.get("推进方式", "未指定")
    立场 = ccos_outline.get("内容立场", "")
    冲突 = ccos_outline.get("核心认知冲突", "")
    情绪曲线 = ccos_outline.get("情绪曲线", [])
    lines.append(f"内容目标: {content_goal}")
    if 立场:
        lines.append(f"立场: {立场}")
    if 冲突:
        lines.append(f"核心冲突: {冲突}")
    lines.append(f"主结构: {main_structure}")
    lines.append(f"推进方式: {progression}")
    lines.append("")

    # 模块流（每个模块：模块名 + 功能 + 篇幅 + 内容摘要）
    modules = ccos_outline.get("认知模块流", [])
    if modules:
        lines.append("模块流：")
        for i, m in enumerate(modules, 1):
            mod_name = m.get("模块", "?")
            mod_func = m.get("功能", "未指定")
            mod_length = m.get("篇幅", "未指定")
            mod_summary = m.get("内容摘要", "")
            lines.append(f"  {i}. {mod_name} ({mod_length}) — {mod_func}")
            if mod_summary:
                lines.append(f"     {mod_summary[:80]}")
        lines.append("")

    # 最终大纲
    final_outline = ccos_outline.get("最终动态认知大纲", "")
    if final_outline:
        lines.append("最终大纲：")
        lines.append(f"  {final_outline[:200]}{'...' if len(final_outline) > 200 else ''}")
        lines.append("")

    # 情绪曲线
    if 情绪曲线:
        lines.append(f"情绪曲线: {'→'.join(情绪曲线)}")
        lines.append("")

    return "\n".join(lines)

def format_prism_os_output(result: Dict) -> str:
    """
    将 run_prism_os() 返回的 JSON 格式化为可读报告
    """
    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "【PRISM-OS 选题结果】",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ""
    ]

    # HKR 评分展示
    hkr = result.get("hkr")
    if hkr:
        lines.append("■ HKR 选题质量评分")
        lines.append(f"  H(愉悦度): {'█' * max(1, int(hkr.get('h', 0) * 10))} {hkr.get('h', 0):.1f}")
        lines.append(f"  K(知识增量): {'█' * max(1, int(hkr.get('k', 0) * 10))} {hkr.get('k', 0):.1f}")
        lines.append(f"  R(情感共鸣): {'█' * max(1, int(hkr.get('r', 0) * 10))} {hkr.get('r', 0):.1f}")
        lines.append(f"  综合: {hkr.get('hkr_avg', 0):.1f}")
        combined = result.get("combined_score")
        if combined is not None:
            lines.append(f"  联合评分(entropy×0.4+HKR×0.6): {combined:.1f}")
        lines.append("")

    # 候选标题
    candidates = result.get("candidates", [])
    if candidates:
        lines.append("■ 候选标题（按综合评分排序）")
        dim_names = {
            "reversal": "逆向拆解",
            "micro_scene": "微观切片",
            "systemic_flaw": "系统归因",
            "bridge": "认知脚手架"
        }

        for i, c in enumerate(candidates, 1):
            dim = c.get("dimension", "")
            dim_name = dim_names.get(dim, dim)
            title = c.get("title", "")
            comp = c.get("competition_level", "未知")
            novelty = c.get("novelty_score", 0)
            novelty_pct = int(novelty * 100) if novelty else 0

            # 逻辑审计标记
            logic_mark = "✓"
            if "logic_audit" in result:
                for audit in result.get("logic_audit", []):
                    if audit.get("title") == title and audit.get("has_fallacy"):
                        logic_mark = "⚠"
                        break

            lines.append(f"  {i} [{dim_name}] {logic_mark} {title}")
            lines.append(f"     {comp} | 新颖度 {novelty_pct}%")

        lines.append("")

    # 备选匹配显示
    backup_matches = result.get("backup_matches", [])
    if backup_matches:
        lines.append("■ 相关备选方向")
        for m in backup_matches[:3]:
            sim = int(m.get("similarity", 0) * 100)
            lines.append(f"  📌 {m.get('title', '')}（相似度 {sim}%）")
        lines.append("")

    # 认知大纲（CCOS v2.0 / 旧版兼容）
    ccos = result.get("ccos_outline")
    if ccos:
        lines.append("■ 认知大纲（CCOS v2.0）")

        # 双平台 CCOS 格式
        if isinstance(ccos, dict) and "wechat_cognitive_outline" in ccos:
            for platform, label in [("wechat_cognitive_outline", "📝 公众号"), ("xiaohongshu_cognitive_outline", "📕 小红书")]:
                outline = ccos.get(platform, {})
                if outline:
                    lines.append(f"  {label}:")
                    lines.append(f"    内容目标: {outline.get('内容目标', '')}")
                    lines.append(f"    主结构: {outline.get('主结构', '')}")
                    lines.append(f"    推进方式: {outline.get('推进方式', '')}")
                    modules = outline.get("认知模块流", [])
                    if modules:
                        module_names = " → ".join([m.get("模块", "") for m in modules[:5]])
                        lines.append(f"    模块流: {module_names}")
                        for m in modules[:6]:
                            mod_name = m.get("模块", "")
                            func = m.get("功能", "")
                            words = m.get("篇幅", "") or m.get("estimated_words", "")
                            if func or words:
                                lines.append(f"      {mod_name}: {func}（{words}）")
                    lines.append(f"    最终大纲: {outline.get('最终动态认知大纲', '')}")
                    lines.append("")
        # 单平台 CCOS 格式
        elif isinstance(ccos, dict) and "内容目标" in ccos:
            lines.append(f"    内容目标: {ccos.get('内容目标', '')}")
            lines.append(f"    主结构: {ccos.get('主结构', '')}")
            lines.append(f"    推进方式: {ccos.get('推进方式', '')}")
            modules = ccos.get("认知模块流", [])
            if modules:
                module_names = " → ".join([m.get("模块", "") for m in modules[:5]])
                lines.append(f"    模块流: {module_names}")
                for m in modules[:6]:
                    mod_name = m.get("模块", "")
                    func = m.get("功能", "")
                    words = m.get("篇幅", "") or m.get("estimated_words", "")
                    if func or words:
                        lines.append(f"      {mod_name}: {func}（{words}）")
            lines.append(f"    最终大纲: {ccos.get('最终动态认知大纲', '')}")
            lines.append("")
        lines.append("")

    # 素材缺口摘要
    material_gaps = result.get("material_gaps", {})
    if material_gaps:
        gap_count = sum(1 for g in material_gaps.values() if isinstance(g, dict) and g.get("has_gap"))
        if gap_count > 0:
            lines.append(f"■ 素材就绪度: {gap_count}个模块有缺口")
            for mod_type, gap_info in material_gaps.items():
                if isinstance(gap_info, dict) and gap_info.get("has_gap"):
                    lines.append(f"  ⚠ {mod_type}: {gap_info.get('gap_description', '缺素材')[:60]}")
                    search_results = gap_info.get("search_results", [])
                    if search_results:
                        for sr in search_results[:2]:
                            lines.append(f"     🔍 {sr.get('title', '')[:40]} — {sr.get('source', '')}")
                elif isinstance(gap_info, dict):
                    lines.append(f"  ✓ {mod_type}: 已召回{gap_info.get('recalled_count', 0)}条")
            lines.append("")

    # 旧版双端大纲（向后兼容）
    outlines = result.get("outlines")
    if outlines and not ccos:
        lines.append("■ 双端大纲（旧版）")

        wechat = outlines.get("wechat_outline")
        if wechat:
            hook = wechat.get("hook", "")
            sections = wechat.get("sections", [])
            section_titles = " → ".join([s.get("title", "") for s in sections[:3]])
            lines.append(f"  📝 公众号: {hook}")
            lines.append(f"     结构: 引子 → {section_titles} → 升华")

        xiaohongshu = outlines.get("xiaohongshu_outline")
        if xiaohongshu:
            hook = xiaohongshu.get("hook", "")
            tags = xiaohongshu.get("tags", [])[:5]
            lines.append(f"  📕 小红书: {hook}")
            lines.append(f"     标签: {', '.join(tags)}")
        lines.append("")

    # 逻辑审计摘要
    logic_audit = result.get("logic_audit", [])
    if logic_audit:
        lines.append("■ 逻辑审计")
        fallacy_count = sum(1 for a in logic_audit if a.get("has_fallacy"))
        if fallacy_count > 0:
            lines.append(f"  ⚠ 发现 {fallacy_count} 个标题存在逻辑问题:")
            for audit in logic_audit[:3]:
                if audit.get("has_fallacy"):
                    ft = audit.get("fallacy_type", "未知")
                    sev = int(audit.get("severity", 0) * 100)
                    title = audit.get("title", "")[:25]
                    lines.append(f"     - {title}... → {ft}({sev}%)")
        else:
            lines.append("  ✓ 所有标题逻辑通过")
        lines.append("")

    # 认知旅程
    cj = result.get("cognitive_journey", {})
    if cj and cj.get("status") != "first_time":
        dist = cj.get("avg_distance", 0)
        status = cj.get("cognitive_progress", "未知")
        warning = cj.get("warning", "")

        lines.append("■ 认知旅程")
        status_icon = "✓" if status == "正常" else "⚠"
        lines.append(f"  {status_icon} 与历史选题距离: {dist:.2f}（{status}）")
        if warning:
            lines.append(f"  警告: {warning}")
        lines.append("")

    # 刺客反转（如果有）
    reversals = result.get("reversals", [])
    if reversals:
        lines.append("■ 刺客反转（历史爆款）")
        for r in reversals[:2]:
            original = r.get("original_thesis", "")[:30]
            reversal = r.get("reversal_thesis", "")[:30]
            strategy = r.get("reversal_strategy", "")
            lines.append(f"  原题: {original}...")
            lines.append(f"  反转: {reversal}...")
            lines.append(f"  策略: {strategy}")
        lines.append("")

    # 数字分身推荐（Phase 8）
    twin_selected = result.get("twin_selected", [])
    twin_learn = result.get("twin_learn", {})
    if twin_selected:
        lines.append("■ 数字分身推荐")
        # 显示学习到的思维特征
        if twin_learn:
            pattern = twin_learn.get("thinking_pattern", "")
            confidence = twin_learn.get("confidence", 0)
            if pattern:
                lines.append(f"  学习到的思维特征: {pattern}")
                lines.append(f"  学习置信度: {int(confidence * 100)}%")
        for t in twin_selected[:3]:
            topic = t.get("topic", "")[:40]
            reason = t.get("selection_reason", "")[:30]
            lines.append(f"  ✓ {topic}")
            lines.append(f"    原因: {reason}...")
        lines.append("")

    # 数据持久化状态
    storage_status = result.get("storage", {}).get("status")
    if storage_status == "ok":
        lines.append("✓ 选题已保存到历史记录")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    return "\n".join(lines)


# ============ CLI 入口 ============

def _safe_print(obj):
    """修复 Windows GBK 编码问题"""
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


def _health_check_warn(command_name: str) -> None:
    """
    单命令健康检查：建议通过 run 走完整流程
    - 默认打印到 stderr
    - 检查 argv 中是否有 --suppress-warning 标志
    """
    if "--suppress-warning" in sys.argv:
        return
    print(
        f"[提示] '{command_name}' 是单阶段命令，建议通过 'python prism_os.py run \"<命题>\"' 走完整流程（Phase 0-7）",
        file=sys.stderr,
    )


def main():
    if len(sys.argv) < 2:
        _safe_print({
            "error": "用法: python prism_os.py <命令> [选项]",
            "commands": {
                "run": "python prism_os.py run \"<用户输入>\" [--format] [--no-ext] - 完整流程（无法跳过 Phase 1）",
                "classify": "Phase 0: 意图识别",
                "gateway": "Phase 1: 苏格拉底网关（熵值计算）",
                "prism": "Phase 2: 棱镜引擎（生成正交标题候选）",
                "anchor": "Phase 3: 现实校验锚（验证候选标题）",
                "twin": "Phase 3.5: 数字分身筛选",
                "gap": "Phase 4.6: 素材就绪度分析",
                "logic": "Phase 5: 逻辑压力测试 + 认知旅程",
                "save": "Phase 6: 数据持久化",
                "assassin": "Phase 7: 刺客机制（历史爆款逻辑反转）",
                "run --from-queue": "从队列选择裂缝（多选）进入主流程",
                "run --match-queue": "输入时匹配队列中的相关裂缝",
                "queue": "队列管理：--list/--tag/--dismiss/--stats",
                "confirm": "python prism_os.py confirm \"<标题>\" - 确认选题并写入飞书",
                "generate": "python prism_os.py generate \"<命题>\" [--platform wechat|xiaohongshu] [--interactive] - Phase 5 内容生成",
                "ccos": "CCOS v2.0 认知推进流大纲生成"
            },
            "options": {
                "--format, -f": "格式化输出（可读报告）",
                "--no-ext": "跳过 Phase 4-8（仅 Phase 0-3）",
                "--no-interactive": "跳过 Phase 3.5 → Phase 4.5 用户选标题决策点（默认选第一个）",
                "--skip-gateway": "跳过 Phase 1 苏格拉底网关（调试用）",
                "--clarification <text>": "提供网关追问的澄清答案（避免 need_clarification 阻塞）",
                "--no-ccos-review": "跳过 Phase 4.5 CCOS 大纲人工审核（默认开启审核）",
                "--from-queue": "从 crack_queue 选择裂缝进入主流程",
                "--match-queue": "输入时匹配 crack_queue 中的相关裂缝"
            }
        })
        sys.exit(1)

    command = sys.argv[1]

    # 短触发：未知命令 → 当作 run 处理（天然语言一句话直接跑）
    known_commands = {"run", "classify", "gateway", "prism", "anchor", "twin", "gap", "logic", "save", "assassin", "confirm", "ccos", "generate", "narrate", "queue", "archive", "metrics"}
    if command not in known_commands:
        # 第一个参数不是命令 → 当作 user_input 走完整流程
        user_input = command
        # 剩余参数合并
        for arg in sys.argv[2:]:
            user_input += " " + arg
        result = run_prism_os(user_input, include_phase_4_8=True)
        output = format_prism_os_output(result)
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.exit(0)

    if command == "run":
        user_input = ""
        include_ext = True
        use_format = False
        from_queue = False
        match_queue = False
        run_interactive = True
        run_skip_gateway = False
        run_clarification = None
        run_ccos_review = True
        run_platform = "both"
        run_interactive_only = False
        run_panic = False
        run_dry_run = False

        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--format" or arg == "-f":
                use_format = True
                i += 1
            elif arg == "--no-ext":
                include_ext = False
                i += 1
            elif arg == "--no-interactive":
                run_interactive = False
                i += 1
            elif arg == "--interactive-only":
                run_interactive_only = True
                i += 1
            elif arg == "--panic":
                run_panic = True
                i += 1
            elif arg == "--dry-run":
                run_dry_run = True
                i += 1
            elif arg == "--skip-gateway":
                run_skip_gateway = True
                i += 1
            elif arg == "--no-ccos-review":
                run_ccos_review = False
                i += 1
            elif arg == "--from-queue":
                from_queue = True
                i += 1
            elif arg == "--match-queue":
                match_queue = True
                i += 1
            elif arg == "--clarification" and i + 1 < len(sys.argv):
                run_clarification = sys.argv[i + 1]
                i += 2
            elif arg == "--platform" and i + 1 < len(sys.argv):
                run_platform = sys.argv[i + 1]
                i += 2
            elif not user_input and not arg.startswith("--"):
                user_input = arg
                i += 1
            else:
                i += 1

        # --interactive-only: stdin 不可用时直接退出
        if run_interactive_only and not sys.stdin.isatty():
            print("[ERROR] --interactive-only 已设置但 stdin 不可用，退出。", file=sys.stderr)
            sys.exit(2)

        if from_queue:
            # 从队列选择
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from crack_queue import CrackQueue
            q = CrackQueue()
            entries = q.list_active()

            if not entries:
                _safe_print({"error": "队列为空，没有待消费的裂缝"})
                sys.exit(1)

            # 显示队列供选择
            print(f"\n=== 队列选择（{len(entries)} 条待消费）===\n")
            for i, e in enumerate(entries[:20], 1):
                signals = e.get("signals", {})
                emotions = signals.get("emotion", [])
                crack_type = e.get("crack_type", "")
                confidence = e.get("confidence", 0)
                priority = e.get("priority_score", 0)

                print(f"[{i}] {e.get('title', '')[:50]}")
                print(f"    类型: {crack_type} | 置信: {confidence:.0%} | 优先级: {priority:.2f}")
                if emotions:
                    print(f"    情绪: {'/'.join(emotions)}")
                if signals.get("trend"):
                    print(f"    趋势: {signals['trend'][:40]}...")
                if e.get("expression_angles"):
                    angles = e["expression_angles"]
                    print(f"    表达入口: {angles[0].get('type','')}→{angles[0].get('angle','')[:30]}...")
                print()

            print("请输入数字选择（多选用空格分隔，如 1 3 5）：")
            try:
                choice = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n取消")
                sys.exit(0)

            if not choice:
                print("取消")
                sys.exit(0)

            # 解析选择
            try:
                indices = [int(x) - 1 for x in choice.split()]
            except ValueError:
                _safe_print({"error": "无效的选择，请输入数字"})
                sys.exit(1)

            # 合并选中的裂缝 consensus/reality 作为 user_input
            selected = []
            for idx in indices:
                if 0 <= idx < len(entries):
                    selected.append(entries[idx])

            if not selected:
                _safe_print({"error": "没有选中任何条目"})
                sys.exit(1)

            # 构建合并输入
            consensus_parts = []
            reality_parts = []
            signals_parts = []
            for e in selected:
                c = e.get("consensus", "")
                r = e.get("reality", "")
                if c and c != "无":
                    consensus_parts.append(c)
                if r and r != "无":
                    reality_parts.append(r)
                sig = e.get("signals", {})
                if sig:
                    trend = sig.get("trend", "")
                    if trend:
                        signals_parts.append(trend)

            # 合并为一个输入
            parts = []
            if consensus_parts:
                parts.append(f"共识：{'；'.join(consensus_parts)}")
            if reality_parts:
                parts.append(f"现实：{'；'.join(reality_parts)}")
            if signals_parts:
                parts.append(f"趋势：{'；'.join(signals_parts)}")

            user_input = "选题方向：" + " | ".join(parts)

            # 标记选中条目为 consumed
            for e in selected:
                q.mark_consumed(e.get("id", ""), "run_from_queue")

            print(f"\n已选择 {len(selected)} 条裂缝，合并输入：")
            print(f"  {user_input[:100]}...\n")

        if match_queue and user_input:
            # 匹配队列并展示相关裂缝
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from crack_queue import CrackQueue
            q = CrackQueue()
            results = q.search(user_input)

            if results:
                print(f"\n=== 队列匹配（找到 {len(results)} 条相关裂缝）===\n")
                for i, e in enumerate(results[:5], 1):
                    signals = e.get("signals", {})
                    crack_type = e.get("crack_type", "")
                    confidence = e.get("confidence", 0)
                    creator_match = e.get("creator_match", {})
                    match_score = creator_match.get("match_score", 0)

                    marker = " ← AI推荐" if i == 1 and match_score > 0.7 else ""
                    print(f"[{i}] {e.get('title', '')[:50]}{marker}")
                    print(f"    类型: {crack_type} | 置信: {confidence:.0%}")
                    if signals.get("trend"):
                        print(f"    趋势: {signals['trend'][:50]}...")
                    print()
            else:
                print(f"\n队列中未找到与 '{user_input}' 相关的裂缝\n")

        if not user_input and not from_queue:
            _safe_print({"error": "请提供用户输入"})
            sys.exit(1)

        # 加载历史选题供刺客机制使用
        try:
            from storage import load_log
            history_logs = load_log(20)
            history_topics = [log.get("thesis", "") for log in history_logs if log.get("thesis")]
        except Exception:
            history_topics = []

        result = run_prism_os(
            user_input,
            include_phase_4_8=include_ext,
            history_topics=history_topics,
            interactive=(run_interactive and not from_queue),
            skip_gateway=run_skip_gateway,
            user_clarification=run_clarification,
            ccos_review=run_ccos_review,
            platform=run_platform,
            panic_on_error=run_panic,
            dry_run=run_dry_run,
        )

        # GAP-2: run 成功后自动接力 narrate
        if result.get("status") == "success" and result.get("ccos_outline"):
            try:
                narrate_result = _run_narrate(user_input, run_platform)
                result["narrate"] = narrate_result
            except Exception as e:
                print(f"[WARNING] narrate 接力失败（run 状态保留）: {e}", file=sys.stderr)
                result["narrate"] = {"status": "failed", "error": str(e)}

        if use_format:
            output = format_prism_os_output(result)
            sys.stdout.buffer.write(output.encode("utf-8"))
        else:
            _safe_print(result)

    elif command == "classify":
        if len(sys.argv) < 3:
            _safe_print({"error": "请提供用户输入"})
            sys.exit(1)
        user_input = sys.argv[2]
        result = classify_intent(user_input)
        _safe_print(result)

    elif command == "gateway":
        if len(sys.argv) < 3:
            _safe_print({"error": "请提供用户输入"})
            sys.exit(1)
        user_input = sys.argv[2]
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from socratic_gateway import socratic_gateway
        result = socratic_gateway(user_input)

        # need_clarification 时停在 stdin 等用户回答追问
        if result.get("status") == "need_clarification":
            questions = result.get("questions", [])
            directions = result.get("directions", [])

            print("\n━━━ 选题追问 ━━━", file=sys.stderr)
            for i, q in enumerate(questions, 1):
                # questions 是 List[str]
                if isinstance(q, str):
                    print(f"  {i}. {q}", file=sys.stderr)
                else:
                    print(f"  {i}. {q.get('内容', str(q))}", file=sys.stderr)
                    if q.get("可选方向"):
                        print(f"     快捷: {'/'.join(q.get('可选方向', []))}", file=sys.stderr)
            print("━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
            print("请回答上述问题（直接输入 / 选项编号+内容 / skip跳过）：", file=sys.stderr)

            try:
                user_answer = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                user_answer = "skip"

            if user_answer.lower() == "skip":
                print("[跳过] 直接进入后续流程", file=sys.stderr)
            else:
                print(f"[用户回答] {user_answer}", file=sys.stderr)
                result["user_answer"] = user_answer
                result["status"] = "answered"

        _safe_print(result)

    elif command == "confirm":
        if len(sys.argv) < 3:
            _safe_print({"error": "请提供标题"})
            sys.exit(1)
        title = sys.argv[2]
        result = confirm_title(title)
        _safe_print(result)

    elif command == "ccos":
        _health_check_warn("ccos")
        # CCOS v2.0 交互式大纲生成
        # 用法: python prism_os.py ccos "<命题>" [--platform wechat|xiaohongshu|both] [--skip-alignment]
        topic = ""
        platform = "both"
        skip_alignment = False

        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--platform" and i + 1 < len(sys.argv):
                platform = sys.argv[i + 1]
                i += 2
            elif arg in ("--skip-alignment", "-s"):
                skip_alignment = True
                i += 1
            elif not topic and not arg.startswith("--"):
                topic = arg
                i += 1
            else:
                i += 1

        if not topic:
            _safe_print({"error": "请提供命题: python prism_os.py ccos \"<命题>\" [--platform wechat]"})
            sys.exit(1)

        from cognitive_outline import (
            generate_alignment_questions,
            cognitive_outline_workflow,
            generate_dual_platform_outline
        )

        # Layer 0: 认知对齐
        questions = generate_alignment_questions(topic, platform)

        if skip_alignment:
            alignment_result = {"parsed": {}, "status": "skipped"}
        else:
            # 打印七类追问，等待用户输入
            print("\n━━━ Layer 0 认知对齐 ━━━", file=sys.stderr)
            for idx, q in enumerate(questions, 1):
                opts = ", ".join(q["可选方向"]) if q["可选方向"] else ""
                print(f"  {idx}. {q['内容']}", file=sys.stderr)
                if opts:
                    print(f"     快捷方向: {opts}", file=sys.stderr)
            print("━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
            print("请回答上述问题（直接输入 / 选项编号+内容 / skip跳过）:", file=sys.stderr)

            # 读取用户输入（从 stdin）
            try:
                user_input = input().strip()
            except EOFError:
                user_input = "skip"

            from cognitive_outline import parse_user_alignment_response, cognitive_alignment_layer0
            alignment_result = cognitive_alignment_layer0(topic, platform, user_input)

        # 根据平台选择生成大纲
        if platform == "both":
            ccos_result = generate_dual_platform_outline(topic, "reversal")
        else:
            ccos_result = cognitive_outline_workflow(topic, "reversal", platform, alignment_result)

        _safe_print({"topic": topic, "platform": platform, "alignment": alignment_result, "ccos_outline": ccos_result})

    elif command == "generate":
        # Phase 5: 内容生成
        # 用法: python prism_os.py generate "<标题>" [--platform wechat|xiaohongshu] [--interactive]
        topic = ""
        platform = "wechat"
        interactive = False

        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--platform" and i + 1 < len(sys.argv):
                platform = sys.argv[i + 1]
                i += 2
            elif arg == "--interactive":
                interactive = True
                i += 1
            elif not topic and not arg.startswith("--"):
                topic = arg
                i += 1
            else:
                i += 1

        if not topic:
            _safe_print({"error": "请提供命题: python prism_os.py generate \"<命题>\" [--platform wechat] [--interactive]"})
            sys.exit(1)

        from content_generator import (
            content_generation_workflow,
            interactive_content_generation_workflow,
            _load_ccos_for_topic
        )

        ccos_outline = _load_ccos_for_topic(topic, platform)
        if not ccos_outline:
            _safe_print({
                "error": f"未找到命题 '{topic}' 的 CCOS 大纲，请先运行: python prism_os.py ccos \"{topic}\"",
                "topic": topic,
                "platform": platform
            })
            sys.exit(1)

        if interactive:
            result = interactive_content_generation_workflow(topic, ccos_outline, platform)
            _safe_print({"status": result["status"], "topic": topic, "platform": platform})
        else:
            result = content_generation_workflow(topic, ccos_outline, platform)
            _safe_print(result)

    elif command == "narrate":
        _health_check_warn("narrate")
        # Phase 5: 叙事驱动内容生成（新方案，主命令）
        # 用法: python prism_os.py narrate "<命题>" [--platform wechat|xiaohongshu] [--interactive] [--search] [--skip-experience] [--quality-check]
        topic = ""
        platform = "wechat"
        interactive = False
        auto_scrape = False
        skip_experience = False
        quality_check_flag = False

        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--platform" and i + 1 < len(sys.argv):
                platform = sys.argv[i + 1]
                i += 2
            elif arg == "--interactive":
                interactive = True
                i += 1
            elif arg == "--search":
                auto_scrape = True
                i += 1
            elif arg == "--skip-experience":
                skip_experience = True
                i += 1
            elif arg == "--quality-check":
                quality_check_flag = True
                i += 1
            elif not topic and not arg.startswith("--"):
                topic = arg
                i += 1
            else:
                i += 1

        if not topic:
            _safe_print({"error": '请提供命题: python prism_os.py narrate "<命题>" [--platform wechat] [--interactive] [--skip-experience] [--quality-check]'})
            sys.exit(1)

        from content_generator import (
            narrative_generation_workflow,
            interactive_narrative_workflow,
            _load_ccos_for_topic,
            prompt_real_experience,
            quality_check,
        )

        ccos_outline = _load_ccos_for_topic(topic, platform)
        if not ccos_outline:
            _safe_print({
                "error": f'未找到命题 "{topic}" 的 CCOS 大纲，请先运行: python prism_os.py ccos "{topic}"',
                "topic": topic,
                "platform": platform
            })
            sys.exit(1)

        # 真实经历询问
        if not skip_experience and not interactive:
            experience_prompt = prompt_real_experience(topic, ccos_outline, platform)
            print(f"\n[真实经历] {experience_prompt.get('prompt', '')}", file=sys.stderr)
            if experience_prompt.get("question_areas"):
                for area in experience_prompt["question_areas"]:
                    print(f"  - {area}", file=sys.stderr)

        if interactive:
            # 加载 calibration（Phase 6.1）
            from template_scorer import load_calibration
            calibration = load_calibration()
            result = interactive_narrative_workflow(topic, ccos_outline, platform, calibration=calibration)
            _safe_print({"status": result["status"], "topic": topic, "platform": platform})
        else:
            result = _run_narrate(topic, platform)

            # 质量自检
            qc_result = None
            if quality_check_flag and result.get("full_draft"):
                qc_result = quality_check(result["full_draft"], platform)
                print(f"\n[质量自检] 评分: {qc_result.get('score', 0)}/100", file=sys.stderr)
                if qc_result.get("issues"):
                    for issue in qc_result["issues"][:5]:
                        print(f"  [{issue.get('level', '')}] {issue.get('type', '')}: {issue.get('suggestion', '')}", file=sys.stderr)

            # 输出摘要
            output = {
                "status": result["status"],
                "topic": result.get("topic", topic),
                "platform": result.get("platform", platform),
                "strategy": result.get("strategy", {}).get("strategy", ""),
                "word_count": result.get("word_count", 0),
                "materials_used": len(result.get("materials_used", [])),
                "draft_preview": result.get("full_draft", "")[:200] + "..." if len(result.get("full_draft", "")) > 200 else result.get("full_draft", ""),
            }
            if qc_result:
                output["quality_check"] = {
                    "score": qc_result.get("score", 0),
                    "issue_count": len(qc_result.get("issues", [])),
                }
            _safe_print(output)

    elif command == "prism":
        _health_check_warn("prism")
        # Phase 2: 棱镜引擎 - 生成正交标题候选 + 交互式选择
        # 用法: python prism_os.py prism "<thesis>" [--identity <role>] [--audience <target>]
        thesis = ""
        identity_role = ""
        audience = ""
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--identity" and i + 1 < len(sys.argv):
                identity_role = sys.argv[i + 1]
                i += 2
            elif arg == "--audience" and i + 1 < len(sys.argv):
                audience = sys.argv[i + 1]
                i += 2
            elif not thesis and not arg.startswith("--"):
                thesis = arg
                i += 1
            else:
                i += 1

        if not thesis:
            _safe_print({"error": "请提供命题: python prism_os.py prism \"<thesis>\""})
            sys.exit(1)

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from prism_engine import prism_engine
        from storage import append_selected_title

        result = prism_engine(thesis, identity_role, audience)
        candidates = result.get("candidates", [])

        if not candidates:
            _safe_print(result)
            sys.exit(0)

        # 显示候选标题列表供选择
        print("\n【候选标题列表】", file=sys.stderr)
        dim_names = {
            "reversal": "逆向拆解",
            "micro_scene": "微观切片",
            "systemic_flaw": "系统归因",
            "bridge": "认知脚手架"
        }
        archetype_names = {
            "opinion_assertion": "观点断言",
            "identity_label": "身份标签",
            "scene_suspense": "场景悬念",
            "data_counter_ask": "数据反问",
            "story_hook": "故事钩子"
        }
        for i, c in enumerate(candidates, 1):
            dim = c.get("dimension", "")
            arch = c.get("archetype", "")
            dim_name = dim_names.get(dim, dim)
            arch_name = archetype_names.get(arch, arch)
            print(f"  {i}. [{dim_name}] {c.get('title', '')}", file=sys.stderr)
        print("", file=sys.stderr)

        # 交互式选择
        while True:
            print("请输入数字选择标题（1-{}），或 q 退出：".format(len(candidates)), file=sys.stderr)
            try:
                choice = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n取消选择", file=sys.stderr)
                sys.exit(0)

            if choice.lower() == "q":
                print("退出", file=sys.stderr)
                sys.exit(0)

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    selected = candidates[idx]
                    selected_title = selected.get("title", "")
                    # 写入 topic_log
                    append_selected_title(
                        title=selected_title,
                        platform="wechat",
                        source="prism",
                        metadata={
                            "dimension": selected.get("dimension", ""),
                            "archetype": selected.get("archetype", ""),
                            "thesis": thesis
                        }
                    )
                    _safe_print({
                        "status": "selected",
                        "selected_title": selected_title,
                        "dimension": selected.get("dimension", ""),
                        "archetype": selected.get("archetype", ""),
                        "thesis": thesis
                    })
                    break
                else:
                    print(f"无效选择，请输入 1-{len(candidates)} 之间的数字", file=sys.stderr)
            except ValueError:
                print("请输入数字或 q", file=sys.stderr)

    elif command == "anchor":
        # Phase 3: 现实校验锚 - 验证候选标题
        # 用法: python prism_os.py anchor [--input candidates.json]
        input_file = None
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--input" and i + 1 < len(sys.argv):
                input_file = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        candidates = None
        if input_file:
            with open(input_file, "r", encoding="utf-8") as f:
                candidates = json.load(f)
        else:
            try:
                candidates = json.loads(sys.stdin.read())
            except json.JSONDecodeError:
                _safe_print({"error": "请通过 --input 或 stdin 提供候选标题数据"})
                sys.exit(1)

        if not candidates:
            _safe_print({"error": "候选标题数据为空"})
            sys.exit(1)

        # 兼容：如果传入的是 dict 且有 candidates 字段，自动提取
        if isinstance(candidates, dict) and "candidates" in candidates:
            candidates = candidates["candidates"]

        if not isinstance(candidates, list) or len(candidates) == 0:
            _safe_print({"error": "候选标题数据必须是包含 candidates 的非空数组", "received_type": type(candidates).__name__})
            sys.exit(1)

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from reality_anchor import reality_anchor
        result = reality_anchor(candidates)
        _safe_print(result)

    elif command == "twin":
        # Phase 3.5: 数字分身筛选
        # 用法: python prism_os.py twin --input candidates.json
        input_file = None
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--input" and i + 1 < len(sys.argv):
                input_file = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        candidates = None
        if input_file:
            with open(input_file, "r", encoding="utf-8") as f:
                candidates = json.load(f)
        else:
            try:
                candidates = json.loads(sys.stdin.read())
            except json.JSONDecodeError:
                _safe_print({"error": "请通过 --input 或 stdin 提供候选标题数据"})
                sys.exit(1)

        if not candidates:
            _safe_print({"error": "候选标题数据为空"})
            sys.exit(1)

        if isinstance(candidates, dict) and "candidates" in candidates:
            candidates = candidates["candidates"]

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from storage import load_config
        from cognitive_crack import digital_twin_filter

        config = load_config()
        twin_config = config.get("digital_twin", {})
        thinking_pattern = twin_config.get("thinking_pattern", "理性、克制、反常识")

        result = digital_twin_filter(candidates, thinking_pattern)
        _safe_print(result)

    elif command == "gap":
        _health_check_warn("gap")
        # Phase 4.6: Gap Analysis - 素材就绪度分析
        # 用法: python prism_os.py gap "<thesis>" [--materials <materials>] [--no-block]
        thesis = ""
        materials = ""
        no_block = False
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--materials" and i + 1 < len(sys.argv):
                materials = sys.argv[i + 1]
                i += 2
            elif arg == "--no-block":
                no_block = True
                i += 1
            elif not thesis and not arg.startswith("--"):
                thesis = arg
                i += 1
            else:
                i += 1

        if not thesis:
            _safe_print({"error": "请提供命题: python prism_os.py gap \"<thesis>\""})
            sys.exit(1)

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from gap_analysis import analyze_gap
        result = analyze_gap(thesis, materials)

        # --no-block 模式：直接返回 JSON
        if no_block:
            _safe_print(result)
            sys.exit(0)

        # 阻塞模式：展示缺口，等待用户选择
        decision = _run_gap_decision_loop(thesis, result)
        _safe_print({"status": decision, "thesis": thesis, "gap_result": result})

    elif command == "logic":
        # Phase 5: 逻辑压力测试 + 认知旅程
        # 用法: python prism_os.py logic --input candidates.json [--history "topic1" "topic2"]
        input_file = None
        history_topics = []
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--input" and i + 1 < len(sys.argv):
                input_file = sys.argv[i + 1]
                i += 2
            elif arg == "--history":
                i += 1
                while i < len(sys.argv) and not sys.argv[i].startswith("--"):
                    history_topics.append(sys.argv[i])
                    i += 1
            else:
                i += 1

        candidates = None
        if input_file:
            with open(input_file, "r", encoding="utf-8") as f:
                candidates = json.load(f)
        else:
            try:
                candidates = json.loads(sys.stdin.read())
            except json.JSONDecodeError:
                _safe_print({"error": "请通过 --input 或 stdin 提供候选标题数据"})
                sys.exit(1)

        if not candidates:
            _safe_print({"error": "候选标题数据为空"})
            sys.exit(1)

        if isinstance(candidates, dict) and "candidates" in candidates:
            candidates = candidates["candidates"]

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from logic_pressure import logic_pressure
        result = logic_pressure(candidates, history_topics if history_topics else None)
        _safe_print(result)

    elif command == "save":
        # Phase 6: 数据持久化 - 写入 topic_log.yaml
        # 用法: python prism_os.py save --thesis "<thesis>" [--status success|no_candidates]
        thesis = ""
        status = "success"
        candidates_count = 0
        entropy_score = 0
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--thesis" and i + 1 < len(sys.argv):
                thesis = sys.argv[i + 1]
                i += 2
            elif arg == "--status" and i + 1 < len(sys.argv):
                status = sys.argv[i + 1]
                i += 2
            elif arg == "--count" and i + 1 < len(sys.argv):
                try:
                    candidates_count = int(sys.argv[i + 1])
                except ValueError:
                    pass
                i += 2
            elif arg == "--entropy" and i + 1 < len(sys.argv):
                try:
                    entropy_score = float(sys.argv[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        if not thesis:
            _safe_print({"error": "请提供命题: python prism_os.py save --thesis \"<thesis>\""})
            sys.exit(1)

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from storage import append_log

        log_entry = {
            "thesis": thesis,
            "candidates_count": candidates_count,
            "entropy_score": entropy_score,
        }
        storage_result = append_log(log_entry)
        _safe_print({"status": "ok" if storage_result.get("status") == "ok" else "failed", "thesis": thesis})

    elif command == "assassin":
        # Phase 7: 刺客机制 - 历史爆款逻辑反转
        # 用法: python prism_os.py assassin [--history "topic1" "topic2"]
        history_topics = []
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--history":
                i += 1
                while i < len(sys.argv) and not sys.argv[i].startswith("--"):
                    history_topics.append(sys.argv[i])
                    i += 1
            else:
                i += 1

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from assassin import assassin_mechanism
        result = assassin_mechanism(
            historical_topics=history_topics if history_topics else None,
            entities=None,
            relations=None
        )
        _safe_print(result)

    elif command == "queue":
        # 队列管理命令
        # 用法: python prism_os.py queue [--list] [--tag <id> <label>] [--dismiss <id>]
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from crack_queue import CrackQueue

        q = CrackQueue()
        args = sys.argv[2:]

        if not args or "--list" in args or "-l" in args:
            # 列出所有 new/reviewed 条目
            status_filter = None
            if "--status" in args:
                idx = args.index("--status")
                if idx + 1 < len(args):
                    status_filter = args[idx + 1]
            entries = q.list_all(status_filter) if status_filter else q.list_active()
            if not entries:
                _safe_print({"status": "empty", "message": "队列为空"})
            else:
                _safe_print({"status": "ok", "total": len(entries), "entries": entries[:20]})

        elif "--tag" in args or "-t" in args:
            idx = args.index("--tag") if "--tag" in args else args.index("-t")
            if idx + 2 <= len(args):
                entry_id, label = args[idx + 1], args[idx + 2]
                if q.tag(entry_id, label):
                    _safe_print({"status": "ok", "action": "tagged", "id": entry_id, "label": label})
                else:
                    _safe_print({"status": "error", "message": f"未找到条目: {entry_id}"})

        elif "--dismiss" in args or "-d" in args:
            idx = args.index("--dismiss") if "--dismiss" in args else args.index("-d")
            if idx + 1 < len(args):
                entry_id = args[idx + 1]
                if q.dismiss(entry_id):
                    _safe_print({"status": "ok", "action": "dismissed", "id": entry_id})
                else:
                    _safe_print({"status": "error", "message": f"未找到条目: {entry_id}"})

        elif "--stats" in args:
            active, total = q.count()
            _safe_print({"status": "ok", "active": active, "total": total})

        else:
            _safe_print({
                "usage": "python prism_os.py queue [--list] [--tag <id> <label>] [--dismiss <id>] [--stats]"
            })

    elif command == "archive":
        # 归档查询命令
        # 用法: python prism_os.py archive --search <keyword> [--limit N]
        #        python prism_os.py archive --trends <crack_id>
        from crack_queue import CrackQueue

        q = CrackQueue()
        args = sys.argv[2:]

        if "--search" in args or "-s" in args:
            idx = args.index("--search") if "--search" in args else args.index("-s")
            keyword = args[idx + 1] if idx + 1 < len(args) else ""
            limit = 10
            if "--limit" in args:
                li = args.index("--limit")
                try:
                    limit = int(args[li + 1])
                except (ValueError, IndexError):
                    pass

            if not keyword:
                _safe_print({"error": "请提供搜索关键词: python prism_os.py archive --search <keyword>"})
                sys.exit(1)

            results = q.search_archive(keyword, limit=limit)
            _safe_print({"status": "ok", "keyword": keyword, "count": len(results), "results": results})

        elif "--trends" in args or "-t" in args:
            idx = args.index("--trends") if "--trends" in args else args.index("-t")
            crack_id = args[idx + 1] if idx + 1 < len(args) else ""
            limit = 5
            if "--limit" in args:
                li = args.index("--limit")
                try:
                    limit = int(args[li + 1])
                except (ValueError, IndexError):
                    pass

            # 通过 ID 找到 crack 条目
            entry = None
            if crack_id:
                all_entries = q.list_all()
                for e in all_entries:
                    if e.get("id") == crack_id:
                        entry = e
                        break

            if not entry:
                _safe_print({"error": f"未找到 ID 为 {crack_id} 的归档条目"})
                sys.exit(1)

            results = q.query_trends(entry, limit=limit)
            _safe_print({"status": "ok", "crack_id": crack_id, "count": len(results), "results": results})

        elif "--list" in args or "-l" in args:
            # 列出最近归档条目
            archive = q._load_archive() if hasattr(q, "_load_archive") else []
            _safe_print({"status": "ok", "total": len(archive), "entries": archive[:20]})

        else:
            _safe_print({
                "usage": "python prism_os.py archive --search <keyword> [--limit N]\n"
                        "       python prism_os.py archive --trends <crack_id> [--limit N]\n"
                        "       python prism_os.py archive --list"
            })

    elif command == "metrics":
        # Phase 6.0: 数据反馈闭环 — 飞书多维表格同步与反哺
        _health_check_warn("metrics")
        args = sys.argv[2:]

        if not args or args[0] == "--help":
            _safe_print({
                "usage": "python prism_os.py metrics sync          # 从飞书同步数据到本地\n"
                        "       python prism_os.py metrics status        # 查看当前反哺状态\n"
                        "       python prism_os.py metrics list          # 列出本地 snapshot\n"
                        "       python prism_os.py metrics score         # 运行模板优选"
            })
            sys.exit(0)

        subcmd = args[0]

        if subcmd == "sync":
            from feishu_bitable import FeishuBitable
            from metrics_sync import MetricsSync

            try:
                fb = FeishuBitable.from_config()
                syncer = MetricsSync(feishu_client=fb)
                result = syncer.sync()
                _safe_print(result)
            except Exception as e:
                _safe_print({"status": "error", "error": str(e)})

        elif subcmd == "status":
            from template_scorer import load_calibration
            from metrics_sync import MetricsSync

            cal = load_calibration()
            snapshot_path = os.path.join(os.path.dirname(__file__), "..", "data", "metrics_snapshot.yaml")
            snap_exists = os.path.exists(snapshot_path)

            info = {
                "calibration_exists": cal is not None,
                "snapshot_exists": snap_exists,
            }
            if cal:
                info["sample_size"] = cal.get("sample_size", 0)
                info["last_updated"] = cal.get("last_updated", "")
                info["strategies"] = {
                    platform: list(strats.keys())
                    for platform, strats in cal.get("by_platform_strategy", {}).items()
                }
            _safe_print(info)

        elif subcmd == "list":
            from metrics_sync import MetricsSync

            snapshot_path = os.path.join(os.path.dirname(__file__), "..", "data", "metrics_snapshot.yaml")
            if not os.path.exists(snapshot_path):
                _safe_print({"status": "ok", "count": 0, "message": "未找到 snapshot，请先运行 sync"})
            else:
                try:
                    import yaml
                    with open(snapshot_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or []
                except (ImportError, Exception):
                    with open(snapshot_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                _safe_print({"status": "ok", "count": len(data), "articles": data[:20]})

        elif subcmd == "score":
            from template_scorer import run_calibration, save_calibration

            snapshot_path = os.path.join(os.path.dirname(__file__), "..", "data", "metrics_snapshot.yaml")
            if not os.path.exists(snapshot_path):
                _safe_print({"status": "error", "error": "未找到 snapshot，请先运行 sync"})
                sys.exit(1)
            try:
                import yaml
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    articles = yaml.safe_load(f) or []
            except (ImportError, Exception):
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    articles = json.load(f)

            calibration = run_calibration(articles)
            save_calibration(calibration)
            _safe_print({
                "status": "ok",
                "sample_size": calibration["sample_size"],
                "strategies_scored": sum(len(v) for v in calibration.get("by_platform_strategy", {}).values()),
            })

        else:
            _safe_print({"error": f"未知子命令: {subcmd}，请使用 sync/status/list/score"})

    elif command == "listen":
        # HTTP long-running server for cross-machine access
        # python prism_os.py listen [--port 7654] [--token <secret>]
        import argparse
        parser = argparse.ArgumentParser(description="PRISM-OS HTTP Server")
        parser.add_argument("--port", type=int, default=7654, help="监听端口（默认 7654）")
        parser.add_argument("--token", type=str, default=None, help="访问令牌（可选）")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
        listen_args = parser.parse_args(sys.argv[2:])

        port = listen_args.port
        token = listen_args.token
        host = listen_args.host

        print(f"[PRISM-OS HTTP Server] 启动中...")
        print(f"  地址: http://{host}:{port}")
        print(f"  Token: {'已启用（需在 Header 中携带 X-Token）' if token else '未启用（建议生产环境设置 --token）'}")
        print(f"  跨机器可用: http://<本机IP>:{port}")
        print(f"  按 Ctrl+C 停止")
        print()

        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json as _json

        class _PrismHandler(BaseHTTPRequestHandler):
            def _send_json(self, code, data):
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
                self.end_headers()
                self.wfile.write(_json.dumps(data, ensure_ascii=False).encode("utf-8"))

            def do_OPTIONS(self):
                self._send_json(204, {})

            def do_POST(self):
                # Auth check
                if token:
                    provided = self.headers.get("X-Token", "")
                    if provided != token:
                        self._send_json(401, {"error": "Unauthorized", "message": "Token 不匹配"})
                        return

                # Read body
                content_len = int(self.headers.get("Content-Length", 0))
                if content_len == 0:
                    self._send_json(400, {"error": "Bad Request", "message": "请求体为空"})
                    return

                try:
                    body = self.rfile.read(content_len)
                    req = _json.loads(body.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": "Bad JSON", "message": str(e)})
                    return

                topic = req.get("topic", "")
                if not topic:
                    self._send_json(400, {"error": "Bad Request", "message": "缺少 topic 字段"})
                    return

                # Run PRISM-OS
                include_ext = req.get("include_phase_4_8", True)
                platform = req.get("platform", None)  # None = 让 run_prism_os 内部决定

                print(f"[{self.address_string()}] POST /run  topic='{topic[:50]}...'")

                try:
                    result = run_prism_os(
                        topic,
                        include_phase_4_8=include_ext,
                        platform=platform,
                        interactive=False,  # HTTP 无 stdin，不能阻塞
                    )
                    self._send_json(200, {"status": "ok", "result": result})
                    print(f"[{self.address_string()}] 完成")
                except Exception as e:
                    self._send_json(500, {"error": "Internal Error", "message": str(e)})
                    print(f"[{self.address_string()}] 错误: {e}")

            def log_message(self, format, *args):
                # 安静日志（只打印重要请求）
                pass

        server = HTTPServer((host, port), _PrismHandler)
        print(f"[PRISM-OS HTTP Server] 已启动 → http://{host}:{port}/run")
        print()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[PRISM-OS HTTP Server] 已停止")
            server.shutdown()
        sys.exit(0)

    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()