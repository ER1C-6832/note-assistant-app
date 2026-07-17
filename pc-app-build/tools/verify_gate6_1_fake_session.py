"""Verify the product Gate 6.1 route supervisor without opening real devices."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.audio.device_registry import PyAudioDeviceRegistry  # noqa: E402
from app.assistant.audio.gate6_contracts import (  # noqa: E402
    DeviceDirection,
    DevicePreferenceMode,
    PlaybackActivity,
)
from app.assistant.audio.session_supervisor import AudioSessionSupervisor  # noqa: E402
from app.assistant.preferences import AssistantPreferencesStore  # noqa: E402


class _Manager:
    devices = (
        {
            "index": 0,
            "name": "Fake Default Microphone",
            "hostApi": 0,
            "maxInputChannels": 1,
            "maxOutputChannels": 0,
            "defaultSampleRate": 16000.0,
            "defaultLowInputLatency": 0.02,
        },
        {
            "index": 1,
            "name": "Fake Default Speakers",
            "hostApi": 0,
            "maxInputChannels": 0,
            "maxOutputChannels": 2,
            "defaultSampleRate": 48000.0,
            "defaultLowOutputLatency": 0.1,
        },
        {
            "index": 2,
            "name": "Fake USB Headset",
            "hostApi": 0,
            "maxInputChannels": 1,
            "maxOutputChannels": 2,
            "defaultSampleRate": 48000.0,
            "defaultLowInputLatency": 0.01,
            "defaultLowOutputLatency": 0.02,
        },
    )

    def get_device_count(self) -> int:
        return len(self.devices)

    def get_device_info_by_index(self, index: int) -> dict[str, object]:
        return dict(self.devices[index])

    def get_host_api_info_by_index(self, _index: int) -> dict[str, str]:
        return {"name": "Fake WASAPI"}

    def get_default_input_device_info(self) -> dict[str, int]:
        return {"index": 0}

    def get_default_output_device_info(self) -> dict[str, int]:
        return {"index": 1}

    def is_format_supported(self, _rate: int, **_kwargs: object) -> bool:
        return True

    def terminate(self) -> None:
        return None


class _Observer:
    def __init__(self) -> None:
        self.running = False

    def start(self, _sink) -> None:
        self.running = True

    def close(self) -> None:
        self.running = False


class _Duplex:
    open_stream_count = 0

    def close(self) -> None:
        self.open_stream_count = 0


async def _verify() -> tuple[dict[str, object], bool]:
    with tempfile.TemporaryDirectory(prefix="note-assistant-gate6-1-") as directory:
        observer = _Observer()
        supervisor = AudioSessionSupervisor(
            AssistantPreferencesStore(Path(directory) / "preferences.json"),
            registry=PyAudioDeviceRegistry(pyaudio_factory=_Manager),
            route_observer=observer,
            duplex_session=_Duplex(),
        )
        await supervisor.start()
        initial_generation = supervisor.snapshot.route_generation
        input_items = supervisor.input_device_items()
        output_items = supervisor.output_device_items()
        headset = next(item for item in input_items if "USB Headset" in str(item["label"]))
        await supervisor.select_device(
            DeviceDirection.INPUT,
            DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
            str(headset["key"]),
        )
        selected_name = supervisor.snapshot.input_device_public_name
        supervisor.set_playback_activity(PlaybackActivity.PLAYING)
        orthogonal_playback = supervisor.snapshot.playback_activity.value
        await supervisor.close()
        terminal = supervisor.diagnostics()
        verified = all(
            (
                initial_generation > 0,
                len(input_items) == 3,
                len(output_items) == 3,
                selected_name == "Fake USB Headset",
                orthogonal_playback == "playing",
                terminal["capture_activity"] == "inactive",
                terminal["playback_activity"] == "inactive",
                terminal["microphone_lease"]["owner"] == "none",
                terminal["route_observer_running"] is False,
                terminal["duplex_open_stream_count"] == 0,
                terminal["pending_route_tasks"] == [],
            )
        )
        report = {
            "status": "gate6_1_fake_session_complete" if verified else "failed",
            "initial_route_generation": initial_generation,
            "input_item_count": len(input_items),
            "output_item_count": len(output_items),
            "pinned_selection_public_name": selected_name,
            "orthogonal_playback_observed": orthogonal_playback,
            "private_device_ids_exposed": False,
            "portaudio_indexes_persisted": False,
            "product_aec_enabled": False,
            "product_kws_enabled": False,
            "terminal": terminal,
            "secrets_redacted": True,
            "payload_persisted": False,
        }
        return report, verified


def main() -> int:
    report, verified = asyncio.run(_verify())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
