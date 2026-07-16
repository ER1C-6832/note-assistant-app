from __future__ import annotations

import asyncio

import pytest

from app.assistant.controller import EffectRunner
from app.assistant.effects import (
    CloseTransport,
    SetVoiceInteractionMode,
    StopStreamingConversation,
)
from app.assistant.playback import (
    AssistantPlaybackEngine,
    DeterministicFakeOpusDecoder,
    GateControlledFakeAudioOutput,
    PcmAudioFormat,
    PlaybackCoordinator,
    PyAudioOutputPlan,
)
from app.assistant.playback.runtime_controller import PlaybackEffectRunner
from app.assistant.playback.runtime_events import (
    ActualPlaybackEnded,
    ActualPlaybackStarted,
    RuntimePlaybackCancelled,
)
from app.assistant.protocol import DownlinkAudioFormat
from app.assistant.state import VoiceInteractionMode


class _Clock:
    def __init__(self) -> None:
        self.value = 0

    def now_ns(self) -> int:
        self.value += 1_000_000
        return self.value


class _CoordinatorSpy:
    def __init__(self, order: list[str]) -> None:
        self.order = order

    @property
    def task_running(self) -> bool:
        return False

    @property
    def output_running(self) -> bool:
        return False

    @property
    def pcm_buffered_bytes(self) -> int:
        return 0

    @property
    def last_summary(self):
        return None

    @property
    def last_latency_sample(self):
        return {}

    @property
    def output_plan(self):
        return None

    async def cancel(self, reason: str, playback_generation: int | None = None) -> bool:
        del playback_generation
        self.order.append(f"cancel:{reason}")
        return True

    async def close(self) -> None:
        self.order.append("coordinator:close")


async def _sink(_event) -> None:
    return None


def _runner(order: list[str]) -> PlaybackEffectRunner:
    return PlaybackEffectRunner(
        playback_coordinator=_CoordinatorSpy(order),
        transport=object(),
        event_sink=_sink,
        clock=_Clock(),
    )


@pytest.mark.asyncio
async def test_user_stop_cancels_playback_before_streaming_stop(monkeypatch) -> None:
    order: list[str] = []

    async def base_execute(_self, effect) -> None:
        order.append(f"base:{type(effect).__name__}")

    monkeypatch.setattr(EffectRunner, "execute", base_execute)
    runner = _runner(order)
    effect = StopStreamingConversation(
        connection_generation=1,
        streaming_generation=1,
        capture_generation=2,
        turn_token=2,
        requested_at_ns=10,
        reason="user_stop",
        submit_audio=False,
        end_session=True,
    )

    await runner.execute(effect)

    assert order == ["cancel:user_stop", "base:StopStreamingConversation"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("effect", "reason"),
    [
        (CloseTransport(generation=1, reason="user_disconnect"), "user_disconnect"),
        (
            SetVoiceInteractionMode(mode=VoiceInteractionMode.HOLD_TO_TALK),
            "voice_mode_changed",
        ),
    ],
)
async def test_disconnect_and_mode_switch_cancel_before_delegate(
    monkeypatch, effect, reason
) -> None:
    order: list[str] = []

    async def base_execute(_self, delegated) -> None:
        order.append(f"base:{type(delegated).__name__}")

    monkeypatch.setattr(EffectRunner, "execute", base_execute)
    runner = _runner(order)

    await runner.execute(effect)

    assert order[0] == f"cancel:{reason}"
    assert order[1] == f"base:{type(effect).__name__}"


@pytest.mark.asyncio
async def test_shutdown_closes_playback_before_base_runtime(monkeypatch) -> None:
    order: list[str] = []

    async def base_shutdown(_self) -> None:
        order.append("base:shutdown")

    monkeypatch.setattr(EffectRunner, "shutdown", base_shutdown)
    runner = _runner(order)

    await runner.shutdown()

    assert order == ["coordinator:close", "base:shutdown"]


@pytest.mark.asyncio
async def test_cancelled_playback_emits_cancel_not_natural_end() -> None:
    clock = _Clock()
    output = GateControlledFakeAudioOutput(chunk_bytes=3_840)
    plan = PyAudioOutputPlan(0, "Fake output", PcmAudioFormat(48_000, 2), 960)

    def engine_factory(context, selected, sink):
        return AssistantPlaybackEngine(
            decoder_factory=lambda _context: DeterministicFakeOpusDecoder(
                pcm_format=selected.pcm_format,
                clock_ns=clock.now_ns,
            ),
            output_factory=lambda: output,
            event_sink=sink,
            clock_ns=clock.now_ns,
            startup_prebuffer_chunks=1,
            drain_timeout_seconds=1.0,
        )

    events = []

    async def sink(event) -> None:
        events.append(event)

    coordinator = PlaybackCoordinator(
        clock_ns=clock.now_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
    )
    await coordinator.open_generation(1, sink)
    context = await coordinator.begin_stream(
        connection_generation=1,
        stream_sequence=1,
        turn_token=1,
        streaming_generation=1,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        session_id="session",
        started_at_ns=clock.now_ns(),
    )
    assert context is not None
    for payload in (b"one", b"two", b"three"):
        assert coordinator.offer_payload_nowait(
            connection_generation=1,
            stream_sequence=1,
            payload=payload,
            received_at_ns=clock.now_ns(),
        )
    assert await coordinator.start_playback(
        connection_generation=1,
        stream_sequence=1,
        playback_generation=1,
    )

    for _ in range(200):
        if any(isinstance(event, ActualPlaybackStarted) for event in events):
            break
        await asyncio.sleep(0.001)

    assert any(isinstance(event, ActualPlaybackStarted) for event in events)
    assert await coordinator.cancel("user_stop", playback_generation=1)
    await asyncio.sleep(0)

    assert sum(isinstance(event, RuntimePlaybackCancelled) for event in events) == 1
    assert not any(isinstance(event, ActualPlaybackEnded) for event in events)
    assert coordinator.active_context is None
    assert not coordinator.task_running
    assert not coordinator.output_running
    assert coordinator.pcm_buffered_bytes == 0

    await coordinator.close_generation(1, "test_complete")
    await coordinator.close_generation(1, "duplicate_close")
