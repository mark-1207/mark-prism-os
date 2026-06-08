# Phase 6.0 数据反馈闭环

> 独立支线，与 L41 主流程**平行**，由 Windows 计划任务每日 03:00 自动触发
> 不修改主流程；v1.3.0 引入，v1.3.1 接入 calibration

## 目标

把"生成 → 发布"补成完整飞轮，让 PRISM-OS 从「生成工具」进化成「数据驱动的创作者操作系统」。

## 架构

```
[用户发布文章] → [用户每天在飞书表填 5 个数字]
                       ↓
              [飞书多维表格 PRISM-OS 内容表现库]
                       ↓
        [PRISM-OS 后台每天 03:00 增量拉取]
                       ↓
        [数据校准（模板优选 / HKR 校准）]
                       ↓
        [下次 run/narrate 自动应用新校准]
```

## 核心约定

- **手动录入**：用户只填 5 个数字（阅读/转发/收藏/点赞/评论）
- **3 个时间点**：T+1d / T+7d / T+30d（每篇 3 行，缺失容忍）
- **零 CLI 参与**：Windows 计划任务每天 03:00 自动跑
- **冷启动**：<3 篇样本不推荐任何策略

## 飞书多维表字段

16 基础字段 + 5 公式字段：

| 字段名 | 类型 | 备注 |
|--------|------|------|
| 文章标题 | 文本 | 关联 `topic_log.yaml` |
| 平台 | 单选 | wechat / xiaohongshu |
| 命题 | 文本 | 原始输入 |
| CCOS 主题结构 | 单选 | 4 选 1 |
| 叙事策略 | 单选 | 6 选 1 |
| T+1d 阅读 | 数字 | 手动填 |
| T+1d 转发 | 数字 | 手动填 |
| T+1d 收藏 | 数字 | 手动填 |
| T+1d 点赞 | 数字 | 手动填 |
| T+1d 评论 | 数字 | 手动填 |
| T+7d ... | 5 个数字字段 | 同上 |
| T+30d ... | 5 个数字字段 | 同上 |
| 互动率 | 公式 | (转发+收藏+点赞+评论) / 阅读 |
| 总互动 | 公式 | T+1d+T+7d+T+30d 加和 |

## 反哺机制 B（模板优选，v1.3.0 MVP）

- 按「平台 × 叙事策略」/「平台 × CCOS 模块组合」统计真实互动率
- 输出到 `data/feedback_calibration.yaml`
- `narrate` 步骤按 calibration 调整策略推荐权重

## 反哺机制 A（HKR 校准，v1.3.1 延后）

- 30+ 篇后启动
- 用真实互动率反推 H/K/R 哪个维度真预测有用
- 棱镜引擎打分时叠加校准系数

## CLI 调试命令

```bash
python scripts/metrics_sync.py          # 手动触发同步
python scripts/prism_os.py metrics sync  # 等价
python scripts/prism_os.py metrics status # 查看反哺状态
```

## Windows 计划任务

`scripts/setup_scheduler.ps1` 注册任务"PRISM-OS Metrics Sync"，每天 03:00 跑 `metrics_sync_wrapper.bat`。
