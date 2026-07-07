"""下线管理 Hook 处理器"""

from typing import Any

from maibot_sdk import HookHandler
from maibot_sdk.types import HookMode, HookOrder

from .core_mixin import REPLY_TOOL_NAMES


def _extract_hook_tool_name(raw_item: Any) -> str:
    if not isinstance(raw_item, dict):
        return ""
    raw_name = raw_item.get("name") or raw_item.get("tool_name")
    function_data = raw_item.get("function")
    if not raw_name and isinstance(function_data, dict):
        raw_name = function_data.get("name")
    return str(raw_name or "").strip()


class OfflineHookHandlersMixin:
    """声明下线期间的 Hook 入口"""

    @HookHandler(
        "chat.receive.before_process",
        name="offline_inbound_recorder",
        description="下线期间记录入站消息到 backlog，到点或 @ 唤醒时执行注入",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
    )
    async def handle_before_receive(
        self,
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        del kwargs

        if not self._enabled():
            return None
        if not self._is_offline():
            return None

        if self._wakeup_pending:
            self._record_backlog(message)
            await self._execute_wake_up()
            return None

        if self._try_wake_by_at(message):
            self._record_backlog(message)
            self._mark_for_wake_up(reason="@ 提及唤醒")
            await self._execute_wake_up()
            return None

        self._record_backlog(message)
        return None

    @HookHandler(
        "maisaka.planner.before_request",
        name="offline_planner_tool_stripper",
        description="下线期间移除 Planner 的回复类工具，保留学习相关管线",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_planner_before_request(
        self,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        if not self._enabled() or not self._is_offline():
            return None
        if not self.config.control.block_reply_tools:
            return None

        raw_tool_defs = kwargs.get("tool_definitions")
        if not isinstance(raw_tool_defs, list):
            return None

        filtered_tools = []
        for tool_def in raw_tool_defs:
            tool_name = _extract_hook_tool_name(tool_def)
            if tool_name not in REPLY_TOOL_NAMES:
                filtered_tools.append(tool_def)

        modified_kwargs = dict(kwargs)
        modified_kwargs["tool_definitions"] = filtered_tools
        return {"action": "continue", "modified_kwargs": modified_kwargs}
