# maibot-offline-manager

Planner 可调用 `go_offline` 工具主动下线，离线期间消息正常入库、学习管线继续运行，仅移除 Planner 的回复类工具。@ 提及可选择唤醒，管理员可通过 `/offline_force` 和 `/offline_wake` 控制。

## 工作原理

```
Planner 调用 go_offline(hours=4)
  → offline_until = now + 4h
  → 释放焦点槽（防 focus 死锁）
  → 记日志，持久化

离线中
  → 每条消息记到 backlog (内存)
  → 消息正常流入学习管线（表达学习、行为学习、黑话学习、A_Memorix）
  → Planner 触发时回复类工具被摘除（reply/send_emoji/send_image/switch_chat）
  → 保留 wait/no_action 等非发送工具

唤醒
  → 到点 / @提及 / 管理员命令
  → backlog 转换为 user history context 注入 runtime._chat_history
  → enqueue_proactive_task() 触发 Planner
  → Planner 带完整离线上下文决定是否回复

重启不丢消息
  → 持久化 offline_until / offline_started_at 到 JSON
  → 唤醒时若 backlog 为空，从 mai_messages 表按时间范围补取
```

## Tool

### `go_offline`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `hours` | int | ✓ | 下线时长（1-24） |
| `reason` | str | ✗ | 下线原因（选填，记日志用） |

适合在深夜/凌晨不便回复时调用，替代反复 `wait` 或装死。

## Commands

| 命令 | 说明 |
|------|------|
| `/offline_force [hours] [reason]` | 管理员强制下线 |
| `/offline_wake` | 管理员强制上线 |

## 配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `plugin.enabled` | `true` | 是否启用 |
| `control.max_offline_hours` | `24` | Planner 单次最大下线时长 |
| `control.max_inject_messages` | `50` | 唤醒时每个聊天流最多注入的消息条数 |
| `control.allow_at_wake` | `true` | 允许 @ 唤醒 |
| `control.block_reply_tools` | `true` | 下线期间移除回复工具 |
| `control.persist_offline_state` | `true` | 持久化下线状态（重启恢复） |
| `control.admin_user_ids` | `[]` | 允许使用管理命令的用户（空则不限制） |

## 参考

本插件参考 [goodnight_sleep_manager](https://github.com/RaTaiHok/goodnight_sleep_manager) 编写。
