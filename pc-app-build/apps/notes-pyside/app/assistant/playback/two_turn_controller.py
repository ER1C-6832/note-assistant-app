"""Gate 4.3 controller compatibility layer for deterministic auto-next capture."""

from __future__ import annotations

from ..effects import AssistantEffect, StartStreamingConversation
from .runtime_controller import AssistantController as PlaybackAssistantController
from .runtime_events import AcousticBargeInConfirmed
from .two_turn_state_machine import TwoTurnConversationStateMachine


class AssistantController(PlaybackAssistantController):
    """Execute auto-next capture admission in event order and exactly once."""

    AUTO_NEXT_LEDGER_LIMIT = 256

    def __init__(
        self,
        *,
        transport,
        state_machine=None,
        clock=None,
        initial_state=None,
        playback_coordinator=None,
        identity_manager=None,
        fake_activation_client=None,
        real_activation_client=None,
        preferences_store=None,
        audio_engine=None,
        microphone_coordinator=None,
        runtime_log_path=None,
    ) -> None:
        super().__init__(
            transport=transport,
            state_machine=state_machine or TwoTurnConversationStateMachine(),
            clock=clock,
            initial_state=initial_state,
            playback_coordinator=playback_coordinator,
            identity_manager=identity_manager,
            fake_activation_client=fake_activation_client,
            real_activation_client=real_activation_client,
            preferences_store=preferences_store,
            audio_engine=audio_engine,
            microphone_coordinator=microphone_coordinator,
            runtime_log_path=runtime_log_path,
        )
        self._auto_next_turn_keys: dict[tuple[int, int, int], None] = {}
        self._auto_next_turn_request_count = 0
        self._auto_next_turn_started_count = 0
        self._auto_next_turn_suppressed_count = 0
        self._auto_next_turn_last_latency_ms: float | None = None

    @property
    def auto_next_turn_request_count(self) -> int:
        return self._auto_next_turn_request_count

    @property
    def auto_next_turn_started_count(self) -> int:
        return self._auto_next_turn_started_count

    @property
    def auto_next_turn_suppressed_count(self) -> int:
        return self._auto_next_turn_suppressed_count

    @property
    def auto_next_turn_last_latency_ms(self) -> float | None:
        return self._auto_next_turn_last_latency_ms

    async def confirm_acoustic_barge_in(
        self,
        *,
        playback_generation: int,
        monitor_generation: int,
        next_capture_generation: int,
    ) -> None:
        state = self.state
        await self._submit_command(
            AcousticBargeInConfirmed(
                at_ns=self._clock.now_ns(),
                connection_generation=state.connection.connection_generation,
                streaming_generation=state.conversation.streaming_generation,
                playback_generation=playback_generation,
                monitor_generation=monitor_generation,
                next_capture_generation=next_capture_generation,
            )
        )

    async def _apply_effects(self, effects: tuple[AssistantEffect, ...]) -> None:
        ordinary: list[AssistantEffect] = []
        for effect in effects:
            if self._is_auto_next_effect(effect):
                if ordinary:
                    await super()._apply_effects(tuple(ordinary))
                    ordinary.clear()
                await self._execute_auto_next_effect(effect)
            else:
                ordinary.append(effect)
        if ordinary:
            await super()._apply_effects(tuple(ordinary))

    async def _execute_auto_next_effect(self, effect: StartStreamingConversation) -> None:
        key = (
            effect.streaming_generation,
            effect.capture_generation,
            effect.turn_token,
        )
        if key in self._auto_next_turn_keys:
            self._auto_next_turn_suppressed_count += 1
            return
        self._auto_next_turn_keys[key] = None
        if len(self._auto_next_turn_keys) > self.AUTO_NEXT_LEDGER_LIMIT:
            self._auto_next_turn_keys.pop(next(iter(self._auto_next_turn_keys)))

        self._auto_next_turn_request_count += 1
        await self._execute_effect(effect)
        finished_at_ns = self._clock.now_ns()
        self._auto_next_turn_last_latency_ms = max(
            0.0,
            (finished_at_ns - effect.requested_at_ns) / 1_000_000,
        )
        if self.audio_capture_active:
            self._auto_next_turn_started_count += 1

    @staticmethod
    def _is_auto_next_effect(effect: AssistantEffect) -> bool:
        return isinstance(effect, StartStreamingConversation) and effect.turn_index > 1


ConversationStateMachine = TwoTurnConversationStateMachine
