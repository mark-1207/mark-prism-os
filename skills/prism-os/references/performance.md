# 性能优化 + LLM Fallback

## LLM 4 级 Fallback 顺序

```
Kimi (moonshot-v1-128k)
  ↓ 失败
NVIDIA NIM (meta/llama-3.1-70b-instruct 等)
  ↓ 失败
Gateway（用户自建代理）
  ↓ 失败
OpenRouter (qwen / deepseek / gemma / mistral / llama 多模型轮询)
  ↓ 全部失败
[Error] 流程终止
```

每个 provider 内部 1 次重试，1.0s 间隔。

## 性能优化点

### 1. embedding 缓存

- 路径：`data/embedding_cache.json`
- 命中：跳过实际 embedding 计算
- 失效：手动删除或跑 `python scripts/prism_os.py embedding --rebuild`

### 2. 双端大纲合并

CCOS 旧版：双端 18 次 LLM 调用 → 新版 12 次（v1.0.7 优化）。

### 3. 棱镜引擎批次生成

旧版：4 维度 × 3 个 = 12 次 LLM 调用  
新版：4 维度 × 1 次（每个返回 3 个）= 4 次 LLM 调用（v1.2.0 重构）

### 4. 候选标题正交性校验

```python
check_orthogonality(candidates)
```

- 阈值：cosine similarity < 0.75
- 最多重试 3 次
- 超阈值仍不符合则保留 + 标注警告

## 单次 `run` 耗时参考

| 阶段 | 耗时 | LLM 调用 |
|------|------|----------|
| Phase 0 意图 | < 1s | 1 |
| Phase 1 网关 | 2-5s | 1-2 |
| Phase 2 棱镜 | 8-15s | 4 |
| Phase 3 现实 | 5-10s | 1-4 |
| Phase 3.5 数字分身 | 2-3s | 1 |
| Phase 4.5 CCOS | 30-60s | 4-8 |
| Phase 5 逻辑 | 3-5s | 1 |
| Phase 6 存储 | < 1s | 0 |
| **合计** | **~60-100s** | **~14-22 次** |

## 失败排查

### curl failed

API 连不上，4 个 provider 都失败。检查：
- 网络是否通
- API key 是否有效
- 是否被风控

### 静默默认（GAP-3/4）

stdin 不可用时 `run` 静默选第一个 / 静默继续。详见 [CLAUDE.md GAP-3/4](../CLAUDE.md)。
