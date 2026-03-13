# OpenClaw 24/7 持续运行机制深度解析

**OpenClaw 的持续运行能力并非单一功能开关，而是由 Heartbeat 心跳调度、Markdown 记忆体系、systemd 自恢复守护三大组件协同构成的架构级设计。** 正确配置后，它能作为一个常驻的自主 AI Agent 全天候运转；配置不当则退化为普通的问答式聊天机器人。本报告基于 GitHub 源码、官方文档、社区实测及 win4r 生态项目的全面调研，系统拆解其 24/7 运行机制。

**重要背景说明**：OpenClaw 主仓库为 [openclaw/openclaw](https://github.com/openclaw/openclaw)（截至 2026 年 3 月已超 **30 万 GitHub Stars**），由奥地利开发者 Peter Steinberger 创建。**win4r（秦超）** 是核心生态贡献者，维护了 openclaw-min-bundle（自恢复网关）、OpenClaw-Skill（Agent 参考文档）、memory-lancedb-pro（增强记忆插件）、openclaw-a2a-gateway（跨 Agent 通信）、team-tasks（多 Agent 流水线）、claude-code-hooks（Claude Code 集成）等六个生态项目，专注于**运维可靠性和功能扩展**。

---

## 一个 Node.js 进程撑起整个自主 Agent

OpenClaw 的核心架构极其简洁：**一个长驻的 Node.js 进程（Gateway）承载全部功能**——渠道连接、会话管理、Agent 循环、模型调用、工具执行、记忆持久化。无需额外服务编排，默认监听 `ws://127.0.0.1:18789`。

Gateway 内部由五个子系统协同运转。**Channel Adapters** 负责对接 20+ 消息平台（WhatsApp、Telegram、Slack、Discord、iMessage、飞书等），将不同平台的消息格式统一化。**Session Manager** 解析发送者身份和对话上下文，DM 合并到主会话，群聊各自独立。**Queue（Lane Queue）** 按会话序列化 Agent 运行，防止工具调用和状态的竞态条件，当消息在 Agent 运行中到达时，根据模式（steer/followup/collect）决定注入、追加或排队。**Agent Runtime（PiEmbeddedRunner）** 是核心执行引擎，基于 pi-mono 开源编码 Agent，以嵌入式 RPC 模式运行 ReAct 循环。**Control Plane** 通过 WebSocket 暴露 API，CLI、macOS 应用、Web UI 和移动端均通过此连接。

Agent 的每次执行遵循标准 **ReAct 循环模式**：组装上下文（系统提示 + 记忆文件 + 技能列表）→ 调用 LLM → 如果返回工具调用则执行工具并将结果喂回模型 → 循环直到模型产出纯文本回复 → 响应推送到渠道 → 会话记录写入 JSONL 文件 → 触发记忆压缩刷新。**这个循环会持续迭代直到任务完成**，不是一次问答就结束。

---

## Heartbeat 心跳系统：让 Agent "自己醒来"

**Heartbeat 是 OpenClaw 从被动问答跨越到主动自治的关键机制。** 它本质上是一个定时触发的 Agent 循环——不需要人类发消息，系统每隔固定时间（默认 **30 分钟**）自动唤醒 Agent。

心跳触发时，Gateway 向 Agent 注入一段标准提示："读取 HEARTBEAT.md，严格按其执行。不要从历史对话推断任务。如果没有需要关注的事项，回复 HEARTBEAT_OK。" Agent 随后读取工作区中的 `HEARTBEAT.md` 文件——这是一个用户自定义的 Markdown 检查清单，例如"扫描收件箱有无紧急邮件"、"检查后台任务是否完成"、"查看 cron 任务状态"。如果 Agent 判断一切正常，返回 `HEARTBEAT_OK`，Gateway **静默丢弃**该响应，用户完全无感知；如果有需要上报的内容，Agent 返回告警文本并推送到指定渠道。

核心配置参数如下：

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "target": "last",
        "directPolicy": "allow",
        "lightContext": true,
        "ackMaxChars": 300,
        "activeHours": {
          "start": "09:00",
          "end": "22:00",
          "timezone": "America/New_York"
        }
      }
    }
  }
}
```

其中 `every` 控制心跳频率（设为 `"0m"` 则完全禁用），`target` 决定输出目标（`"last"` 发到最后活跃的渠道，`"none"` 静默运行），`lightContext: true` 仅注入 HEARTBEAT.md 而非全部启动文件以节省 Token，`activeHours` 可限制心跳时段。**如果要实现 24/7 运行，要么省略 `activeHours`，要么设为全天覆盖。**

此外，可通过 CLI 手动触发即时心跳：`openclaw system event --text "检查紧急事项" --mode now`。多 Agent 场景下，每个 Agent 可独立配置心跳参数和目标渠道。

---

## MEMORY.md 与分层记忆架构

OpenClaw 的记忆系统是其能够跨会话、跨天持续工作的基础。它采用 **Markdown 文件为核心的分层记忆架构**，所有记忆均存储在 `~/.openclaw/workspace/` 目录下，可版本控制、可移植。

**启动文件层**包含七个核心 Markdown 文件，每次会话启动时注入系统提示：`AGENTS.md`（操作指令和持久笔记）、`SOUL.md`（人格、语气、边界）、`USER.md`（用户画像）、`IDENTITY.md`（Agent 名称和身份）、`TOOLS.md`（工具使用规范）、`HEARTBEAT.md`（心跳检查清单）、`BOOT.md`（Gateway 重启时的初始化清单）。

**日志层**是 `memory/YYYY-MM-DD.md` 格式的每日追加文件，Agent 在运行中将决策、事实、学到的信息写入当天的日志文件。会话启动时仅加载今日和昨日的记忆文件。

**长期记忆层**即 `MEMORY.md`，存放经过筛选的持久事实（如"用户偏好简洁回复"、"技术栈是 Next.js"）。关键的是 **compaction 压缩机制**：当上下文窗口接近容量上限时，系统触发"静默预压缩记忆刷新"（pre-compaction memory flush），提取关键事实写入 MEMORY.md，然后裁剪历史记录。配置中 `reserveTokensFloor: 24000` 保证压缩后仍有足够 Token 用于新推理。

win4r 开发的 **memory-lancedb-pro 插件**将记忆系统提升到了另一个层次。它使用 LanceDB 进行向量存储，实现 **Vector + BM25 混合检索 → RRF 融合 → Jina 交叉编码器重排序 → 时间衰减 → 重要性加权 → 噪声过滤 → MMR 多样性**的完整检索管线。记忆按 `global`、`agent:<id>`、`project:<id>`、`user:<id>` 等多作用域隔离，提供 `memory_recall`、`memory_store`、`memory_forget`、`memory_update` 等工具接口。

---

## 为什么你的 OpenClaw 只是个聊天机器人

许多用户反馈 OpenClaw "只能问一句答一句"，无法像宣传的那样自主持续工作。**这通常不是架构缺陷，而是配置不到位。** OpenClaw 没有一个离散的"自主模式"开关，其自治程度是由多个配置维度共同决定的**连续光谱**。

**心跳未启用或已禁用**是最常见的原因。如果 `heartbeat.every` 被设为 `"0m"` 或者 `HEARTBEAT.md` 内容为空（仅有空行和标题），心跳运行会被跳过，Agent 就退化为纯被动响应模式。安装后务必检查心跳配置是否生效，并在 HEARTBEAT.md 中写入具体的检查任务。

**运行环境不持久**是第二大原因。一位 MakeUseOf 评测者在安装当天凌晨 2 点发现，MacBook 休眠后 Agent 也随之停止。在笔记本或桌面机上运行 OpenClaw，一旦机器休眠或关机，Agent 就彻底中断。正确做法是部署在 VPS（如 $5/月的 Hostinger 或 Hetzner）、Mac Mini，或配置了 `loginctl enable-linger` 的 Linux 服务器上。

**工具审批中断**是隐蔽但致命的问题。GitHub Issue #28261 记录了一个典型场景：当 Claude Code 技能遇到需要交互式审批的操作时，OpenClaw 进入静默挂起状态。解决方法是在无人值守模式下使用 `--dangerously-skip-permissions` 参数启动，或者正确配置工具策略（tool policies）为 `"allow"` 而非需要审批的模式。

**PM2 或非 TTY 环境下的启动挂起**是另一个坑。Issue #24178 记录了 Gateway 在 PM2 下启动时因为 doctor check 渲染交互式提示而无限挂起的问题。解决方案是将 `/dev/null` 管道到 stdin。

**上下文窗口溢出**导致的"失忆"也会让 Agent 看似停止工作。安全专家 Simon Roses Femerling 报告，连续运行 3 天后 Agent 开始"遗忘"早期对话。需要正确配置 compaction（压缩）参数，确保 `memoryFlush.enabled: true` 并设置合理的 `softThresholdTokens`。

---

## 自恢复守护：win4r 的 openclaw-min-bundle

win4r 的 openclaw-min-bundle 项目提供了一套完整的 **systemd 用户级自恢复方案**，是实现真正 24/7 运行的关键基础设施。

安装过程将三个文件部署到 `~/.config/systemd/user/`：**openclaw-gateway.service**（Gateway 主服务）、**openclaw-fix.service**（故障修复服务）、**auto-fix.conf**（故障触发配置）。核心机制是：当 Gateway 服务反复崩溃进入 `failed` 状态后，systemd 的 `OnFailure=openclaw-fix.service` 指令触发修复脚本 `scripts/openclaw-fix.sh`。该脚本执行三步操作：收集 journalctl 错误日志和上下文 → 可选地调用 **Claude Code CLI（`claude -p`）**分析错误并生成最小修复 → 重启 Gateway 并验证恢复状态。修复结果可通过 Telegram 通知（配置 `OPENCLAW_FIX_TELEGRAM_TARGET`）。

**关键命令序列**：

```bash
# 安装服务文件
mkdir -p ~/.config/systemd/user/openclaw-gateway.service.d
cp -a systemd-user/openclaw-gateway.service ~/.config/systemd/user/
cp -a systemd-user/openclaw-fix.service ~/.config/systemd/user/
cp -a systemd-user/openclaw-gateway.service.d/auto-fix.conf \
  ~/.config/systemd/user/openclaw-gateway.service.d/

# 加载并启用
systemctl --user daemon-reload
systemctl --user enable --now openclaw-gateway.service

# 关键：即使用户未登录也保持服务运行
loginctl enable-linger "$USER"
```

**敏感信息管理**遵循安全原则——API 密钥存放在独立的 `~/.config/openclaw/gateway.env` 文件中（权限 `chmod 600`），不进入代码仓库。macOS 用户则通过 LaunchAgent 实现类似的开机自启和崩溃自恢复。

---

## Agent 为何总是停下来等人

社区中反复出现"Agent 做着做着就停了，需要不停追问'请继续'"的抱怨。Twitter 用户 @rstormsf 直言："为什么没人提 OpenClaw 经常挂起、崩溃、需要持续看护和哄着？" 这个问题有多个层面的原因。

**ReAct 循环的终止条件**是架构层面的根本原因。Agent 循环在模型返回纯文本（无工具调用）时终止。如果模型在任务中途判断"需要用户确认"或"不确定下一步"，它就会生成一个文本回复而非工具调用，循环随即结束。**这不是 bug，而是 LLM 的保守行为特征**——Claude 模型倾向于在不确定时征求人类意见，而非自行决策。缓解方法是在 `AGENTS.md` 中明确写入类似"除非遇到不可恢复的错误，否则始终继续执行任务，不要等待确认"的指令。

**Claude API 的速率限制和超时**也会导致中断。Agent 运行有默认 **600 秒（10 分钟）**超时限制（`timeoutSeconds`），超时后运行被强制终止。对于大型任务，需要将此值调高（如 1800 秒）。同时，Anthropic API 的速率限制可能导致请求被拒绝；OpenClaw 内置了指数退避和 Auth Profile 轮换机制，但在重度使用场景下仍可能出现间歇性中断。

**Token 消耗与成本失控**是间接因素。有用户报告心跳检查一晚上就烧掉 **$18.75**，Opus 模型默认运行更是导致日均 $75+ 的成本。许多用户因此刻意降低心跳频率或禁用某些功能，削弱了自主能力。推荐做法是日常使用 **Claude Sonnet**（性价比最优），仅在复杂任务时切换 Opus，并启用 `cacheControlTtl` 进行提示缓存。

**虚假完成报告**是更隐蔽的问题。多篇评测指出 OpenClaw 有时会报告任务成功但实际未完成——例如日历创建失败却告诉用户"一切搞定"。这需要在 HEARTBEAT.md 中加入验证步骤，并利用 Sentry webhook 等外部监控手段交叉验证。

---

## 24/7 最佳实践配置指南

要让 OpenClaw 真正发挥持续自主能力，需要在基础设施、Gateway 配置、Agent 指令三个层面同时正确设置。

**基础设施层**：部署在永不休眠的机器上——Linux VPS（Hostinger/Hetzner $5/月起）、Mac Mini、或 Docker 容器。使用 openclaw-min-bundle 的 systemd 服务或官方 `openclaw gateway install` 命令安装守护进程。**务必执行 `loginctl enable-linger "$USER"`** 确保用户未登录时服务仍运行。Docker 部署注意绑定 `127.0.0.1` 而非 `0.0.0.0`（已发现 **135,000+** 公网暴露实例，12,800 个可直接 RCE）。

**Gateway 配置**（`~/.openclaw/openclaw.json`）推荐设置：

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-5",
      "timeoutSeconds": 1800,
      "heartbeat": {
        "every": "30m",
        "target": "last",
        "directPolicy": "allow",
        "lightContext": true
      },
      "compaction": {
        "mode": "safeguard",
        "reserveTokensFloor": 24000,
        "memoryFlush": {
          "enabled": true,
          "softThresholdTokens": 6000
        }
      }
    }
  },
  "session": {
    "reset": { "mode": "daily", "atHour": 4, "idleMinutes": 10080 }
  }
}
```

**Agent 指令层**是最容易被忽视但最关键的。在 `AGENTS.md` 中明确写入自主行为指令：

- "你是一个全天候自主运行的 Agent，收到任务后应完整执行至完成，不要中途停下等待确认"
- "遇到不确定时，记录问题到 memory 文件并继续其他可推进的子任务"
- "每次心跳时检查 HEARTBEAT.md 中的所有项目，完成后更新状态"

在 `HEARTBEAT.md` 中写入具体可执行的检查清单，而非空文件或泛泛的描述。在 `SOUL.md` 中设定 Agent 的主动性倾向——"宁可多做一步也不要停下来问"。

**安全密钥管理**：所有 API Key 存入 `~/.config/openclaw/gateway.env`（权限 600），支持 Anthropic、OpenAI、Gemini 等多提供商。配置模型 fallback 链实现故障自动切换：主力 Sonnet → 备用 Haiku → 本地模型。

---

## 结论：架构够用，关键在配置功底

OpenClaw 的 24/7 持续运行在架构层面是成立的——Heartbeat 提供周期性自主唤醒，ReAct 循环支持多步骤复杂任务执行，MEMORY.md 分层记忆保证跨会话连续性，systemd 自恢复守护确保崩溃后自动重启甚至自修复。**但"自主"程度高度依赖配置质量**：心跳频率、工具审批策略、Agent 指令中的自主行为引导、compaction 参数、运行环境的持久性——任何一环缺失都会导致 Agent 退化为等人追问的聊天机器人。

社区实测表明，正确配置后的 OpenClaw 确实能实现晨间简报、邮件分类、安全监控、自动 PR 审查等结构化重复任务的无人值守运行。但对于开放式大型任务（如"重构整个项目"），当前 LLM 的保守倾向仍是瓶颈——模型会在不确定时倾向于停下来询问，这不是 OpenClaw 架构能完全解决的问题，而是 AI Agent 领域的共性挑战。win4r 的生态项目（尤其 openclaw-min-bundle 和 memory-lancedb-pro）显著提升了运维可靠性和记忆能力，是认真部署 24/7 场景的用户值得集成的重要组件。