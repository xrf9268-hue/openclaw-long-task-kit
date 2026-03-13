# openclaw-long-task-kit 差距分析报告

> 基于两份深度研究文档、当前项目代码，以及 upstream `openclaw/openclaw` 参考实现的对比分析
> 最后校正日期：2026-03-13

---

## 项目现状总结

项目已经具备一套可用的长任务控制平面雏形：

- **状态管理**：有原子写入、`fcntl` 文件锁、状态文件封装、显式错误包装
- **Schema 验证**：零外部依赖的手写验证器，区分硬错误与软警告
- **Cron 矩阵**：4 个标准任务生成器（watchdog / continuation / deadman / closure-check）
- **策略引擎**：continuation、deadman、exhaustion 三类策略函数已实现
- **生成器**：`heartbeat_entry` / `boot_entry` / `agents_directive` / `cron_matrix`
- **CLI 命令**：`init` / `preflight` / `lock` / `close` / `pointer` / `status` / `watchdog`
- **质量保证**：`mypy --strict`、`ruff`、CI 覆盖 Python 3.11-3.13；本地已验证 `pytest` **120 passed**

但它距离研究报告和 upstream OpenClaw 所描述的“24/7 自主推进系统”仍有明显差距，而且当前报告原版对少数能力有**高估覆盖度**的问题。

---

## 审查后关键更正

1. **不能把当前状态层描述为“TOCTOU 安全”**  
   当前实现同时使用锁和原子 rename，但 `locked_update()` 持有的是旧 inode 的锁，随后通过 `os.rename()` 覆盖路径；这意味着 rename 后的新文件不再受旧锁约束，仍存在并发一致性窗口。

2. **`Heartbeat + HEARTBEAT.md` 只能算“部分覆盖”**  
   当前项目只实现了 HEARTBEAT 条目写入和 preflight 标记检查，并未实现 upstream OpenClaw Heartbeat 的 cadence、target、directPolicy、activeHours、24/7 调度等能力。

3. **“工具审批策略检查”不能算已部分覆盖 upstream 真实能力**  
   当前 preflight 只检查 workspace 下是否存在 `exec-approvals.*` 文件；而 upstream OpenClaw 的真实审批策略位于主机级 `~/.openclaw/exec-approvals.json`。

4. **原报告低估了 OpenClaw 的记忆与自我推进能力面**  
   upstream 不只有 `MEMORY.md / memory/*.md` 文件布局，还有 `memory_search` / `memory_get` 工具、预压缩 memory flush、memory CLI、索引/检索后端等。

---

## 一、高优先级缺口与风险

| # | 缺口/风险 | 现状 | 影响 |
|---|-----------|------|------|
| 1 | **状态文件并发一致性仍有窗口** | 有 `flock` + atomic rename，但锁与最终落盘 inode 不是同一对象 | 会高估状态层可靠性，后续并发命令容易踩出隐蔽竞态 |
| 2 | **`init` 未接入 `BOOT.md` / `AGENTS.md` 生成器** | 生成器存在，但初始化流程只写 state + cron + HEARTBEAT | BOOT 恢复清单和自主行为指令没有真正进入工作流 |
| 3 | **Heartbeat 仅覆盖文件条目，不覆盖真正调度能力** | 无 cadence、target、activeHours、24/7 配置层 | 很难把项目对齐到研究报告强调的“无人值守推进” |
| 4 | **无 Gateway 健康检查** | `preflight` 只检查本地状态/文件/cron 声明 | 无法验证 `openclaw status/health`、守护进程可达性、网关在线性 |
| 5 | **无 Webhook 触发支持** | 没有 `/hooks/wake` / `/hooks/agent` 相关桥接 | 无法接外部系统回调，长任务自动化闭环不完整 |
| 6 | **无 systemd / launchd 服务模板** | 没有 daemon/lingering/onboarding 配套 | 24/7 持续运行底座缺失 |
| 7 | **无结构化日志 / 诊断导出** | 主要输出仍是 `click.echo` | 不能对齐 upstream JSONL 日志、`logs --follow`、诊断标记和可观测性能力 |

---

## 二、中优先级改进

| # | 改进项 | 说明 |
|---|--------|------|
| 8 | **缺少 `ltk doctor` 命令** | upstream 有 `openclaw doctor`；当前缺统一环境诊断入口 |
| 9 | **缺少 `ltk resume` 命令** | `BOOT.md` 生成器存在，但无“按恢复清单继续任务”的命令 |
| 10 | **无 MEMORY.md / memory/*.md 管理** | 当前没有 daily memory、long-term memory、写入约定、检索入口 |
| 11 | **无 memory tools / memory flush 设计** | 与 upstream 的 `memory_search` / `memory_get` / pre-compaction memory flush 相比缺口很大 |
| 12 | **无通知发送能力** | `telegram_chat_id` 仅出现在配置中，没有任何实际发送逻辑 |
| 13 | **continuation prompt 未接入 cron 任务** | `build_continuation_prompt()` 已实现，但 cron payload 仍是静态文案 |
| 14 | **exhaustion 策略未集成到任何命令** | 只有策略函数，没有触发链路 |
| 15 | **README.md 缺失** | 这是产品化缺口，但优先级低于 24/7 主链路缺口 |
| 16 | **审批检查未指向真实 OpenClaw 主机配置** | 当前只看 workspace 文件，不看 `~/.openclaw/exec-approvals.json` |

---

## 三、低优先级但有价值

| # | 改进项 | 说明 |
|---|--------|------|
| 17 | **多任务并行管理** | 当前 pointer 只有“单活跃任务”语义，没有 lanes / maxConcurrent 对应物 |
| 18 | **外部 Worker 桥接** | 与研究报告建议的 Celery / Temporal / Airflow 外置执行层仍有距离 |
| 19 | **compaction 感知** | 没有 token 消耗、压缩前 flush、上下文裁剪可见性 |
| 20 | **Hook 体系缺失** | 当前没有类似 upstream `session-memory`、`command-logger`、`boot-md` 这类内部事件 hooks |

---

## 四、代码质量与测试观察

| # | 问题 | 位置 |
|---|------|------|
| 21 | `close` 用例偏少 | `tests/test_close.py`：当前 2 个测试，缺 partial close、heartbeat 删除失败、write-back 失败等场景 |
| 22 | `lock` 用例偏少 | `tests/test_lock.py`：当前 3 个测试，缺 TTL 过期、同 owner 续期、损坏锁状态等场景 |
| 23 | `pointer` 用例偏少 | `tests/test_pointer.py`：当前 3 个测试，缺损坏 JSON、权限错误等边界 |
| 24 | 测试总量应更新 | 当前总计 **120** 个测试，不应再写 “111+” |

补充说明：

- 本地已在 WSL 中创建 `.venv` 并执行 `pytest -q`
- 结果：**120 passed**

---

## 五、研究报告关键机制与项目映射

| 研究/上游机制 | 项目是否覆盖 | 说明 |
|----------------|-------------|------|
| Gateway 守护进程（systemd/launchd） | 未覆盖 | 无服务模板、无守护安装流程 |
| Heartbeat 调度（every/target/activeHours/directPolicy） | 未覆盖 | 没有 heartbeat runtime/config 语义 |
| HEARTBEAT.md 条目写入 | 已覆盖 | `heartbeat_entry` 生成器 + preflight 标记检查 |
| Cron 定时任务 | 已覆盖 | `cron_matrix` 4 个标准任务 + `CronClient` |
| 任务状态落盘（JSON） | 已覆盖 | `StateFile` + schema 验证 |
| 分布式锁/主机级协调锁 | 部分覆盖 | 有单状态文件锁，但并发语义仍有窗口，不宜称分布式锁 |
| Webhooks（`/hooks/wake`, `/hooks/agent`） | 未覆盖 | 无相关代码 |
| Internal Hooks | 未覆盖 | 无事件驱动 hook 体系 |
| `MEMORY.md` / `memory/*.md` 体系 | 未覆盖 | 无记忆文件管理 |
| memory tools（`memory_search` / `memory_get`） | 未覆盖 | 无语义检索与定向读取 |
| pre-compaction memory flush | 未覆盖 | 无压缩前静默记忆落盘机制 |
| BOOT.md 恢复清单 | 部分覆盖 | 生成器存在，但未接入 `init` |
| AGENTS.md 自主行为指令 | 部分覆盖 | 生成器存在，但未接入 `init` |
| 工具审批策略检查 | 未覆盖 | 仅检查 workspace 文件，不对应 upstream 主机级配置 |
| 外部 Worker 桥接 | 未覆盖 | 无 Celery / Temporal / Airflow 集成 |
| `doctor` 健康诊断 | 未覆盖 | 无统一诊断命令 |
| `logs --follow` / JSONL 日志 | 未覆盖 | 无日志读取接口、无结构化落盘 |
| Diagnostics / OTel / flags | 未覆盖 | 无诊断标记、无导出 |
| 通知告警（Telegram 等） | 未覆盖 | 配置存在，发送逻辑缺失 |
| 上下文压缩感知 | 未覆盖 | 无 token / compaction 状态追踪 |
| 多任务并行 | 未覆盖 | pointer 仅支持单任务 |

---

## 六、upstream OpenClaw 关键能力清单（长任务 / 自我推进 / 24/7）

下表用于明确“目标系统到底有哪些能力”，避免后续补差时只盯住少数文件名。

| 能力域 | upstream OpenClaw 已具备的能力 | 当前 kit 状态 |
|--------|--------------------------------|--------------|
| 24/7 运行底座 | Gateway 常驻、systemd/launchd、doctor、daemon 安装、日志追踪 | 基本未覆盖 |
| Heartbeat | `every`、`target`、`directPolicy`、`lightContext`、`includeReasoning`、`activeHours`、24/7 配置 | 未覆盖 runtime；仅有 HEARTBEAT 条目生成 |
| Cron | main / isolated session、wakeMode、announce / webhook delivery、failureAlert | 仅覆盖“生成 4 个基础 cron spec” |
| Hooks | `session-memory`、`boot-md`、`command-logger`、`bootstrap-extra-files` 等 | 未覆盖 |
| Webhooks | `/hooks/wake`、`/hooks/agent`、CLI helper、外部系统触发 | 未覆盖 |
| 记忆文件 | `MEMORY.md`、`memory/YYYY-MM-DD.md`、workspace 约定 | 未覆盖 |
| 记忆工具 | `memory_search`、`memory_get`、memory CLI、索引后端 | 未覆盖 |
| 自我进化/自我整理 | pre-compaction memory flush、daily memory、long-term memory 提炼 | 未覆盖 |
| 审批与宿主执行 | `approval-pending`、`/approve`、`exec-approvals.json`、allowlist、safe bins | 未覆盖真实实现 |
| 可观测性 | JSONL 日志、`openclaw logs --follow`、diagnostics flags、health/doctor | 未覆盖 |

其中与“长任务、自我推进、24/7”最相关的 upstream 文档/实现面包括：

- `docs/gateway/heartbeat.md`
- `docs/automation/hooks.md`
- `docs/cli/webhooks.md`
- `docs/concepts/memory.md`
- `docs/tools/exec-approvals.md`
- `docs/cli/doctor.md`
- `docs/cli/logs.md`
- `docs/diagnostics/flags.md`

---

## 七、建议实施优先级

### 第一批：修正基础判断并补齐主链路

1. 修正报告中的覆盖结论：Heartbeat 改为“部分覆盖/未覆盖 runtime”，审批改为“未覆盖真实主机配置”
2. 在 `init` 中接入 `BOOT.md` 和 `AGENTS.md` 生成器
3. 明确修复状态文件锁语义问题，避免继续把它当作“已解决”
4. 给 `preflight` 增加 Gateway 可达性/健康检查

### 第二批：补齐 OpenClaw 24/7 关键能力

5. 实现 `ltk doctor`
6. 增加 systemd/launchd 模板或安装脚本
7. 增加结构化日志与日志读取入口
8. 实现真正的 heartbeat 配置层，而不只是 HEARTBEAT.md 条目写入

### 第三批：补齐长任务与自我推进能力

9. 引入 MEMORY 文件体系
10. 设计 memory tools / memory flush / compaction 感知
11. 增加 Webhook 与 Hook 体系
12. 让 continuation / exhaustion / notification 进入真实命令链路

### 第四批：完善工程质量

13. 补 README
14. 补 close / lock / pointer 边界测试
15. 设计多任务并行与外部 worker 桥接

---

## 八、结论

`openclaw-long-task-kit` 已经有一个不错的“控制平面原型”，但它当前更接近：

- **任务状态文件 + cron 生成器 + preflight 检查器**

而不是研究报告和 upstream OpenClaw 所描述的：

- **可 24/7 常驻、可自主推进、具备记忆、自带审批闭环、可观测、可被外部事件驱动的长任务执行系统**

因此，后续补差不能只围绕 README、几个命令和模板展开，而应围绕以下主链路来设计：

1. 守护进程与健康检查
2. Heartbeat/Cron/Webhook 自动推进
3. 记忆体系与状态落盘
4. 审批与宿主执行边界
5. 结构化日志与诊断
