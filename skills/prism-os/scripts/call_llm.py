#!/usr/bin/env python3
"""
PRISM-OS LLM 调用脚本
支持 Kimi → Gateway → OpenRouter 三级 fallback

模型优先级：
- Kimi: 主路径，场景动态选择 8k/32k/128k
- Gateway: 备用（免费模型，当前服务不可用）
- OpenRouter: 最终降级（free 模型，自动从 API 刷新）

模型刷新：
  refresh_openrouter_models() 每 10 分钟缓存一次，
  规则：prompt_price=0 且 ctx>=32k，按 ctx 降序排列。

用法: python call_llm.py '<prompt>'
"""

import sys
import io
import json
import os
import time
import subprocess
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# ============ 强制 UTF-8 输出 ============
# Windows 默认 GBK，LLM 返回中文会撞 UnicodeDecodeError 导致父进程读 stdout 线程崩
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name)
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        setattr(sys, _stream_name, io.TextIOWrapper(_stream.buffer, encoding="utf-8", errors="replace"))

# ============ .env 自动加载（兼容跨机器迁移）============
# 在 key 文件旁边放 .env 文件，自动读取
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# ============ curl subprocess 封装（绕过 Windows Python SSL 问题）============

# 全局节流控制：确保 API 调用间隔至少此秒数
_last_api_call = 0.0
_MIN_APICALL_INTERVAL = 0.8


def _global_throttle():
    """所有 curl API 调用底层的节流，防止 rate limit"""
    global _last_api_call
    now = time.time()
    elapsed = now - _last_api_call
    if elapsed < _MIN_APICALL_INTERVAL:
        time.sleep(_MIN_APICALL_INTERVAL - elapsed)
    _last_api_call = time.time()


def _curl_post(url: str, payload: dict, headers: dict, timeout: int = 30) -> Optional[dict]:
    """用 curl POST 发送请求，绕过 Windows SSL 问题。
    返回响应 JSON dict，失败（包括 HTTP 4xx/5xx）返回 None。"""
    _global_throttle()
    try:
        proc = subprocess.run(
            ["curl", "-s", "-f", "--max-time", str(timeout), "-k", "-X", "POST",
             url,
             "-H", "Content-Type: application/json",
             *sum([["-H", f"{k}: {v}"] for k, v in headers.items()], []),
             "-d", json.dumps(payload)],
            capture_output=True, timeout=timeout + 5
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        # 防御性检查：API 可能返回 {"error": ...} 但 HTTP 200（某些 API 行为）
        if isinstance(data, dict) and "error" in data:
            return None
        return data
    except Exception:
        return None


def _curl_get(url: str, headers: dict, timeout: int = 30) -> Optional[dict]:
    """用 curl GET 发送请求，绕过 Windows SSL 问题。
    返回响应 JSON dict，失败返回 None。"""
    _global_throttle()
    try:
        proc = subprocess.run(
            ["curl", "-s", "-f", "--max-time", str(timeout), "-k", "-X", "GET",
             url,
             *sum([["-H", f"{k}: {v}"] for k, v in headers.items()], [])],
            capture_output=True, timeout=timeout + 5
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        if isinstance(data, dict) and "error" in data:
            return None
        return data
    except Exception:
        return None


# ============ API Keys & Endpoints ============

# Kimi (Moonshot) - 优先付费
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

# NVIDIA NIM — 高速推理，Kimi 失败后首选降级
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# NVIDIA 模型映射（OpenAI 兼容 API）
NVIDIA_MODEL_MAP = {
    "reasoning": "meta/llama-3.1-70b-instruct",
    "quality": "meta/llama-3.1-70b-instruct",
    "writing-cn": "meta/llama-3.1-70b-instruct",
    "writing-en": "meta/llama-3.1-70b-instruct",
    "translation": "meta/llama-3.1-70b-instruct",
    "fast": "meta/llama-3.1-8b-instruct",
    "long-context": "mistralai/mistral-large-2-instruct",
    "summary": "meta/llama-3.1-70b-instruct",
    "extraction": "meta/llama-3.1-70b-instruct",
}
NVIDIA_MAX_TOKENS_MAP = {
    "reasoning": 8192,
    "quality": 16384,
    "writing-cn": 16384,
    "writing-en": 16384,
    "translation": 8192,
    "fast": 4096,
    "long-context": 128000,
    "summary": 8192,
    "extraction": 8192,
}

# OpenRouter 备用付费
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Kimi 模型场景映射（已验证可用）
KIMI_MODEL_MAP = {
    "reasoning": "moonshot-v1-128k",    # 推理思考（kimi-k2.6 不可用）
    "quality": "moonshot-v1-128k",      # 高质量
    "writing-cn": "moonshot-v1-128k",   # 中文写作
    "writing-en": "moonshot-v1-128k",   # 英文写作
    "translation": "moonshot-v1-128k",  # 翻译
    "fast": "moonshot-v1-32k",          # 快速
    "long-context": "moonshot-v1-128k", # 超长文本
    "summary": "moonshot-v1-128k",      # 总结
    "extraction": "moonshot-v1-128k",   # 提炼
    "multimodal": "moonshot-v1-128k-vision-preview",  # 图片理解
}

# Kimi 场景 → max_tokens 映射（按需分配，控制成本）
KIMI_MAX_TOKENS_MAP = {
    "reasoning": 8192,      # 推理思考，短回复
    "quality": 16384,       # 高质量，中等长度
    "writing-cn": 16384,    # 中文写作
    "writing-en": 16384,   # 英文写作
    "translation": 8192,    # 翻译
    "fast": 4096,           # 快速，短回复
    "long-context": 128000, # 超长文本
    "summary": 8192,        # 总结
    "extraction": 8192,     # 提炼
    "multimodal": 8192,     # 图片理解
}

# OpenRouter 备用模型（当 Kimi 失败时）
# 优先级规则：free > cheap > fast，context_length >= 32k
# 动态从 OpenRouter API 获取，可通过 refresh_openrouter_models() 更新

# 默认兜底模型（OpenRouter付费key可用模型，按能力/速度排序）
# 已验证可用：qwen-72b > deepseek-v3 > gemma-26b > mistral-24b > llama-8b > qwen3-8b
OPENROUTER_FALLBACK_MODELS = [
    "qwen/qwen-2.5-72b-instruct",     # 验证可用，大参数，强
    "deepseek/deepseek-chat-v3",       # 验证可用，强
    "google/gemma-4-26b-a4b-it",        # 验证可用
    "mistralai/mistral-small-24b-instruct-2501",  # 验证可用
    "meta-llama/llama-3.1-8b-instruct", # 验证可用
    "qwen/qwen3-8b",                   # 验证可用，快
]

# 缓存的模型列表（通过 refresh_openrouter_models 更新）
_openrouter_cached_models: List[str] = []


def refresh_openrouter_models(force: bool = False) -> List[str]:
    """
    从 OpenRouter API 获取可用模型，缓存 free/low-cost 模型列表。
    规则：prompt_price = 0（免费）且 context_length >= 32k，按 ctx 降序排列。

    Args:
        force: True 则强制刷新，False 则用缓存（缓存10分钟有效）

    Returns:
        可用模型 ID 列表
    """
    global _openrouter_cached_models

    # 10分钟缓存
    cache_key = "_openrouter_models_cache_time"
    cache_time = getattr(refresh_openrouter_models, cache_key, 0)
    if not force and _openrouter_cached_models and (time.time() - cache_time < 600):
        return _openrouter_cached_models

    print(f"[OpenRouter] 获取模型列表...", file=sys.stderr)
    try:
        data = _curl_get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=30
        )

        models = data.get("data", [])
        candidates = []

        for m in models:
            price = m.get("pricing", {})
            p_prompt = float(price.get("prompt", -1) or -1)
            ctx = m.get("context_length", 0) or 0
            model_id = m.get("id", "")

            # 规则：免费 + ctx >= 32k
            if p_prompt == 0 and ctx >= 32768:
                candidates.append(model_id)

        # 按模型名排序（稳定顺序）
        candidates.sort()
        _openrouter_cached_models = candidates

        # 更新时间戳
        setattr(refresh_openrouter_models, cache_key, time.time())

        print(f"[OpenRouter] 发现 {len(candidates)} 个符合条件的模型", file=sys.stderr)
        if candidates:
            print(f"[OpenRouter] Top 3: {candidates[:3]}", file=sys.stderr)
        return candidates

    except Exception as e:
        print(f"[OpenRouter] 获取模型列表失败: {e}，使用缓存", file=sys.stderr)
        # 失败时返回默认列表（不爆错）
        return _openrouter_cached_models or OPENROUTER_FALLBACK_MODELS


def get_openrouter_models() -> List[str]:
    """获取 OpenRouter 模型列表
    优先使用已验证的付费模型，避免免费模型限流问题
    """
    # 直接返回已验证可用的付费模型，不再用API缓存的免费模型
    return OPENROUTER_FALLBACK_MODELS


# ============ 配置加载 ============

def load_config() -> Dict:
    """加载 Gateway 配置"""
    url = os.environ.get("LLM_API_URL", "http://localhost:3000/v1/chat/completions")
    key = os.environ.get("GATEWAY_AUTH_KEY", os.environ.get("LLM_API_KEY", ""))
    return {
        "llm_api_url": url,
        "llm_api_key": key
    }


def get_scene() -> str:
    """获取当前场景"""
    return os.environ.get("GATEWAY_SCENE", "")


def get_kimi_model(scene: str) -> str:
    """根据场景获取 Kimi 模型"""
    return KIMI_MODEL_MAP.get(scene, "moonshot-v1-128k")


def get_kimi_max_tokens(scene: str) -> int:
    """根据场景获取 Kimi 最大 token 数"""
    return KIMI_MAX_TOKENS_MAP.get(scene, 8192)


def get_nvidia_model(scene: str) -> str:
    """根据场景获取 NVIDIA 模型"""
    return NVIDIA_MODEL_MAP.get(scene, "meta/llama-3.1-70b-instruct")


def get_nvidia_max_tokens(scene: str) -> int:
    """根据场景获取 NVIDIA 最大 token 数"""
    return NVIDIA_MAX_TOKENS_MAP.get(scene, 8192)


# ============ Kimi API 调用 ============

def call_kimi(prompt: str, model: str = "kimi-k2", temperature: float = 0.7, max_tokens: int = 4096) -> Dict:
    """
    调用 Kimi (Moonshot) API

    Args:
        prompt: 提示词
        model: Kimi 模型名
        temperature: 温度
        max_tokens: 最大 tokens

    Returns:
        {"content": str, "error": str|null, "model": str, "provider": str}
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    headers = {
        "Authorization": f"Bearer {KIMI_API_KEY}"
    }

    try:
        result = _curl_post(KIMI_API_URL, payload, headers, timeout=120)
        if not result:
            return {"content": None, "error": "curl failed", "model": model, "provider": "kimi"}
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "content": content,
            "error": None,
            "model": model,
            "provider": "kimi",
            "via_backup": False  # Kimi 是主路径，不是备用
        }
    except Exception as e:
        return {
            "content": None,
            "error": str(e),
            "model": model,
            "provider": "kimi"
        }


# ============ NVIDIA NIM API 调用 ============

def call_nvidia(prompt: str, model: str = "meta/llama-3.1-70b-instruct", temperature: float = 0.7, max_tokens: int = 4096) -> Dict:
    """
    调用 NVIDIA NIM API（OpenAI 兼容）

    Args:
        prompt: 提示词
        model: NVIDIA 模型名
        temperature: 温度
        max_tokens: 最大 tokens

    Returns:
        {"content": str, "error": str|null, "model": str, "provider": "nvidia"}
    """
    if not NVIDIA_API_KEY:
        return {"content": None, "error": "NVIDIA_API_KEY 未配置", "model": model, "provider": "nvidia"}

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}"
    }

    try:
        result = _curl_post(NVIDIA_API_URL, payload, headers, timeout=120)
        if not result:
            return {"content": None, "error": "curl failed", "model": model, "provider": "nvidia"}
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "content": content,
            "error": None,
            "model": model,
            "provider": "nvidia",
        }
    except Exception as e:
        return {
            "content": None,
            "error": str(e),
            "model": model,
            "provider": "nvidia"
        }


# ============ OpenRouter API 调用 ============

def call_openrouter(prompt: str, model: str = "google/gemini-2.0-flash-exp", temperature: float = 0.7) -> Dict:
    """
    调用 OpenRouter API（SSL 问题绕过）

    Args:
        prompt: 提示词
        model: OpenRouter 模型名
        temperature: 温度

    Returns:
        {"content": str, "error": str|null, "model": str, "provider": str}
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 4096
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}"
    }

    try:
        result = _curl_post(OPENROUTER_API_URL, payload, headers, timeout=180)
        if not result:
            return {"content": None, "error": "curl failed", "model": model, "provider": "openrouter"}
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "content": content,
            "error": None,
            "model": model,
            "provider": "openrouter",
            "via_backup": True
            }
    except Exception as e:
        return {
            "content": None,
            "error": str(e),
            "model": model,
            "provider": "openrouter"
        }


# ============ Gateway API 调用 ============

def call_gateway(prompt: str, temperature: float = 0.7) -> Dict:
    """
    调用 Gateway（主路径，免费模型）

    Returns:
        {"content": str, "error": str|null, "via_backup": bool}
    """
    config = load_config()

    if not config["llm_api_url"] or not config["llm_api_key"]:
        return {
            "content": None,
            "error": "Gateway 未配置",
            "via_backup": True
        }

    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }

    headers = {
        "Authorization": f"Bearer {config['llm_api_key']}"
    }
    scene = get_scene()
    if scene:
        headers["X-Gateway-Scene"] = scene

    try:
        result = _curl_post(config["llm_api_url"], payload, headers, timeout=60)
        if not result:
            return {"content": None, "error": "curl failed", "via_backup": True}
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"content": content, "error": None, "via_backup": False}
    except Exception as e:
        return {
            "content": None,
            "error": str(e),
            "via_backup": True  # 超时/网络错误切备用
        }


# ============ 日志配置 ============

import datetime

LOGS_DIR = Path(__file__).parent.parent.parent / ".claude" / "logs"
LLM_CALL_LOG = LOGS_DIR / "llm_call_log.json"


def _ensure_logs_dir():
    """确保 logs 目录存在"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _load_call_log() -> list:
    """加载调用日志"""
    _ensure_logs_dir()
    if LLM_CALL_LOG.exists():
        try:
            return json.loads(LLM_CALL_LOG.read_text(encoding="utf-8")).get("logs", [])
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_call_log(logs: list) -> bool:
    """保存调用日志"""
    try:
        _ensure_logs_dir()
        LLM_CALL_LOG.write_text(
            json.dumps({"logs": logs, "last_updated": datetime.datetime.now().isoformat()}, ensure_ascii=False),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        print(f"[Error] 保存调用日志失败: {e}", file=sys.stderr)
        return False


def _log_llm_call(
    scene: str,
    duration_ms: int,
    status: str,
    provider: str,
    model: str,
    error: str = None,
    tokens: dict = None
) -> bool:
    """
    记录 LLM 调用到日志

    Args:
        scene: 场景
        duration_ms: 耗时（毫秒）
        status: success/timeout/error
        provider: gateway/kimi/openrouter
        model: 模型名
        error: 错误信息
        tokens: {"prompt": int, "completion": int, "total": int}

    Returns:
        bool: 是否成功
    """
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scene": scene,
        "duration_ms": duration_ms,
        "status": status,
        "provider": provider,
        "model": model,
        "error": error,
        "tokens": tokens
    }

    logs = _load_call_log()
    logs.append(log_entry)

    # 只保留最近 1000 条
    if len(logs) > 1000:
        logs = logs[-1000:]

    return _save_call_log(logs)


# ============ 响应验证 ============

def _validate_response(result: dict, provider: str) -> Tuple[bool, str]:
    """
    验证 LLM 响应格式

    Args:
        result: API 返回的原始 dict
        provider: 提供商

    Returns:
        (是否有效, 错误信息)
    """
    if not isinstance(result, dict):
        return False, f"响应不是 dict 类型: {type(result)}"

    # 检查 choices 字段
    choices = result.get("choices", [])
    if not choices:
        return False, "响应缺少 choices 字段"

    if not isinstance(choices, list):
        return False, f"choices 不是列表: {type(choices)}"

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return False, f"choices[0] 不是 dict: {type(first_choice)}"

    # 检查 message 字段
    message = first_choice.get("message", {})
    if not isinstance(message, dict):
        return False, f"message 不是 dict: {type(message)}"

    # 检查 content 字段
    content = message.get("content")
    if content is None:
        return False, "message.content 为 None"

    if not isinstance(content, str):
        return False, f"content 不是字符串: {type(content)}"

    # 检查 finish_reason
    finish_reason = first_choice.get("finish_reason")
    if finish_reason and finish_reason not in ["stop", "length"]:
        return False, f"非标准 finish_reason: {finish_reason}"

    return True, ""


# ============ 超时配置 ============

DEFAULT_TIMEOUT = 30  # 默认 30 秒


# ============ 重试配置 ============

def _retry_with_backoff(fn, max_retries: int = 2, initial_delay: float = 1.0) -> Dict:
    """
    指数退避重试

    Args:
        fn: 要重试的函数
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）

    Returns:
        函数结果
    """
    delay = initial_delay

    for attempt in range(max_retries + 1):
        result = fn()
        if result.get("error") is None:
            return result

        if attempt < max_retries:
            print(f"[重试] {attempt + 1}/{max_retries} 失败，{delay}s 后重试...", file=sys.stderr)
            time.sleep(delay)
            delay *= 2  # 指数退避：1s, 2s

    return result


# ============ 结构化错误 ============

def _make_structured_error(provider: str, error: str, retry_count: int = 0) -> Dict:
    """
    生成结构化错误

    Returns:
        包含 error_type, error_message, retryable, provider 的 dict
    """
    error_type = "unknown"
    retryable = False

    if any(x in error.lower() for x in ["timeout", "timed out"]):
        error_type = "timeout"
        retryable = True
    elif "http 500" in error.lower() or "internal" in error.lower():
        error_type = "server_error"
        retryable = True
    elif "http 4" in error.lower():
        error_type = "client_error"
        retryable = False
    elif "connection" in error.lower():
        error_type = "network"
        retryable = True

    return {
        "content": None,
        "error": error,
        "error_type": error_type,
        "retryable": retryable,
        "retry_count": retry_count,
        "provider": provider,
        "model": "none"
    }


# ============ 错误可重试性判断 ============

def _is_retryable_error(error: str) -> bool:
    """
    判断 LLM 错误是否可重试

    可重试：timeout、connection、network、SSL、502/503/504
    不可重试：401 Unauthorized、403 Forbidden、400 Bad Request（请求本身有问题）
    """
    error_lower = error.lower()
    if any(x in error_lower for x in ["http 401", "http 403", "unauthorized", "forbidden", "bad request", "invalid request"]):
        return False
    if any(x in error_lower for x in ["timeout", "connection", "network", "ssl", "temporary", "502", "503", "504", "reset", "refused"]):
        return True
    return True  # 默认可重试


def _call_with_retry(fn, prompt: str, *args, max_retries: int = 2, initial_delay: float = 1.0, **kwargs) -> Dict:
    """
    带指数退避重试的 provider 调用

    Args:
        fn: 要重试的函数 (prompt, *args, **kwargs) -> result_dict
        prompt: 提示词
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）

    Returns:
        函数结果（成功或最终失败）
    """
    delay = initial_delay
    last_result = None

    for attempt in range(max_retries + 1):
        result = fn(prompt, *args, **kwargs)
        last_result = result

        if result.get("error") is None:
            return result  # 成功

        error = result.get("error", "")
        if not _is_retryable_error(error):
            # 不可重试的错误（如 401），直接返回
            return result

        if attempt < max_retries:
            print(f"[重试] {attempt + 1}/{max_retries} 失败，{delay}s 后重试... ({error[:50]})", file=sys.stderr)
            time.sleep(delay)
            delay *= 2  # 指数退避

    return last_result  # 返回最后一次结果


# ============ 主调用函数 ============

def call_llm(prompt: str, model: str = "gpt-4", temperature: float = 0.7) -> Dict:
    """
    四层 fallback 调用：
    1. Kimi (付费) — 主路径，按场景动态选择 8k/32k/128k
    2. NVIDIA NIM (高速推理) — Kimi 失败后首选降级
    3. Gateway (免费模型) — 备用
    4. OpenRouter (付费备用) — 最终降级

    所有 provider 失败即止，不重试。

    Args:
        prompt: 提示词
        model: 模型名（仅用于 Gateway）
        temperature: 温度

    Returns:
        {"content": str, "error": str|null, "model": str, "provider": str, "via_backup": bool}
    """
    scene = get_scene()
    start_time = time.time()

    # Step 1: Kimi (主路径，场景动态模型，带重试)
    kimi_model = get_kimi_model(scene)
    kimi_max_tokens = get_kimi_max_tokens(scene)
    print(f"[Kimi] {kimi_model}({kimi_max_tokens})...", file=sys.stderr)
    result = _call_with_retry(call_kimi, prompt, kimi_model, temperature, kimi_max_tokens, max_retries=1)
    duration_ms = int((time.time() - start_time) * 1000)
    _log_llm_call(scene, duration_ms, "success" if result["error"] is None else "error",
                   "kimi", kimi_model, result.get("error"))
    if result["error"] is None:
        return result

    kimi_error = result["error"]
    print(f"[Kimi] 失败: {kimi_error}", file=sys.stderr)

    # Step 1.5: NVIDIA NIM (高速推理，Kimi 失败后首选降级，带重试)
    nvidia_model = get_nvidia_model(scene)
    nvidia_max_tokens = get_nvidia_max_tokens(scene)
    print(f"[NVIDIA] {nvidia_model}({nvidia_max_tokens})...", file=sys.stderr)
    result = _call_with_retry(call_nvidia, prompt, nvidia_model, temperature, nvidia_max_tokens, max_retries=1)
    duration_ms = int((time.time() - start_time) * 1000)
    _log_llm_call(scene, duration_ms, "success" if result["error"] is None else "error",
                   "nvidia", nvidia_model, result.get("error"))
    if result["error"] is None:
        return result

    nvidia_error = result["error"]
    print(f"[NVIDIA] 失败: {nvidia_error}", file=sys.stderr)

    # Step 2: Gateway (免费模型，Kimi 失败后尝试，带重试)
    print(f"[Gateway] 尝试...", file=sys.stderr)
    result = _call_with_retry(call_gateway, prompt, temperature, max_retries=1)
    duration_ms = int((time.time() - start_time) * 1000)
    _log_llm_call(scene, duration_ms, "success" if result["error"] is None else "error",
                   "gateway", model, result.get("error"))
    if result["error"] is None:
        result["model"] = scene or "gateway"
        result["provider"] = "gateway"
        return result

    gw_error = result["error"]
    print(f"[Gateway] 失败: {gw_error}", file=sys.stderr)

    # Step 3: OpenRouter 最终降级（使用动态模型列表，带重试）
    for or_model in get_openrouter_models():
        print(f"[OpenRouter] {or_model}...", file=sys.stderr)
        result = _call_with_retry(call_openrouter, prompt, or_model, temperature, max_retries=1)
        duration_ms = int((time.time() - start_time) * 1000)
        _log_llm_call(scene, duration_ms, "success" if result["error"] is None else "error",
                       "openrouter", or_model, result.get("error"))
        if result["error"] is None:
            return result
        print(f"[OpenRouter] 失败: {result['error']}", file=sys.stderr)

    return _make_structured_error("none", f"所有 provider 都失败: Kimi={kimi_error}, NVIDIA={nvidia_error}")


# ============ 统一 LLM 原始文本调用 ============

def call_llm_raw(
    prompt: str,
    temperature: float = 0.7,
    scene: str = "writing-cn",
    error_prefix: str = "[LLM]"
) -> Optional[str]:
    """
    统一的 LLM 调用封装，返回原始文本内容。
    所有模块通过此函数或 shim 调用，避免重复实现。

    Args:
        prompt: LLM 提示词
        temperature: 温度（默认 0.7）
        scene: GATEWAY_SCENE 值（默认 "writing-cn"）
        error_prefix: stderr 错误信息前缀

    Returns:
        原始文本内容，失败返回 None
    """
    os.environ["GATEWAY_SCENE"] = scene
    result = call_llm(prompt, temperature=temperature)
    if result.get("error"):
        print(f"{error_prefix} {result['error']}", file=sys.stderr)
        return None
    return result.get("content", "")


# ============ CLI 入口 ============

def main():
    # 启动时刷新 OpenRouter 模型列表
    refresh_openrouter_models()
    print(f"[OpenRouter] 当前模型: {get_openrouter_models()[:3]}...", file=sys.stderr)

    if len(sys.argv) < 2:
        print(json.dumps({"error": "用法: python call_llm.py '<prompt>'"}))
        sys.exit(1)

    prompt = sys.argv[1]
    result = call_llm(prompt)

    # 输出（修复 Windows GBK 编码）
    output = json.dumps(result, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()