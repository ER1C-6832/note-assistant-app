"""Run deterministic Gate 3.3 streaming/VAD acceptance."""

from __future__ import annotations

import asyncio
import json
import struct
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant import (  # noqa: E402
    AssistantAudioStatus,
    AssistantController,
    ConversationStateMachine,
    StreamingConversationState,
    VoiceActivityState,
    VoiceInteractionMode,
    redact_error_text,
)
from app.assistant.audio import (  # noqa: E402
    AssistantAudioEngine,
    FakeCaptureScript,
    FakeOpusEncoder,
    MicrophoneLeaseCoordinator,
    ScriptedFakeAudioCapture,
    ScriptedVoiceActivityDetector,
)
from app.assistant.network import ReconnectPolicy  # noqa: E402
from app.assistant.testing import (  # noqa: E402
    FakeClock,
    OpenSucceeded,
    ScriptedFakeTransport,
    VoiceReply,
)


def _frames(count: int, amplitude: int) -> tuple[bytes, ...]:
    frame = struct.pack("<320h", *([amplitude] * 320))
    return tuple(frame for _ in range(count))


def _runtime(*, states, frames, voice_steps=()):
    clock = FakeClock()
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(frames))
    engine = AssistantAudioEngine(
        capture=capture,
        encoder_factory=FakeOpusEncoder,
        vad_factory=lambda _timeout: ScriptedVoiceActivityDetector(states),
    )
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=(OpenSucceeded(session_id="gate3-3-fake-session"),),
        voice_steps=voice_steps,
    )
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(
            ReconnectPolicy(jitter_fraction=0.0, backoff_seconds=(0.01, 0.02, 0.03))
        ),
        clock=clock,
        audio_engine=engine,
        microphone_coordinator=MicrophoneLeaseCoordinator(),
    )
    return controller, capture, transport


async def _connect(controller: AssistantController) -> None:
    await controller.enable_assistant()
    await controller.use_fake_runtime()
    await controller.connect()
    await controller.wait_for_state(lambda state: state.is_connected)
    await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)


async def _run() -> dict[str, object]:
    states = (
        VoiceActivityState.WARMUP,
        VoiceActivityState.WAITING_FOR_SPEECH,
        VoiceActivityState.SPEECH_DETECTED,
        VoiceActivityState.SPEECH_ACTIVE,
        VoiceActivityState.END_OF_SPEECH,
    )
    controller, capture, transport = _runtime(
        states=states,
        frames=_frames(len(states), 1600),
        voice_steps=(VoiceReply(stt_text="记录客户报价", assistant_text="好的"),),
    )
    completed = controller.state
    local_session_id = None
    pending: list[str] = []
    checks: dict[str, bool] = {}
    try:
        await _connect(controller)
        await controller.start_streaming_conversation(permission_granted=True)
        started = await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
            and state.conversation.streaming_session_active
        )
        local_session_id = started.conversation.streaming_session_id
        emitted = capture.emit_all()
        waiting = await controller.wait_for_state(
            lambda state: state.conversation.streaming_state
            is StreamingConversationState.WAITING_FOR_NEXT_TURN
            and state.conversation.last_assistant_text == "好的",
            timeout_seconds=3.0,
        )
        listen_starts_before_wait = len(transport.listen_start_calls)
        await asyncio.sleep(0.05)
        checks = {
            "streaming_session_uuid": bool(local_session_id and len(local_session_id) >= 32),
            "vad_speech_started": waiting.diagnostics.vad_speech_started_count == 1,
            "vad_speech_ended": waiting.diagnostics.vad_speech_ended_count == 1,
            "auto_listen_stop": len(transport.listen_stop_calls) == 1,
            "single_listen_start": listen_starts_before_wait == 1,
            "binary_audio_uploaded": len(transport.sent_audio_packets) == emitted == len(states),
            "stt_received": waiting.conversation.last_stt_text == "记录客户报价",
            "assistant_reply_received": waiting.conversation.last_assistant_text == "好的",
            "waiting_for_next_turn": (
                waiting.conversation.streaming_state
                is StreamingConversationState.WAITING_FOR_NEXT_TURN
            ),
            "session_remains_active_while_waiting": waiting.conversation.streaming_session_active,
            "waiting_audio_idle": waiting.audio.status is AssistantAudioStatus.IDLE,
            "waiting_response_timer_stopped": not controller.streaming_response_timer_running,
            "waiting_capture_released": (
                not controller.audio_capture_active
                and not controller.audio_uplink_running
                and not controller.streaming_vad_running
                and not controller.audio_worker_alive
                and controller.microphone_lease_generation is None
            ),
            "no_automatic_next_turn": (
                len(transport.listen_start_calls) == listen_starts_before_wait == 1
                and not controller.audio_capture_active
            ),
        }

        await controller.stop_streaming_conversation("gate3_3_fake_acceptance")
        completed = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )
        checks.update(
            {
                "manual_session_stop": not completed.conversation.streaming_session_active,
                "capture_released": (
                    not controller.audio_capture_active
                    and not controller.audio_uplink_running
                    and not controller.streaming_vad_running
                    and not controller.streaming_response_timer_running
                    and not controller.audio_worker_alive
                    and controller.microphone_lease_generation is None
                ),
            }
        )
    finally:
        await controller.shutdown()
        await asyncio.sleep(0)
        pending = sorted(
            task.get_name()
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and not task.done()
            and task.get_name().startswith("assistant-")
        )

    checks["no_pending_runtime_tasks"] = pending == []
    return {
        "status": ("gate3_3_fake_streaming_verified" if all(checks.values()) else "failed"),
        **checks,
        "streaming_generation": completed.conversation.streaming_generation,
        "streaming_turn_index": completed.conversation.streaming_turn_index,
        "captured_frames": completed.audio.captured_frames,
        "encoded_frames": completed.audio.encoded_frames,
        "uploaded_frames": completed.audio.uploaded_frames,
        "pending_runtime_tasks": pending,
    }


def main() -> int:
    try:
        result = asyncio.run(_run())
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] == "gate3_3_fake_streaming_verified" else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": redact_error_text(str(exc) or type(exc).__name__),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
