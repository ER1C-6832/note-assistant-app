"""Controller/effect-runner compatibility layer activating Gate 4.2 playback."""

from __future__ import annotations

from ..controller import AssistantController as BaseAssistantController
from ..controller import EffectRunner
from ..effects import (
    CloseTransport,
    SetVoiceInteractionMode,
    StopPlayback,
    StopStreamingConversation,
)
from .coordinator import PlaybackCoordinator
from .runtime_effects import CancelActualPlayback, StartActualPlayback
from .runtime_state_machine import PlaybackConversationStateMachine


class PlaybackEffectRunner(EffectRunner):
    def __init__(self, *, playback_coordinator: PlaybackCoordinator, **kwargs) -> None:
        super().__init__(**kwargs)
        self._playback_coordinator = playback_coordinator

    @property
    def playback_task_running(self) -> bool:
        return self._playback_coordinator.task_running

    @property
    def playback_output_active(self) -> bool:
        return self._playback_coordinator.output_running

    @property
    def playback_pcm_buffered_bytes(self) -> int:
        return self._playback_coordinator.pcm_buffered_bytes

    @property
    def playback_last_summary(self):
        return self._playback_coordinator.last_summary

    @property
    def playback_latency_sample(self):
        return self._playback_coordinator.last_latency_sample

    @property
    def playback_output_plan(self):
        return self._playback_coordinator.output_plan

    async def execute(self, effect) -> None:
        if isinstance(effect, StopStreamingConversation):
            await self._playback_coordinator.cancel(effect.reason)
        elif isinstance(effect, CloseTransport):
            await self._playback_coordinator.cancel(effect.reason)
        elif isinstance(effect, SetVoiceInteractionMode):
            await self._playback_coordinator.cancel("voice_mode_changed")
        elif isinstance(effect, StopPlayback):
            await self._playback_coordinator.cancel(
                effect.reason,
                playback_generation=effect.generation,
            )
            return
        if isinstance(effect, StartActualPlayback):
            await self._playback_coordinator.start_playback(
                connection_generation=effect.connection_generation,
                stream_sequence=effect.stream_sequence,
                playback_generation=effect.playback_generation,
            )
            return
        if isinstance(effect, CancelActualPlayback):
            await self._playback_coordinator.cancel(
                effect.reason,
                playback_generation=effect.playback_generation,
            )
            return
        await super().execute(effect)

    async def cancel_runtime_effects(self, reason: str) -> None:
        await self._playback_coordinator.cancel(reason)
        await super().cancel_runtime_effects(reason)

    async def shutdown(self) -> None:
        await self._playback_coordinator.close()
        await super().shutdown()


class AssistantController(BaseAssistantController):
    """Drop-in controller that installs the playback-aware reducer/effect runner."""

    def __init__(
        self,
        *,
        transport,
        state_machine=None,
        clock=None,
        initial_state=None,
        playback_coordinator: PlaybackCoordinator | None = None,
        identity_manager=None,
        fake_activation_client=None,
        real_activation_client=None,
        preferences_store=None,
        audio_engine=None,
        microphone_coordinator=None,
    ) -> None:
        state_machine = state_machine or PlaybackConversationStateMachine()
        super().__init__(
            transport=transport,
            state_machine=state_machine,
            clock=clock,
            initial_state=initial_state,
            identity_manager=identity_manager,
            fake_activation_client=fake_activation_client,
            real_activation_client=real_activation_client,
            preferences_store=preferences_store,
            audio_engine=audio_engine,
            microphone_coordinator=microphone_coordinator,
        )
        coordinator = playback_coordinator or _coordinator_from_transport(transport)
        self._playback_coordinator = coordinator
        if coordinator is not None:
            coordinator.bind_runtime_state_provider(lambda: self._state)
            self._effect_runner = PlaybackEffectRunner(
                transport=transport,
                event_sink=self._emit_adapter_event,
                clock=self._clock,
                identity_manager=identity_manager,
                fake_activation_client=fake_activation_client,
                real_activation_client=real_activation_client,
                preferences_store=preferences_store,
                audio_engine=audio_engine,
                microphone_coordinator=microphone_coordinator,
                playback_coordinator=coordinator,
            )

    @property
    def playback_task_running(self) -> bool:
        runner = self._effect_runner
        return bool(getattr(runner, "playback_task_running", False))

    @property
    def playback_output_active(self) -> bool:
        runner = self._effect_runner
        return bool(getattr(runner, "playback_output_active", False))

    @property
    def playback_pcm_buffered_bytes(self) -> int:
        runner = self._effect_runner
        return int(getattr(runner, "playback_pcm_buffered_bytes", 0))

    @property
    def playback_last_summary(self):
        return getattr(self._effect_runner, "playback_last_summary", None)

    @property
    def playback_latency_sample(self):
        return getattr(self._effect_runner, "playback_latency_sample", {})

    @property
    def playback_output_plan(self):
        return getattr(self._effect_runner, "playback_output_plan", None)


def _coordinator_from_transport(transport) -> PlaybackCoordinator | None:
    direct = getattr(transport, "playback_coordinator", None)
    if isinstance(direct, PlaybackCoordinator):
        return direct
    real = getattr(transport, "_real_transport", None)
    nested = getattr(real, "playback_coordinator", None)
    return nested if isinstance(nested, PlaybackCoordinator) else None


ConversationStateMachine = PlaybackConversationStateMachine
