from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from app.assistant.playback.models import PcmAudioFormat, TtsStreamContext
from app.assistant.playback.pyaudio_output import (
    PyAudioOutputAdapter,
    PyAudioOutputPlan,
)
from app.assistant.playback.queues import PcmPlaybackBuffer
from app.assistant.protocol import DownlinkAudioFormat


class FakeStream:
    def __init__(self, callback) -> None:
        self.callback = callback
        self.active = False
        self.closed = False

    def start_stream(self) -> None:
        self.active = True

    def stop_stream(self) -> None:
        self.active = False

    def is_active(self) -> bool:
        return self.active

    def close(self) -> None:
        self.closed = True


class FakePyAudioManager:
    def __init__(self) -> None:
        self.stream: FakeStream | None = None
        self.terminated = False

    def open(self, **kwargs):
        self.stream = FakeStream(kwargs["stream_callback"])
        return self.stream

    def terminate(self) -> None:
        self.terminated = True


@pytest.mark.asyncio
async def test_callback_consumes_real_pcm_and_reports_drain_after_stream_inactive(
    monkeypatch,
) -> None:
    fake_module = SimpleNamespace(paInt16=8, paContinue=0, paComplete=1, paAbort=2)
    monkeypatch.setitem(sys.modules, "pyaudio", fake_module)
    manager = FakePyAudioManager()
    pcm_format = PcmAudioFormat(48_000, 2)
    plan = PyAudioOutputPlan(0, "Fake speakers", pcm_format, frames_per_buffer=4)
    adapter = PyAudioOutputAdapter(
        plan,
        pyaudio_factory=lambda: manager,
        poll_interval_seconds=0.001,
    )
    source = PcmPlaybackBuffer(pcm_format, capacity_bytes=64)
    payload = b"\x01\x02\x03\x04" * 4
    assert source.offer(payload)
    source.mark_terminal()
    consumed: list[tuple[int, int]] = []
    drained = asyncio.Event()
    context = TtsStreamContext(
        connection_generation=1,
        stream_sequence=1,
        playback_generation=1,
        turn_token=1,
        streaming_generation=None,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        started_at_ns=0,
    )

    await adapter.open(context, source, lambda b, f: consumed.append((b, f)), drained.set)
    await adapter.start()
    assert manager.stream is not None
    result, flag = manager.stream.callback(None, 4, {}, 0)
    assert result == payload
    assert flag == fake_module.paComplete
    assert consumed == [(16, 4)]
    assert not drained.is_set()

    manager.stream.active = False
    await asyncio.wait_for(drained.wait(), timeout=1)
    await adapter.close()
    assert manager.stream.closed
    assert manager.terminated
    assert not adapter.running


@pytest.mark.asyncio
async def test_callback_pads_underflow_without_claiming_real_samples(
    monkeypatch,
) -> None:
    fake_module = SimpleNamespace(paInt16=8, paContinue=0, paComplete=1, paAbort=2)
    monkeypatch.setitem(sys.modules, "pyaudio", fake_module)
    manager = FakePyAudioManager()
    pcm_format = PcmAudioFormat(48_000, 1)
    plan = PyAudioOutputPlan(0, "Fake speakers", pcm_format, frames_per_buffer=4)
    adapter = PyAudioOutputAdapter(plan, pyaudio_factory=lambda: manager)
    source = PcmPlaybackBuffer(pcm_format, capacity_bytes=64)
    consumed: list[tuple[int, int]] = []
    context = TtsStreamContext(
        connection_generation=1,
        stream_sequence=1,
        playback_generation=1,
        turn_token=1,
        streaming_generation=None,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        started_at_ns=0,
    )
    await adapter.open(context, source, lambda b, f: consumed.append((b, f)), lambda: None)
    assert manager.stream is not None
    result, flag = manager.stream.callback(None, 4, {}, 0)
    assert result == b"\x00" * 8
    assert flag == fake_module.paContinue
    assert consumed == []
    assert source.underflow_count == 1
    await adapter.close()
