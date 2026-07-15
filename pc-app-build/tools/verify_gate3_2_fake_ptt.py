"""Run deterministic Gate 3.2 PTT audio-pipeline acceptance."""

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
    AssistantPhase,
    ConversationStateMachine,
    ReconnectPolicy,
    redact_error_text,
)
from app.assistant.audio import (  # noqa: E402
    AssistantAudioEngine,
    FakeCaptureScript,
    FakeOpusEncoder,
    MicrophoneLeaseCoordinator,
    ScriptedFakeAudioCapture,
)
from app.assistant.testing import (  # noqa: E402
    FakeClock,
    OpenSucceeded,
    ScriptedFakeTransport,
    VoiceReply,
)


def _frames(*, count: int, amplitude: int) -> tuple[bytes, ...]:
    frame = struct.pack("<320h", *([amplitude] * 320))
    return tuple(frame for _ in range(count))


def _runtime(frames: tuple[bytes, ...], *, voice_steps=()):
    clock = FakeClock()
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(frames))
    engine = AssistantAudioEngine(capture=capture, encoder_factory=FakeOpusEncoder)
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=(OpenSucceeded(session_id="gate3-2-fake-session"),),
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


async def _run() -> dict[str, object]:
    controller, capture, transport = _runtime(
        _frames(count=5, amplitude=1600),
        voice_steps=(VoiceReply(stt_text="记录客户报价", assistant_text="好的"),),
    )
    happy_path = False
    no_pending_runtime_tasks = False
    completed_state = controller.state
    try:
        await _connect(controller)
        await controller.start_push_to_talk(permission_granted=True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        emitted = capture.emit_all()
        await asyncio.sleep(0.1)
        await controller.stop_push_to_talk()
        completed = await controller.wait_for_state(
            lambda state: state.conversation.last_completed_voice_turn_token == 1,
            timeout_seconds=2.0,
        )
        completed_state = completed
        happy_path = bool(
            emitted == 5
            and completed.phase is AssistantPhase.CONNECTED
            and completed.conversation.last_stt_text == "记录客户报价"
            and completed.conversation.last_assistant_text == "好的"
            and completed.audio.captured_frames == 5
            and completed.audio.encoded_frames == 5
            and completed.audio.uploaded_frames == 5
            and len(transport.listen_start_calls) == 1
            and len(transport.listen_stop_calls) == 1
            and len(transport.sent_audio_packets) == 5
            and not transport.abort_calls
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
        no_pending_runtime_tasks = (
            pending == []
            and controller.closed
            and not controller.audio_uplink_running
            and not controller.audio_capture_active
            and not controller.audio_worker_alive
            and controller.microphone_lease_generation is None
        )

    no_speech_controller, no_speech_capture, no_speech_transport = _runtime(
        _frames(count=3, amplitude=0)
    )
    no_speech_abort = False
    try:
        await _connect(no_speech_controller)
        await no_speech_controller.start_push_to_talk(permission_granted=True)
        await no_speech_controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        no_speech_capture.emit_all()
        await asyncio.sleep(0.05)
        await no_speech_controller.stop_push_to_talk()
        stopped = await no_speech_controller.wait_for_state(
            lambda state: state.conversation.last_completed_voice_turn_token == 1,
            timeout_seconds=2.0,
        )
        no_speech_abort = bool(
            stopped.phase is AssistantPhase.CONNECTED
            and len(no_speech_transport.abort_calls) == 1
            and not no_speech_transport.listen_stop_calls
        )
    finally:
        await no_speech_controller.shutdown()

    checks = {
        "fake_ptt_happy_path": happy_path,
        "no_speech_abort": no_speech_abort,
        "single_listen_start": len(transport.listen_start_calls) == 1,
        "single_listen_stop": len(transport.listen_stop_calls) == 1,
        "binary_audio_uploaded": len(transport.sent_audio_packets) == 5,
        "stt_received": completed_state.conversation.last_stt_text == "记录客户报价",
        "assistant_reply_received": completed_state.conversation.last_assistant_text == "好的",
        "no_pending_runtime_tasks": no_pending_runtime_tasks,
    }
    return {
        "status": "gate3_2_fake_ptt_verified" if all(checks.values()) else "failed",
        **checks,
        "captured_frames": completed_state.audio.captured_frames,
        "encoded_frames": completed_state.audio.encoded_frames,
        "uploaded_frames": completed_state.audio.uploaded_frames,
        "pending_runtime_tasks": pending,
    }


def main() -> int:
    try:
        result = asyncio.run(_run())
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] == "gate3_2_fake_ptt_verified" else 1
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
