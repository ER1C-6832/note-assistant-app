"""Deterministic Gate 4.3 two-playback auto-next acceptance without devices."""

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
from app.assistant.playback.two_turn_state_machine import (  # noqa: E402
    TwoTurnConversationStateMachine,
)
from app.assistant.protocol import DownlinkAudioFormat  # noqa: E402
from app.assistant.state import (  # noqa: E402
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    MicrophoneOwner,
    StreamingConversationState,
    VoiceInteractionMode,
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

    reducer = TwoTurnConversationStateMachine()
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
        audio=replace(
            disabled.audio,
            capture_generation=1,
            microphone_owner=MicrophoneOwner.NONE,
        ),
        conversation=replace(
            disabled.conversation,
            preferred_voice_mode=VoiceInteractionMode.STREAMING_CONVERSATION,
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
    auto_next_effects: list[StartStreamingConversation] = []
    coordinator: PlaybackCoordinator

    async def sink(event) -> None:
        nonlocal state
        events.append(event)
        transition = reducer.reduce(state, event)
        state = transition.state
        for effect in transition.effects:
            if isinstance(effect, StartActualPlayback):
                await coordinator.start_playback(
                    connection_generation=effect.connection_generation,
                    stream_sequence=effect.stream_sequence,
                    playback_generation=effect.playback_generation,
                )
            elif isinstance(effect, StartStreamingConversation):
                auto_next_effects.append(effect)

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
    )
    await coordinator.open_generation(1, sink)
    wire = DownlinkAudioFormat("opus", 24_000, 1, 20.0)
    summaries = []

    async def play_turn(stream_sequence: int, turn_token: int) -> None:
        nonlocal state
        context = await coordinator.begin_stream(
            connection_generation=1,
            stream_sequence=stream_sequence,
            turn_token=turn_token,
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
                stream_sequence=stream_sequence,
                playback_generation=stream_sequence,
                turn_token=turn_token,
                wire_format=wire,
                streaming_generation=1,
            )
        )
        for packet in (b"one", b"two", b"three"):
            assert coordinator.offer_payload_nowait(
                connection_generation=1,
                stream_sequence=stream_sequence,
                payload=packet,
                received_at_ns=clock_ns(),
            )
        assert coordinator.end_stream_nowait(
            connection_generation=1,
            stream_sequence=stream_sequence,
            reason="tts_stop",
            at_ns=clock_ns(),
        )
        target = stream_sequence
        for _ in range(300):
            ended = [item for item in events if isinstance(item, ActualPlaybackEnded)]
            if len(ended) >= target:
                break
            await asyncio.sleep(0.001)
        assert coordinator.last_summary is not None
        summaries.append(coordinator.last_summary)

    await play_turn(1, 1)
    first_effect = auto_next_effects[0]
    assert first_effect.turn_token == 2
    assert first_effect.capture_generation == 2
    assert first_effect.turn_index == 2

    # Model the completed auto-start/capture/submit boundary without opening a microphone.
    state = replace(
        state,
        phase=AssistantPhase.THINKING,
        audio=replace(
            state.audio,
            status=AssistantAudioStatus.IDLE,
            capture_generation=2,
            microphone_owner=MicrophoneOwner.NONE,
        ),
        conversation=replace(
            state.conversation,
            active_voice_turn_token=2,
            active_streaming_turn_token=2,
            streaming_turn_index=2,
            streaming_state=StreamingConversationState.THINKING,
        ),
    )
    await play_turn(2, 2)

    started_count = sum(isinstance(item, ActualPlaybackStarted) for item in events)
    ended_count = sum(isinstance(item, ActualPlaybackEnded) for item in events)
    verified = bool(
        len(summaries) == 2
        and all(summary.natural_end for summary in summaries)
        and all(summary.encoded_packets_received == 3 for summary in summaries)
        and all(
            summary.decoded_sample_frames == summary.played_sample_frames > 0
            for summary in summaries
        )
        and started_count == 2
        and ended_count == 2
        and len(auto_next_effects) == 2
        and auto_next_effects[0].turn_index == 2
        and auto_next_effects[1].turn_index == 3
        and state.conversation.streaming_state is StreamingConversationState.STARTING
        and state.conversation.streaming_turn_index == 3
        and state.audio.status is AssistantAudioStatus.IDLE
        and not coordinator.output_running
        and not coordinator.task_running
    )
    result = {
        "status": "fake_gate_complete" if verified else "failed",
        "completed_playback_turns": len(summaries),
        "playback_started_count": started_count,
        "playback_ended_count": ended_count,
        "auto_next_turn_request_count": len(auto_next_effects),
        "next_turn_indices": [effect.turn_index for effect in auto_next_effects],
        "capture_generations": [
            effect.capture_generation for effect in auto_next_effects
        ],
        "turn_tokens": [effect.turn_token for effect in auto_next_effects],
        "decoded_sample_frames": [
            summary.decoded_sample_frames for summary in summaries
        ],
        "played_sample_frames": [summary.played_sample_frames for summary in summaries],
        "capture_playback_overlap_count": 0,
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
