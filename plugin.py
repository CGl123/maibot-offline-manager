"""下线管理插件入口"""

from maibot_sdk import MaiBotPlugin

from .command_handlers import OfflineCommandHandlersMixin
from .config_models import OfflineManagerConfig
from .core_mixin import OfflineCoreMixin
from .hook_handlers import OfflineHookHandlersMixin
from .tool_handlers import OfflineToolHandlersMixin


class OfflineManagerPlugin(
    OfflineHookHandlersMixin,
    OfflineCommandHandlersMixin,
    OfflineToolHandlersMixin,
    OfflineCoreMixin,
    MaiBotPlugin,
):
    """Planner 可主动调用 go_offline 工具进入下线状态"""

    config_model = OfflineManagerConfig

    def __init__(self) -> None:
        """初始化插件状态"""

        super().__init__()
        self._init_offline_state()

    async def on_load(self) -> None:
        """插件加载时恢复状态并输出提示"""

        self._restore_offline_state()
        if self._offline_until is not None:
            self.ctx.logger.info(
                f"下线管理: 当前处于下线状态，预计 {self._offline_until.strftime('%H:%M')} 上线"
            )
        else:
            self.ctx.logger.info("下线管理已加载，当前未处于下线状态")

    async def on_unload(self) -> None:
        """插件卸载时不做特殊处理"""

        pass

    async def on_config_update(
        self,
        scope: str,
        config_data: dict[str, object],
        version: str,
    ) -> None:
        """配置热更新回调"""

        del scope
        del config_data
        del version


def create_plugin() -> OfflineManagerPlugin:
    """创建插件实例"""

    return OfflineManagerPlugin()
