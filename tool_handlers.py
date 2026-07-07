"""下线管理工具处理器"""

from typing import Any

from maibot_sdk import Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType


class OfflineToolHandlersMixin:
    """声明 Planner 可调用的下线工具"""

    @Tool(
        "go_offline",
        description=        "主动下线一段时间，离线期间不会回应用户消息，但消息正常入库、学习管线继续运行。适合在深夜/凌晨不便回复时调用，替代反复 wait 或装死。@ 提及可唤醒（如已启用）。",
        parameters=[
            ToolParameterInfo(
                name="hours",
                param_type=ToolParamType.INTEGER,
                description="下线时长（小时，1-24）",
                required=True,
            ),
            ToolParameterInfo(
                name="reason",
                param_type=ToolParamType.STRING,
                description="下线原因（可选，会记录到日志）",
                required=False,
            ),
        ],
    )
    async def handle_go_offline(
        self,
        hours: int = 4,
        reason: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Planner 调用下线工具"""

        if not self._enabled():
            return {"success": False, "content": "下线管理插件未启用"}

        if self._is_offline():
            return {
                "success": False,
                "content": f"当前已在下线状态，预计 {self._offline_until.strftime('%H:%M')} 上线",
            }

        clamped_hours = max(1, min(hours, self.config.control.max_offline_hours))
        self._go_offline(clamped_hours, reason)

        return {
            "success": True,
            "content": f"已下线，预计 {self._offline_until.strftime('%H:%M')} 上线（{clamped_hours} 小时）",
        }
