"""下线管理插件配置模型"""

from typing import List

from maibot_sdk import Field, PluginConfigBase


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置"""

    __ui_label__ = "插件"
    __ui_icon__ = "power"
    __ui_order__ = 0

    enabled: bool = Field(default=True, description="是否启用下线管理")


class OfflineControlConfig(PluginConfigBase):
    """下线行为控制"""

    __ui_label__ = "行为"
    __ui_icon__ = "settings"
    __ui_order__ = 1

    max_offline_hours: int = Field(default=24, description="Planner 单次下线最大时长（小时）")
    max_inject_messages: int = Field(default=50, description="唤醒时每个聊天流最多注入的未读消息条数")
    allow_at_wake: bool = Field(default=True, description="下线期间被 @ 提及时是否自动唤醒")
    block_reply_tools: bool = Field(
        default=True,
        description="下线期间是否移除 Planner 的回复类工具（reply/send_emoji/send_image/switch_chat）",
    )
    persist_offline_state: bool = Field(default=True, description="重启后恢复未过期的下线状态")
    admin_user_ids: List[str] = Field(
        default_factory=list,
        description="允许使用 /offline_force 和 /offline_wake 命令的用户 ID；留空时不限制",
    )


class OfflineManagerConfig(PluginConfigBase):
    """下线管理完整配置"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    control: OfflineControlConfig = Field(default_factory=OfflineControlConfig)
