"""Single-writer AssistantController skeleton and effect runner."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from .effects import (
    AssistantEffect,
    CancelRuntimeEffects,
    CloseTransport,
    OpenTransport,
    SendText,
)
from .events import (
    AbortRequested,
    AssistantEvent,
    AudioFailureSimulationRequested,
    ConnectRequested,
    ConnectionClosedSimulationRequested,
    ConnectionFailureSimulationRequested,
    DisableRequested,
    DisconnectRequested,
    EffectExecutionFailed,
    EnableRequested,
    EnsureIdentityRequested,
    FakeActivationRequested,
    IncomingToolCallSimulationRequested,
    PushToTalkStartRequested,
    PushToTalkStopRequested,
    RealActivationRequested,
    ReconnectRequested,
    ResetIdentityRequested,
    ShutdownRequested,
    StreamingBargeInRequested,
    StreamingConversationStartRequested,
    StreamingConversationStopRequested,
    SystemAudioInterrupted,
    SystemAudioRecovered,
    TextSubmitted,
    ToolsListSimulationRequested,
    UseFakeRuntimeRequested,
    UseRealRuntimeRequested,
    VoiceInteractionModeRequested,
)
from .state import AssistantEntrySource, AssistantState, VoiceInteractionMode
from .state_machine import ConversationStateMachine

EventSink = Callable[[AssistantEvent], Awaitable[None]]
StateListener = Callable[[AssistantState], None]


class RuntimeClock(Protocol):
    def now_ns(self) -> int: ...


class AssistantTransport(Protocol):
    async def open(self, generation: int, event_sink: EventSink) -> None: ...

    async def send_text(
        self,
        generation: int,
        text: str,
        event_sink: EventSink,
    ) -> None: ...

    async def close(
        self,
        generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None: ...


class SystemRuntimeClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


class ControllerClosedError(RuntimeError):
    """Raised when a command is submitted after shutdown begins."""


@dataclass(slots=True)
class _QueuedEvent:
    event: AssistantEvent
    processed: asyncio.Future[None] | None = None


class EffectRunner:
    """Execute effect descriptions against adapters and emit typed result events."""

    def __init__(self, transport: AssistantTransport, event_sink: EventSink) -> None:
        self._transport = transport
        self._event_sink = event_sink

    async def execute(self, effect: AssistantEffect) -> None:
        if isinstance(effect, OpenTransport):
            await self._transport.open(effect.generation, self._event_sink)
            return
        if isinstance(effect, CloseTransport):
            await self._transport.close(effect.generation, effect.reason, self._event_sink)
            return
        if isinstance(effect, SendText):
            await self._transport.send_text(
                effect.generation,
                effect.text,
                self._event_sink,
            )
            return
        if isinstance(effect, CancelRuntimeEffects):
            return
        raise NotImplementedError(f"effect is not active in Gate 2.1: {type(effect).__name__}")


class AssistantController:
    """Public Runtime facade backed by one bounded event queue and one event pump."""

    EVENT_QUEUE_CAPACITY = 256

    def __init__(
        self,
        *,
        transport: AssistantTransport,
        state_machine: ConversationStateMachine | None = None,
        clock: RuntimeClock | None = None,
        initial_state: AssistantState | None = None,
    ) -> None:
        self._clock = clock or SystemRuntimeClock()
        self._state_machine = state_machine or ConversationStateMachine()
        self._state = initial_state or AssistantState.disabled(now_ns=self._clock.now_ns())
        self._state.validate()

        self._queue: asyncio.Queue[_QueuedEvent] = asyncio.Queue(maxsize=self.EVENT_QUEUE_CAPACITY)
        self._effect_runner = EffectRunner(transport, self._emit_adapter_event)
        self._effect_tasks: set[asyncio.Task[None]] = set()
        self._listeners: set[StateListener] = set()
        self._state_condition = asyncio.Condition()
        self._pump_task: asyncio.Task[None] | None = None
        self._accepting_commands = True
        self._shutdown_started = False
        self._closed = False

    @property
    def state(self) -> AssistantState:
        return self._state

    @property
    def event_queue_capacity(self) -> int:
        return self._queue.maxsize

    @property
    def pending_effect_count(self) -> int:
        return len(self._effect_tasks)

    @property
    def event_pump_running(self) -> bool:
        return self._pump_task is not None and not self._pump_task.done()

    @property
    def closed(self) -> bool:
        return self._closed

    async def start(self) -> None:
        if self._closed:
            raise ControllerClosedError("AssistantController is already closed")
        if self.event_pump_running:
            return
        self._pump_task = asyncio.create_task(
            self._event_pump(),
            name="assistant-event-pump",
        )

    def subscribe(self, listener: StateListener) -> Callable[[], None]:
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    async def wait_for_state(
        self,
        predicate: Callable[[AssistantState], bool],
        *,
        timeout_seconds: float = 2.0,
    ) -> AssistantState:
        async def wait_loop() -> AssistantState:
            while not predicate(self._state):
                async with self._state_condition:
                    if predicate(self._state):
                        break
                    await self._state_condition.wait()
            return self._state

        return await asyncio.wait_for(wait_loop(), timeout=timeout_seconds)

    async def enable_assistant(self) -> None:
        await self._submit_command(EnableRequested(at_ns=self._clock.now_ns()))

    async def disable_assistant(self) -> None:
        await self._submit_command(DisableRequested(at_ns=self._clock.now_ns()))

    async def use_fake_runtime(self) -> None:
        await self._submit_command(UseFakeRuntimeRequested(at_ns=self._clock.now_ns()))

    async def use_real_runtime(self) -> None:
        await self._submit_command(UseRealRuntimeRequested(at_ns=self._clock.now_ns()))

    async def connect(self) -> None:
        await self._submit_command(ConnectRequested(at_ns=self._clock.now_ns()))

    async def reconnect(self) -> None:
        await self._submit_command(ReconnectRequested(at_ns=self._clock.now_ns()))

    async def disconnect(self, reason: str = "user_disconnect") -> None:
        await self._submit_command(DisconnectRequested(at_ns=self._clock.now_ns(), reason=reason))

    async def send_text(self, text: str) -> None:
        await self._submit_command(TextSubmitted(at_ns=self._clock.now_ns(), text=text))

    async def set_voice_interaction_mode(self, mode: VoiceInteractionMode) -> None:
        await self._submit_command(
            VoiceInteractionModeRequested(at_ns=self._clock.now_ns(), mode=mode)
        )

    async def set_streaming_barge_in_enabled(self, enabled: bool) -> None:
        await self._submit_command(
            StreamingBargeInRequested(at_ns=self._clock.now_ns(), enabled=enabled)
        )

    async def start_push_to_talk(self, permission_granted: bool) -> None:
        await self._submit_command(
            PushToTalkStartRequested(
                at_ns=self._clock.now_ns(),
                permission_granted=permission_granted,
            )
        )

    async def stop_push_to_talk(self) -> None:
        await self._submit_command(PushToTalkStopRequested(at_ns=self._clock.now_ns()))

    async def start_streaming_conversation(
        self,
        permission_granted: bool,
        source: AssistantEntrySource = AssistantEntrySource.STREAMING_BUTTON,
        wake_keyword: str | None = None,
    ) -> None:
        await self._submit_command(
            StreamingConversationStartRequested(
                at_ns=self._clock.now_ns(),
                permission_granted=permission_granted,
                source=source,
                wake_keyword=wake_keyword,
            )
        )

    async def stop_streaming_conversation(self, reason: str = "user_stop") -> None:
        await self._submit_command(
            StreamingConversationStopRequested(
                at_ns=self._clock.now_ns(),
                reason=reason,
            )
        )

    async def abort_current_turn(self, reason: str = "user_interruption") -> None:
        await self._submit_command(AbortRequested(at_ns=self._clock.now_ns(), reason=reason))

    async def handle_system_audio_interruption(
        self,
        reason: str,
        resume_wakeword: bool = False,
    ) -> None:
        await self._submit_command(
            SystemAudioInterrupted(
                at_ns=self._clock.now_ns(),
                reason=reason,
                resume_wakeword=resume_wakeword,
            )
        )

    async def handle_system_audio_recovered(
        self,
        reason: str = "system_audio_recovered",
    ) -> None:
        await self._submit_command(SystemAudioRecovered(at_ns=self._clock.now_ns(), reason=reason))

    async def ensure_device_identity(self) -> None:
        await self._submit_command(EnsureIdentityRequested(at_ns=self._clock.now_ns()))

    async def reset_device_identity(self) -> None:
        await self._submit_command(ResetIdentityRequested(at_ns=self._clock.now_ns()))

    async def run_fake_activation(self) -> None:
        await self._submit_command(FakeActivationRequested(at_ns=self._clock.now_ns()))

    async def run_real_activation(self) -> None:
        await self._submit_command(RealActivationRequested(at_ns=self._clock.now_ns()))

    async def simulate_incoming_tool_call(
        self,
        tool_name: str,
        arguments_json: str = "{}",
    ) -> None:
        await self._submit_command(
            IncomingToolCallSimulationRequested(
                at_ns=self._clock.now_ns(),
                tool_name=tool_name,
                arguments_json=arguments_json,
            )
        )

    async def simulate_incoming_tools_list(self) -> None:
        await self._submit_command(ToolsListSimulationRequested(at_ns=self._clock.now_ns()))

    async def simulate_connection_closed(
        self,
        code: int = 1006,
        reason: str = "debug_abnormal_close",
    ) -> None:
        await self._submit_command(
            ConnectionClosedSimulationRequested(
                at_ns=self._clock.now_ns(),
                code=code,
                reason=reason,
            )
        )

    async def simulate_connection_failure(
        self,
        message: str = "debug_transport_failure",
    ) -> None:
        await self._submit_command(
            ConnectionFailureSimulationRequested(
                at_ns=self._clock.now_ns(),
                message=message,
            )
        )

    async def simulate_audio_failure(self, message: str = "debug_audio_failure") -> None:
        await self._submit_command(
            AudioFailureSimulationRequested(
                at_ns=self._clock.now_ns(),
                message=message,
            )
        )

    async def shutdown(self) -> None:
        if self._closed:
            return
        if self._shutdown_started:
            if self._pump_task is not None:
                await self._pump_task
            return

        await self.start()
        self._shutdown_started = True
        self._accepting_commands = False
        processed = asyncio.get_running_loop().create_future()
        await self._queue.put(
            _QueuedEvent(
                event=ShutdownRequested(at_ns=self._clock.now_ns()),
                processed=processed,
            )
        )
        await processed
        if self._pump_task is not None:
            await self._pump_task
        await self._cancel_effect_tasks()
        self._drain_unprocessed_events()
        self._closed = True

    async def _submit_command(self, event: AssistantEvent) -> None:
        if not self._accepting_commands or self._closed:
            raise ControllerClosedError("AssistantController is shutting down")
        await self.start()
        processed = asyncio.get_running_loop().create_future()
        await self._queue.put(_QueuedEvent(event=event, processed=processed))
        await processed

    async def _emit_adapter_event(self, event: AssistantEvent) -> None:
        if self._closed:
            return
        await self._queue.put(_QueuedEvent(event=event))

    async def _event_pump(self) -> None:
        while True:
            queued = await self._queue.get()
            event = queued.event
            try:
                transition = self._state_machine.reduce(self._state, event)
                if transition.state is not self._state:
                    self._state = transition.state
                    await self._notify_state_changed()
                await self._apply_effects(transition.effects)
                if queued.processed is not None and not queued.processed.done():
                    queued.processed.set_result(None)
            except Exception as exc:
                if queued.processed is not None and not queued.processed.done():
                    queued.processed.set_exception(exc)
                else:
                    await self._emit_adapter_event(
                        EffectExecutionFailed(
                            at_ns=self._clock.now_ns(),
                            effect_name="event_pump",
                            message=str(exc),
                        )
                    )
            finally:
                self._queue.task_done()

            if isinstance(event, ShutdownRequested):
                break

    async def _apply_effects(self, effects: tuple[AssistantEffect, ...]) -> None:
        for effect in effects:
            if isinstance(effect, CancelRuntimeEffects):
                await self._cancel_effect_tasks()
                continue
            if isinstance(effect, CloseTransport):
                await self._execute_effect(effect)
                continue
            task = asyncio.create_task(
                self._execute_effect(effect),
                name=f"assistant-effect-{type(effect).__name__}",
            )
            self._effect_tasks.add(task)
            task.add_done_callback(self._effect_tasks.discard)

    async def _execute_effect(self, effect: AssistantEffect) -> None:
        try:
            await self._effect_runner.execute(effect)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            generation = getattr(effect, "generation", None)
            await self._emit_adapter_event(
                EffectExecutionFailed(
                    at_ns=self._clock.now_ns(),
                    effect_name=type(effect).__name__,
                    message=str(exc),
                    generation=generation,
                )
            )

    async def _cancel_effect_tasks(self) -> None:
        tasks = tuple(task for task in self._effect_tasks if not task.done())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._effect_tasks.difference_update(tasks)

    async def _notify_state_changed(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener(self._state)
            except Exception:
                continue
        async with self._state_condition:
            self._state_condition.notify_all()

    def _drain_unprocessed_events(self) -> None:
        while True:
            try:
                queued = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if queued.processed is not None and not queued.processed.done():
                queued.processed.set_exception(
                    ControllerClosedError("event was discarded during shutdown")
                )
            self._queue.task_done()
