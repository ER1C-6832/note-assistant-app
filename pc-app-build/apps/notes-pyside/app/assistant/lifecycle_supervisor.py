"""Last-resort lifecycle watchdog for Assistant Runtime sessions.

Normal turn completion remains owned by the transport, reducer, playback, and MCP
components.  This supervisor only intervenes when a matching generation/turn
remains non-terminal beyond a bounded deadline.  Recovery uses a generation
change (reconnect), so stale callbacks cannot revive the abandoned turn.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from .state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantPhase,
    AssistantState,
    StreamingConversationState,
)

_LOGGER = logging.getLogger(__name__)

TEXT_TURN_TIMEOUT_SECONDS = 40.0
VOICE_TURN_TIMEOUT_SECONDS = 60.0
STREAMING_TURN_TIMEOUT_SECONDS = 35.0
ORPHAN_BUSY_TIMEOUT_SECONDS = 8.0
LOCAL_CONFIRMATION_GRACE_SECONDS = 4.0
LOCAL_CONFIRMATION_PLAYBACK_GRACE_SECONDS = 12.0

_TERMINAL_LOCAL_STATUSES = frozenset(
    {
        "success",
        "partial_success",
        "rejected",
        "failed",
        "execution_failed",
        "consumed",
        "timeout",
    }
)
_BUSY_PHASES = frozenset(
    {
        AssistantPhase.THINKING,
        AssistantPhase.UPLOADING_AUDIO,
        AssistantPhase.SPEAKING,
    }
)
_BUSY_STREAMING_STATES = frozenset(
    {
        StreamingConversationState.SUBMITTING_TURN,
        StreamingConversationState.THINKING,
        StreamingConversationState.SPEAKING,
        StreamingConversationState.STOPPING,
        StreamingConversationState.RECOVERING,
    }
)


class LifecycleController(Protocol):
    @property
    def state(self) -> AssistantState: ...

    def subscribe(self, listener): ...

    async def reconnect(
        self,
        *,
        reason: str = "manual_reconnect",
        message: str | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _WatchSpec:
    key: tuple[object, ...]
    timeout_seconds: float
    reason: str
    message: str


class SessionLifecycleSupervisor:
    """Verify that every active conversation generation reaches a terminal state."""

    def __init__(self, controller: LifecycleController) -> None:
        self._controller = controller
        self._closed = False
        self._watch_task: asyncio.Task[None] | None = None
        self._local_grace_task: asyncio.Task[None] | None = None
        self._watch_key: tuple[object, ...] | None = None
        self._recovering = False
        self._recovery_count = 0
        self._last_recovery_reason: str | None = None
        self._unsubscribe = controller.subscribe(self._on_state_changed)

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    @property
    def last_recovery_reason(self) -> str | None:
        return self._last_recovery_reason

    @property
    def watchdog_running(self) -> bool:
        return self._watch_task is not None and not self._watch_task.done()

    def _on_state_changed(self, state: AssistantState) -> None:
        if self._closed:
            return
        spec = _watch_spec(state)
        if spec is None:
            self._cancel_watch_nowait()
            return
        if spec.key == self._watch_key and self.watchdog_running:
            return
        self._cancel_watch_nowait()
        self._watch_key = spec.key
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._watch_task = loop.create_task(
            self._wait_and_recover(spec),
            name=f"assistant-lifecycle-watchdog-{spec.reason}",
        )

    async def local_confirmation_finished(
        self,
        action: str,
        confirmation_id: str,
        status: str,
        message: str,
    ) -> None:
        """Give the normal voice/TTS completion path a short grace period.

        A local confirmation is outside the server's MCP request/response turn.
        Therefore it must not directly mutate the AssistantState.  It only asks
        the watchdog to verify that the already-finished voice interaction really
        returned to a terminal state.
        """

        del confirmation_id
        if self._closed or status not in _TERMINAL_LOCAL_STATUSES:
            return
        task = self._local_grace_task
        if task is not None and not task.done():
            task.cancel()
        self._local_grace_task = asyncio.create_task(
            self._verify_after_local_action(action, status, message),
            name=f"assistant-local-confirmation-grace-{action}",
        )

    async def _verify_after_local_action(
        self,
        action: str,
        status: str,
        message: str,
    ) -> None:
        try:
            await asyncio.sleep(LOCAL_CONFIRMATION_GRACE_SECONDS)
            state = self._controller.state
            if state.audio.status is AssistantAudioStatus.PLAYING:
                await asyncio.sleep(LOCAL_CONFIRMATION_PLAYBACK_GRACE_SECONDS)
                state = self._controller.state
            if not _state_is_stuck_after_local_action(state):
                return
            await self._recover(
                reason="local_confirmation_lifecycle_stuck",
                message=(
                    f"本地{action}已返回 {status}，但语音回合未正常结束；"
                    "正在自动恢复连接"
                ),
                details=message,
            )
        except asyncio.CancelledError:
            raise

    async def _wait_and_recover(self, spec: _WatchSpec) -> None:
        try:
            await asyncio.sleep(spec.timeout_seconds)
            if self._closed:
                return
            current = _watch_spec(self._controller.state)
            if current is None or current.key != spec.key:
                return
            await self._recover(spec.reason, spec.message)
        except asyncio.CancelledError:
            raise
        finally:
            if self._watch_task is asyncio.current_task():
                self._watch_task = None
                self._watch_key = None

    async def _recover(
        self,
        reason: str,
        message: str,
        *,
        details: str | None = None,
    ) -> None:
        if self._closed or self._recovering:
            return
        state = self._controller.state
        if (
            not state.enabled
            or state.connection.status
            not in {
                AssistantConnectionStatus.CONNECTED,
                AssistantConnectionStatus.CONNECTING,
            }
        ):
            return
        self._recovering = True
        self._recovery_count += 1
        self._last_recovery_reason = reason
        _LOGGER.error(
            "Assistant lifecycle watchdog recovery: reason=%s phase=%s details=%s",
            reason,
            state.phase.value,
            details or "",
        )
        try:
            await self._controller.reconnect(reason=reason, message=message)
        finally:
            self._recovering = False

    def _cancel_watch_nowait(self) -> None:
        task = self._watch_task
        self._watch_task = None
        self._watch_key = None
        if task is not None and not task.done():
            task.cancel()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._unsubscribe()
        tasks = tuple(
            task
            for task in (self._watch_task, self._local_grace_task)
            if task is not None and not task.done()
        )
        self._watch_task = None
        self._local_grace_task = None
        self._watch_key = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def _watch_spec(state: AssistantState) -> _WatchSpec | None:
    if (
        not state.enabled
        or state.connection.status is not AssistantConnectionStatus.CONNECTED
        or state.phase in {
            AssistantPhase.DISABLED,
            AssistantPhase.IDLE,
            AssistantPhase.CONNECTING,
            AssistantPhase.RECONNECTING,
            AssistantPhase.ERROR,
        }
    ):
        return None

    conversation = state.conversation
    generation = state.connection.connection_generation
    progress = (
        state.phase.value,
        state.protocol.last_protocol_event,
        state.token_usage.turn_id,
        state.token_usage.status,
        state.mcp.last_request_id,
        state.mcp.last_tool_status,
    )

    if conversation.streaming_session_active and (
        conversation.streaming_state in _BUSY_STREAMING_STATES
    ):
        token = conversation.active_streaming_turn_token
        return _WatchSpec(
            key=("streaming", generation, conversation.streaming_generation, token, progress),
            timeout_seconds=STREAMING_TURN_TIMEOUT_SECONDS,
            reason="streaming_lifecycle_timeout",
            message="连续对话回合长时间未结束，正在自动恢复连接",
        )

    if conversation.active_text_turn_token is not None:
        return _WatchSpec(
            key=("text", generation, conversation.active_text_turn_token, progress),
            timeout_seconds=TEXT_TURN_TIMEOUT_SECONDS,
            reason="text_lifecycle_timeout",
            message="文本回合长时间未结束，正在自动恢复连接",
        )

    if conversation.active_voice_turn_token is not None:
        if (
            state.audio.status is AssistantAudioStatus.RECORDING
            and state.phase is AssistantPhase.LISTENING
        ):
            # Holding PTT or waiting for VAD speech is user-controlled, not a
            # response lifecycle timeout.
            return None
        return _WatchSpec(
            key=("voice", generation, conversation.active_voice_turn_token, progress),
            timeout_seconds=VOICE_TURN_TIMEOUT_SECONDS,
            reason="voice_lifecycle_timeout",
            message="语音回合长时间未结束，正在自动恢复连接",
        )

    if state.phase in _BUSY_PHASES:
        return _WatchSpec(
            key=("orphan", generation, progress),
            timeout_seconds=ORPHAN_BUSY_TIMEOUT_SECONDS,
            reason="orphan_busy_state",
            message="助手状态未正常结束，正在自动恢复连接",
        )
    return None


def _state_is_stuck_after_local_action(state: AssistantState) -> bool:
    if state.connection.status is not AssistantConnectionStatus.CONNECTED:
        return False
    return bool(
        state.phase in {
            AssistantPhase.THINKING,
            AssistantPhase.UPLOADING_AUDIO,
            AssistantPhase.SPEAKING,
        }
        or state.audio.status is AssistantAudioStatus.PLAYING
        or state.conversation.active_text_turn_token is not None
        or state.conversation.active_voice_turn_token is not None
        or (
            state.conversation.streaming_session_active
            and state.conversation.streaming_state in _BUSY_STREAMING_STATES
        )
    )


__all__ = [
    "LOCAL_CONFIRMATION_GRACE_SECONDS",
    "LOCAL_CONFIRMATION_PLAYBACK_GRACE_SECONDS",
    "ORPHAN_BUSY_TIMEOUT_SECONDS",
    "SessionLifecycleSupervisor",
    "STREAMING_TURN_TIMEOUT_SECONDS",
    "TEXT_TURN_TIMEOUT_SECONDS",
    "VOICE_TURN_TIMEOUT_SECONDS",
]
