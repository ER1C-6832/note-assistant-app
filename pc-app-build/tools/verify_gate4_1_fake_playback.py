"""Deterministic Gate 4.1 fake playback acceptance."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.playback import (  # noqa: E402
    AssistantPlaybackEngine,
    DeterministicFakeOpusDecoder,
    EncodedDownlinkPacket,
    GateControlledFakeAudioOutput,
    PlaybackEndedSignal,
    PlaybackFailedSignal,
    PlaybackStartedSignal,
    TtsStreamContext,
)
from app.assistant.protocol import DownlinkAudioFormat  # noqa: E402


class Clock:
    def __init__(self) -> None:
        self.value = 1_000_000

    def now_ns(self) -> int:
        self.value += 1_000_000
        return self.value


async def _run() -> int:
    clock = Clock()
    signals = []
    outputs = []

    async def sink(signal) -> None:
        signals.append(signal)

    def output_factory():
        output = GateControlledFakeAudioOutput(chunk_bytes=3_840)
        outputs.append(output)
        return output

    engine = AssistantPlaybackEngine(
        decoder_factory=lambda context: DeterministicFakeOpusDecoder(clock_ns=clock.now_ns),
        output_factory=output_factory,
        event_sink=sink,
        clock_ns=clock.now_ns,
    )
    context = TtsStreamContext(
        connection_generation=1,
        stream_sequence=1,
        playback_generation=1,
        turn_token=1,
        streaming_generation=1,
        wire_format=DownlinkAudioFormat(
            codec="opus",
            sample_rate_hz=24_000,
            channels=1,
            frame_duration_ms=20.0,
        ),
        started_at_ns=clock.now_ns(),
    )

    try:
        await engine.arm(context)
        for sequence in range(1, 4):
            accepted = engine.offer_packet(
                EncodedDownlinkPacket(
                    connection_generation=1,
                    stream_sequence=1,
                    packet_sequence=sequence,
                    received_at_ns=clock.now_ns(),
                    payload=f"fake-opus-{sequence}".encode(),
                )
            )
            if not accepted:
                raise RuntimeError("fake packet unexpectedly rejected")
        if not engine.end_stream(1, reason="tts_stop", at_ns=clock.now_ns()):
            raise RuntimeError("fake terminal unexpectedly rejected")
        await engine.start(1)
        terminal = await engine.wait_finished()

        started_count = sum(isinstance(item, PlaybackStartedSignal) for item in signals)
        ended_count = sum(isinstance(item, PlaybackEndedSignal) for item in signals)
        failed_count = sum(isinstance(item, PlaybackFailedSignal) for item in signals)
        summary = terminal.summary if isinstance(terminal, PlaybackEndedSignal) else None
        verified = bool(
            summary
            and started_count == 1
            and ended_count == 1
            and failed_count == 0
            and summary.encoded_packets_received == 3
            and summary.decoded_sample_frames > 0
            and summary.played_sample_frames == summary.decoded_sample_frames
            and summary.encoded_overflow_count == 0
            and summary.pcm_overflow_count == 0
            and not engine.task_running
            and not engine.output_running
        )
        print(
            json.dumps(
                {
                    "status": "fake_gate_complete" if verified else "failed",
                    "wire_format": context.wire_format.as_public_dict(),
                    "decoded_pcm_format": {
                        "sample_rate_hz": 48_000,
                        "channels": 2,
                        "sample_width_bytes": 2,
                    },
                    "encoded_packets_received": (
                        summary.encoded_packets_received if summary else 0
                    ),
                    "decoded_sample_frames": (summary.decoded_sample_frames if summary else 0),
                    "played_sample_frames": (summary.played_sample_frames if summary else 0),
                    "playback_started_count": started_count,
                    "playback_ended_count": ended_count,
                    "playback_failed_count": failed_count,
                    "task_running_at_final": engine.task_running,
                    "output_running_at_final": engine.output_running,
                    "payload_persisted": False,
                    "output_device_opened": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if verified else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:200],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        await engine.close()


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
