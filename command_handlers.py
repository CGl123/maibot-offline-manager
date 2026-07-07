"""下线管理命令处理器"""

from datetime import datetime
from typing import Any

from maibot_sdk import Command


class OfflineCommandHandlersMixin:
    """声明管理员命令入口"""

    @Command(
        "offline_force",
        description="管理员强制触发下线",
        pattern=r"^/offline_force(\s+\d+)?(\s+.*)?$",
    )
    async def handle_offline_force(
        self,
        stream_id: str = "",
        processed_plain_text: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """管理员强制下线"""

        del kwargs

        if not self._enabled():
            await self.ctx.send.text("[下线管理] 插件未启用", stream_id)
            return True, "[下线管理] 插件未启用", False

        if self._is_offline():
            remaining = ""
            if self._offline_until is not None:
                minutes_left = max(
                    0,
                    (self._offline_until - datetime.now()).total_seconds() / 60,
                )
                remaining = f"（还有约 {minutes_left:.0f} 分钟上线）"
            await self.ctx.send.text(f"[下线管理] 当前已在下线状态{remaining}", stream_id)
            return True, f"已在下线状态{remaining}", False

        parts = processed_plain_text.strip().split(maxsplit=1)
        hours = 4
        reason = "管理员强制下线"
        if len(parts) >= 2:
            tail = parts[1]
            try:
                hours = int(tail.split()[0])
                reason = " ".join(tail.split()[1:]) or reason
            except ValueError:
                hours = 4
                reason = tail

        self._go_offline(hours, reason)
        result_text = (
            f"[下线管理] 已强制下线，预计 {self._offline_until.strftime('%H:%M')} 上线（{hours} 小时）"
            if self._offline_until
            else "[下线管理] 已强制下线"
        )
        await self.ctx.send.text(result_text, stream_id)
        return True, "已强制下线", True

    @Command(
        "offline_wake",
        description="管理员手动唤醒",
        pattern=r"^/offline_wake$",
    )
    async def handle_offline_wake(
        self,
        stream_id: str = "",
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        """管理员手动唤醒"""

        del kwargs

        if not self._enabled():
            await self.ctx.send.text("[下线管理] 插件未启用", stream_id)
            return True, "[下线管理] 插件未启用", False

        if not self._is_offline():
            await self.ctx.send.text("[下线管理] 当前未处于下线状态", stream_id)
            return True, "未处于下线状态", False

        self._mark_for_wake_up(reason="管理员手动唤醒")
        await self._execute_wake_up()
        await self.ctx.send.text("[下线管理] 已手动唤醒，正在注入离线期间的积压消息...", stream_id)
        return True, "已手动唤醒", True
