"""下线管理核心逻辑"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from .state_storage import clear_offline_state, load_offline_state, save_offline_state

from src.common.data_models.message_component_data_model import MessageSequence, TextComponent
from src.maisaka.context.messages import SessionBackedMessage

REPLY_TOOL_NAMES = {"reply", "send_emoji", "send_image", "switch_chat", "fetch_history", "focus_send_emoji"}
MAX_INJECT_MESSAGES = 50
PLUGIN_ID = "maibot-offline-manager"


class OfflineCoreMixin:
    """为插件主体提供下线状态与唤醒逻辑"""

    _offline_until: datetime | None
    _offline_started_at: datetime | None
    _offline_reason: str
    _backlog: Dict[str, List[Dict[str, Any]]]
    _backlog_session_names: Dict[str, str]
    _wakeup_pending: bool

    def _init_offline_state(self) -> None:
        self._offline_until = None
        self._offline_started_at = None
        self._offline_reason = ""
        self._backlog = {}
        self._backlog_session_names = {}
        self._wakeup_pending = False

    def _enabled(self) -> bool:
        return self.config.plugin.enabled

    def _is_offline(self) -> bool:
        if not self._enabled():
            return False
        if self._offline_until is None:
            return False
        if self._wakeup_pending:
            return True
        if datetime.now() >= self._offline_until:
            self._wakeup_pending = True
        return True

    def _mark_for_wake_up(self, *, reason: str = "") -> None:
        self.ctx.logger.info(
            f"下线管理: 已标记唤醒，原因: {reason or '到点'}，积压聊天流 {len(self._backlog)} 个"
        )
        self._wakeup_pending = True

    def _go_offline(self, hours: int, reason: str = "") -> None:
        max_hours = self.config.control.max_offline_hours
        clamped_hours = max(1, min(hours, max_hours))
        self._offline_started_at = datetime.now()
        self._offline_until = self._offline_started_at + timedelta(hours=clamped_hours)
        self._offline_reason = reason or f"主动下线 {clamped_hours} 小时"
        self._backlog = {}
        self._backlog_session_names = {}
        self._wakeup_pending = False

        self._release_focus_if_held()
        save_offline_state(self._offline_until, self._offline_started_at, self._offline_reason)
        self.ctx.logger.info(
            f"下线管理: 已下线，预计 {self._offline_until.strftime('%H:%M')} 上线，原因: {self._offline_reason}"
        )

    async def _execute_wake_up(self) -> None:
        if not self._wakeup_pending:
            return

        self.ctx.logger.info(f"下线管理: 执行唤醒，积压内存聊天流 {len(self._backlog)} 个")
        try:
            from src.chat.heart_flow.heartflow_manager import heartflow_manager

            max_inject = getattr(self.config.control, "max_inject_messages", None) or MAX_INJECT_MESSAGES

            affected_session_ids: set[str] = set()
            for session_id, messages in list(self._backlog.items()):
                affected_session_ids.add(session_id)
                runtime = heartflow_manager.heartflow_chat_list.get(session_id)
                if runtime is None:
                    continue
                selected = messages[-max_inject:]
                await self._inject_backlog_and_trigger(runtime, selected, session_id)

            for session_id, runtime in list(heartflow_manager.heartflow_chat_list.items()):
                if session_id in affected_session_ids:
                    continue
                db_messages = self._query_db_messages_for_wakeup(session_id, max_inject)
                if not db_messages:
                    continue
                affected_session_ids.add(session_id)
                await self._inject_backlog_and_trigger(runtime, db_messages, session_id)

        except Exception as exc:
            self.ctx.logger.error(f"下线管理: 唤醒注入失败: {exc}")

        self._finish_wake_up()

    def _finish_wake_up(self) -> None:
        self._offline_until = None
        self._offline_started_at = None
        self._offline_reason = ""
        self._backlog = {}
        self._backlog_session_names = {}
        self._wakeup_pending = False
        clear_offline_state()

    @staticmethod
    def _release_focus_if_held() -> None:
        try:
            from src.maisaka.focus.manager import focus_mode_manager

            focused_ids = focus_mode_manager.get_focused_session_ids()
            for session_id in focused_ids:
                focus_mode_manager.release_focus_and_block_next_entry(str(session_id))
        except Exception:
            pass

    def _query_db_messages_for_wakeup(
        self,
        session_id: str,
        max_count: int,
    ) -> List[Dict[str, Any]]:
        if self._offline_started_at is None or self._offline_until is None:
            return []

        try:
            from sqlmodel import select

            from src.common.database.database import get_db_session
            from src.common.database.database_model import Messages

            end_time = min(datetime.now(), self._offline_until)
            with get_db_session(auto_commit=False) as session:
                rows = session.exec(
                    select(Messages)
                    .where(
                        Messages.session_id == session_id,
                        Messages.timestamp >= self._offline_started_at,
                        Messages.timestamp <= end_time,
                    )
                    .order_by(Messages.timestamp)
                    .limit(max_count)
                ).all()

            from src.common.data_models.mai_message_data_model import MaiMessage

            result: List[Dict[str, Any]] = []
            for row in rows:
                try:
                    msg = MaiMessage.from_db_instance(row)
                    result.append(self._session_message_to_dict(msg))
                except Exception:
                    continue
            return result
        except Exception:
            return []

    @staticmethod
    def _session_message_to_dict(msg: Any) -> Dict[str, Any]:
        from src.plugin_runtime.host.message_utils import PluginMessageUtils

        return PluginMessageUtils._session_message_to_dict(msg)

    async def _inject_backlog_and_trigger(
        self,
        runtime: Any,
        messages: List[Dict[str, Any]],
        session_id: str,
    ) -> None:
        from src.plugin_runtime.host.message_utils import PluginMessageUtils

        elapsed_hours = 0.0
        if self._offline_started_at is not None:
            elapsed_hours = (datetime.now() - self._offline_started_at).total_seconds() / 3600

        msg_count = len(messages) if messages else 0
        session_name = self._backlog_session_names.get(session_id) or self._extract_session_name(session_id, messages)
        wake_text = (
            f"[系统提示] 刚刚上线了，已离线约 {elapsed_hours:.1f} 小时。\n"
            f"以下是离线期间 {session_name} 错过的 {msg_count} 条消息，请像 switch_chat 一样浏览后自主决定是否回复："
        )
        wake_notice = SessionBackedMessage(
            raw_message=MessageSequence([TextComponent(wake_text)]),
            visible_text=wake_text,
            timestamp=datetime.now(),
            source_kind="system",
        )
        runtime._chat_history.append(wake_notice)

        session_message_list: list = []
        for message_dict in messages:
            try:
                session_msg = PluginMessageUtils._build_session_message_from_dict(message_dict)
            except Exception:
                continue
            session_message_list.append(session_msg)

        if session_message_list:
            history_messages = await runtime.build_session_messages_as_user_history(
                session_message_list,
                source_kind="user",
            )
            runtime._chat_history.extend(history_messages)

        self.ctx.logger.info(
            f"下线管理: 唤醒注入 {session_name}: {msg_count} 条消息 → Planner 触发"
        )

        await runtime.enqueue_proactive_task(
            plugin_id=PLUGIN_ID,
            intent=(
                f"下线后上线，离线约 {elapsed_hours:.1f} 小时，错过了 {msg_count} 条消息。"
                "请浏览上下文中的未读消息，回复或不回复，表达自然的回应态度。"
            ),
            reason=self._offline_reason or "到点上线",
        )

    def _extract_session_name(self, session_id: str, messages: List[Dict[str, Any]]) -> str:
        """从消息字典中提取会话展示名称"""

        if not messages:
            return session_id
        first = messages[0]
        message_info = first.get("message_info", {})
        if isinstance(message_info, dict):
            group_info = message_info.get("group_info")
            if isinstance(group_info, dict):
                group_name = str(group_info.get("group_name") or "").strip()
                if group_name:
                    return group_name
            user_info = message_info.get("user_info")
            if isinstance(user_info, dict):
                user_name = str(
                    user_info.get("user_nickname") or user_info.get("user_cardname") or ""
                ).strip()
                if user_name:
                    return f"{user_name} 的私聊"
        return session_id

    def _record_backlog(self, message: Dict[str, Any]) -> None:
        session_id = str(message.get("session_id") or "").strip()
        if not session_id:
            return

        if session_id not in self._backlog:
            self._backlog[session_id] = []
            message_info = message.get("message_info", {})
            group_name = ""
            user_name = ""
            if isinstance(message_info, dict):
                group_info = message_info.get("group_info")
                if isinstance(group_info, dict):
                    group_name = str(group_info.get("group_name") or "").strip()
                user_info = message_info.get("user_info")
                if isinstance(user_info, dict):
                    user_name = str(
                        user_info.get("user_nickname") or user_info.get("user_cardname") or ""
                    ).strip()
            if group_name:
                self._backlog_session_names[session_id] = group_name
            elif user_name:
                self._backlog_session_names[session_id] = f"{user_name} 的私聊"
            else:
                self._backlog_session_names[session_id] = session_id

        self._backlog[session_id].append(message)

    def _try_wake_by_at(self, message: Dict[str, Any]) -> bool:
        if not self.config.control.allow_at_wake:
            return False
        return bool(message.get("is_at")) or bool(message.get("is_mentioned"))

    def _restore_offline_state(self) -> None:
        offline_until, offline_started_at, reason = load_offline_state()
        if offline_until is not None:
            self._offline_until = offline_until
            self._offline_started_at = offline_started_at
            self._offline_reason = reason or "恢复未过期的下线状态"
            self._backlog = {}
            self._backlog_session_names = {}
            self._wakeup_pending = False
            self.ctx.logger.info(
                f"下线管理: 已恢复下线状态，预计 {offline_until.strftime('%H:%M')} 上线"
            )
