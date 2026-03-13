# openclaw-long-task-kit 差距分析报告

> 基于两份深度研究文档（deep-research-report.md、compass 报告）与项目现状的对比分析
> 生成日期：2026-03-13

---

## 项目现状总结

项目核心骨架已非常扎实：

- **状态管理**：原子写入（tmp + rename）、fcntl 内核锁、TOCTOU 安全
- **Schema 验证**：零外部依赖的手写验证器，硬错误 + 软警告分级
- **Cron 矩阵**：4 个标准 cron 任务（watchdog / continuation / deadman / closure-check）
- **策略引擎**：continuation（继续决策）、deadman（沉默检测）、exhaustion（资源耗尽）
- **生成器**：heartbeat_entry / boot_entry / agents_directive / cron_matrix
- **CLI 命令**：init / preflight / lock / close / pointer / status / watchdog（7 个）
- **质量保证**：mypy --strict、ruff lint/format、111+ 测试用例、CI 矩阵（Python 3.11-3.13）

---

## 一、高优先级缺失（报告反复强调但项目未覆盖）

| # | 缺失项 | 报告依据 | 影响 |
|---|--------|---------|------|
| 1 | **无 README.md** | — | 项目完全没有用户文档，新用户无从入手 |
| 2 | **`init` 未调用 boot_entry / agents_directive 生成器** | 报告强调 BOOT.md 恢复清单和 AGENTS.md 自主行为指令是 24/7 的关键 | 生成器已实现但在 init 流程中被跳过，形同废代码 |
| 3 | **无 Gateway 健康检查** | 报告第一步：确认 Gateway 常驻与可达（`openclaw status/health`） | preflight 检查了文件但没验证 Gateway 是否真正在运行 |
| 4 | **无 Webhook 触发支持** | 两份报告都将 `/hooks/wake` 和 `/hooks/agent` 列为外部系统回调的核心桥梁 | 完全没有 webhook 相关的命令或配置 |
| 5 | **无 systemd/launchd 服务模板** | 报告反复强调 `loginctl enable-linger` 和 supervisor 监管是 24/7 底座 | 用户需自行解决守护进程问题 |
| 6 | **无结构化日志** | 报告建议启用 JSONL 日志和 OTel/OTLP 导出 | 所有输出仅通过 `click.echo`，无法接入监控系统 |

---

## 二、中优先级改进（会显著提升可用性）

| # | 改进项 | 说明 |
|---|--------|------|
| 7 | **缺少 `ltk doctor` 命令** | 参照 `openclaw doctor`，一键诊断环境：Gateway 可达性、cron 可用性、lingering 状态、工作区权限等 |
| 8 | **缺少 `ltk resume` 命令** | BOOT.md 生成器已实现，但没有对应的"从恢复清单自动恢复"命令 |
| 9 | **无 MEMORY.md / memory/*.md 管理** | 报告强调"模型只记住写入磁盘的内容"，记忆是跨会话连续性的基础；项目完全没涉及 |
| 10 | **无通知发送能力** | `telegram_chat_id` 在配置中但没有任何实际发送逻辑；deadman/watchdog 检测到问题后无法主动告警 |
| 11 | **continuation prompt 未对接 cron** | `build_continuation_prompt()` 生成了提示文本，但 cron 任务的 payload 只是静态字符串，没有动态读取状态后生成 |
| 12 | **exhaustion 策略未集成到任何命令** | `ExhaustionResult` 返回 pause/escalate/abort 建议，但没有命令消费这个结果 |

---

## 三、低优先级但有价值

| # | 改进项 | 说明 |
|---|--------|------|
| 13 | **多任务并行管理** | 当前 pointer 只支持单个活跃任务；报告提到 `maxConcurrent` 和 lanes 并行 |
| 14 | **外部 Worker 桥接** | 报告建议小时级任务外置到 Celery/Temporal；可提供 `ltk delegate` 命令 |
| 15 | **compaction 感知** | 报告提到上下文窗口压缩导致"失忆"；可在状态中追踪 token 消耗和压缩事件 |
| 16 | **工具审批策略检查** | 报告指出 `approval-pending` 是隐蔽的卡点；preflight 可检查 exec-approvals 配置是否合理 |

---

## 四、代码质量层面的小问题

| # | 问题 | 位置 |
|---|------|------|
| 17 | `close` 命令测试仅 2 个用例 | `tests/test_close.py` — 缺少 partial close、heartbeat 移除失败、write-back 等场景 |
| 18 | `lock` 命令测试仅 3 个用例 | `tests/test_lock.py` — 缺少 TTL 过期、续期、并发竞争等场景 |
| 19 | `pointer` 测试仅 3 个用例 | `tests/test_pointer.py` — 缺少文件损坏、权限错误等边界 |

---

## 五、建议实施优先级

### 第一批：补齐核心闭环

1. 在 `init` 中集成 BOOT.md 和 AGENTS.md 生成器（代码已有，只需调用）
2. 添加 Gateway 可达性检查到 preflight
3. 编写 README.md

### 第二批：提升运维能力

4. 实现 `ltk doctor` 环境诊断命令
5. 添加 systemd 用户服务模板文件（`deploy/` 目录）
6. 引入 `logging` 模块替代纯 `click.echo`

### 第三批：扩展能力

7. Webhook 触发支持
8. 通知发送能力（Telegram/Slack）
9. `ltk resume` 恢复命令
10. 补充 close/lock/pointer 的测试覆盖

---

## 六、研究报告关键机制与项目映射

| 研究报告提到的机制 | 项目是否覆盖 | 说明 |
|-------------------|-------------|------|
| Gateway 守护进程（systemd/launchd） | 未覆盖 | 无服务模板 |
| Heartbeat + HEARTBEAT.md | 已覆盖 | heartbeat_entry 生成器 + preflight 检查 |
| Cron 定时任务 | 已覆盖 | cron_matrix 4 个标准任务 + CronClient |
| 任务状态落盘（JSON） | 已覆盖 | StateFile 原子写入 + schema 验证 |
| 分布式锁 | 已覆盖 | lock acquire/release + TTL |
| Webhooks（/hooks/wake, /hooks/agent） | 未覆盖 | 无相关代码 |
| MEMORY.md / memory/*.md 记忆体系 | 未覆盖 | 无记忆管理 |
| BOOT.md 恢复清单 | 部分覆盖 | 生成器已实现，但未集成到 init |
| AGENTS.md 自主行为指令 | 部分覆盖 | 生成器已实现，但未集成到 init |
| 工具审批策略检查 | 部分覆盖 | preflight 检查 exec-approvals 文件存在性 |
| 外部 Worker 桥接 | 未覆盖 | 无 Celery/Temporal 集成 |
| 结构化日志 / OTel | 未覆盖 | 仅 click.echo |
| 通知告警（Telegram 等） | 未覆盖 | 配置有 chat_id 但无发送逻辑 |
| 上下文压缩（compaction）感知 | 未覆盖 | 无 token 追踪 |
| 多任务并行 | 未覆盖 | pointer 仅支持单任务 |
