"""Deterministic Gate 4.2 playback/runtime acceptance without opening a device."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.effects import StartStreamingConversation  # noqa: E402
from app.assistant.playback import (  # noqa: E402
    AssistantPlaybackEngine,
    DeterministicFakeOpusDecoder,
    GateControlledFakeAudioOutput,
    PcmAudioFormat,
    PlaybackCoordinator,
    PyAudioOutputPlan,
)
from app.assistant.playback.runtime_effects import StartActualPlayback  # noqa: E402
from app.assistant.playback.runtime_events import (  # noqa: E402
    ActualPlaybackEnded,
    ActualPlaybackStarted,
    TtsPlaybackStreamStarted,
)
from app.assistant.playback.runtime_state_machine import (  # noqa: E402
    PlaybackConversationStateMachine,
)
from app.assistant.protocol import DownlinkAudioFormat  # noqa: E402
from app.assistant.state import (  # noqa: E402
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    StreamingConversationState,
)


async def _run() -> int:
    now = 0

    def clock_ns() -> int:
        nonlocal now
        now += 1_000_000
        return now

    output = GateControlledFakeAudioOutput(chunk_bytes=3_840)
    plan = PyAudioOutputPlan(0, "Fake output", PcmAudioFormat(48_000, 2), 960)

    def engine_factory(context, selected, sink):
        return AssistantPlaybackEngine(
            decoder_factory=lambda _context: DeterministicFakeOpusDecoder(
                pcm_format=selected.pcm_format,
                clock_ns=clock_ns,
            ),
            output_factory=lambda: output,
            event_sink=sink,
            clock_ns=clock_ns,
            startup_prebuffer_chunks=2,
            drain_timeout_seconds=1.0,
        )

    reducer = PlaybackConversationStateMachine()
    disabled = AssistantState.disabled(now_ns=0)
    state = replace(
        disabled,
        enabled=True,
        phase=AssistantPhase.THINKING,
        connection=replace(
            disabled.connection,
            status=AssistantConnectionStatus.CONNECTED,
            session_id="fake-session",
            connection_generation=1,
        ),
        audio=replace(disabled.audio, capture_generation=1),
        conversation=replace(
            disabled.conversation,
            active_entry_source=AssistantEntrySource.STREAMING_BUTTON,
            voice_turn_counter=1,
            active_voice_turn_token=1,
            streaming_session_active=True,
            streaming_generation=1,
            streaming_session_id="fake-streaming",
            streaming_turn_index=1,
            active_streaming_turn_token=1,
            streaming_state=StreamingConversationState.THINKING,
        ),
    )
    events = []
    auto_next_effects = 0
    coordinator: PlaybackCoordinator

    async def sink(event) -> None:
        nonlocal state, auto_next_effects
        events.append(event)
        transition = reducer.reduce(state, event)
        state = transition.state
        auto_next_effects += sum(
            isinstance(effect, StartStreamingConversation) for effect in transition.effects
        )
        for effect in transition.effects:
            if isinstance(effect, StartActualPlayback):
                await coordinator.start_playback(
                    connection_generation=effect.connection_generation,
                    stream_sequence=effect.stream_sequence,
                    playback_generation=effect.playback_generation,
                )

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
    )
    await coordinator.open_generation(1, sink)
    wire = DownlinkAudioFormat("opus", 24_000, 1, 20.0)
    context = await coordinator.begin_stream(
        connection_generation=1,
        stream_sequence=1,
        turn_token=1,
        streaming_generation=1,
        wire_format=wire,
        session_id="fake-session",
        started_at_ns=clock_ns(),
    )
    assert context is not None
    await sink(
        TtsPlaybackStreamStarted(
            at_ns=clock_ns(),
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            wire_format=wire,
            streaming_generation=1,
        )
    )
    for packet in (b"one", b"two", b"three"):
        assert coordinator.offer_payload_nowait(
            connection_generation=1,
            stream_sequence=1,
            payload=packet,
            received_at_ns=clock_ns(),
        )
    assert coordinator.end_stream_nowait(
        connection_generation=1,
        stream_sequence=1,
        reason="tts_stop",
        at_ns=clock_ns(),
    )
    for _ in range(200):
        if any(isinstance(event, ActualPlaybackEnded) for event in events):
            break
        await asyncio.sleep(0.001)

    summary = coordinator.last_summary
    verified = bool(
        summary
        and summary.natural_end
        and summary.encoded_packets_received == 3
        and summary.decoded_sample_frames > 0
        and summary.played_sample_frames == summary.decoded_sample_frames
        and sum(isinstance(event, ActualPlaybackStarted) for event in events) == 1
        and sum(isinstance(event, ActualPlaybackEnded) for event in events) == 1
        and auto_next_effects == 0
        and state.phase is AssistantPhase.CONNECTED
        and state.conversation.streaming_state is StreamingConversationState.WAITING_FOR_NEXT_TURN
        and not coordinator.output_running
        and not coordinator.task_running
    )
    result = {
        "status": "fake_gate_complete" if verified else "failed",
        "wire_format": wire.as_public_dict(),
        "output_format": {
            "sample_rate_hz": plan.pcm_format.sample_rate_hz,
            "channels": plan.pcm_format.channels,
            "sample_width_bytes": plan.pcm_format.sample_width_bytes,
        },
        "encoded_packets_received": summary.encoded_packets_received if summary else 0,
        "decoded_sample_frames": summary.decoded_sample_frames if summary else 0,
        "played_sample_frames": summary.played_sample_frames if summary else 0,
        "playback_started_count": sum(isinstance(event, ActualPlaybackStarted) for event in events),
        "playback_ended_count": sum(isinstance(event, ActualPlaybackEnded) for event in events),
        "auto_next_turn_count": auto_next_effects,
        "output_running_at_final": coordinator.output_running,
        "task_running_at_final": coordinator.task_running,
        "payload_persisted": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    await coordinator.close_generation(1, "fake_acceptance_complete")
    return 0 if verified else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
