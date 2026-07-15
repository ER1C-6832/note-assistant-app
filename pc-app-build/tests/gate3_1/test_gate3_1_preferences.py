from __future__ import annotations

import json
from pathlib import Path

from app.assistant import AssistantPreferences, AssistantPreferencesStore, VoiceInteractionMode


def test_preferences_defaults_and_round_trip(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "assistant_preferences.json")

    defaults = store.load()
    assert defaults.voice_interaction_mode is VoiceInteractionMode.HOLD_TO_TALK
    assert defaults.streaming_idle_timeout_ms == 8_000
    assert defaults.streaming_barge_in_enabled is False
    assert defaults.launcher_x_ratio == 1.0
    assert defaults.launcher_y_ratio == 1.0

    saved = store.save(
        AssistantPreferences(
            voice_interaction_mode=VoiceInteractionMode.STREAMING_CONVERSATION,
            streaming_idle_timeout_ms=12_000,
            streaming_barge_in_enabled=True,
            launcher_x_ratio=0.25,
            launcher_y_ratio=0.75,
        )
    )
    assert saved == store.load()
    payload = json.loads(store.path.read_text(encoding="utf-8"))
    assert payload["voice_interaction_mode"] == "streaming_conversation"
    assert payload["schema_version"] == 1


def test_preferences_invalid_values_fall_back_and_clamp(tmp_path: Path) -> None:
    path = tmp_path / "assistant_preferences.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "voice_interaction_mode": "unknown",
                "streaming_idle_timeout_ms": 999_999,
                "streaming_barge_in_enabled": "yes",
                "conversation_text_enabled": None,
                "text_input_enabled": False,
                "launcher_x_ratio": -2,
                "launcher_y_ratio": 4,
            }
        ),
        encoding="utf-8",
    )

    loaded = AssistantPreferencesStore(path).load()
    assert loaded.voice_interaction_mode is VoiceInteractionMode.HOLD_TO_TALK
    assert loaded.streaming_idle_timeout_ms == 60_000
    assert loaded.streaming_barge_in_enabled is False
    assert loaded.conversation_text_enabled is True
    assert loaded.text_input_enabled is False
    assert loaded.launcher_x_ratio == 0.0
    assert loaded.launcher_y_ratio == 1.0


def test_launcher_update_preserves_runtime_preferences(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "assistant_preferences.json")
    store.update_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
    store.update_streaming_barge_in_enabled(True)
    updated = store.update_launcher_position(0.4, 0.6)

    assert updated.voice_interaction_mode is VoiceInteractionMode.STREAMING_CONVERSATION
    assert updated.streaming_barge_in_enabled is True
    assert (updated.launcher_x_ratio, updated.launcher_y_ratio) == (0.4, 0.6)
