from __future__ import annotations

from dataclasses import replace

from app.assistant.preferences import (
    AssistantPreferences,
    AssistantPreferencesError,
    AssistantPreferencesStore,
)
from app.assistant.stability_guard import (
    NATIVE_BARGE_IN_DISABLED_ERROR_CODE,
    NATIVE_BARGE_IN_PRODUCT_ENABLED,
    apply_native_barge_in_stability_guard,
)


def test_native_barge_in_product_path_is_fail_closed(tmp_path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    store.save(replace(AssistantPreferences(), streaming_barge_in_enabled=True))

    guarded = apply_native_barge_in_stability_guard(store, store.load())

    assert NATIVE_BARGE_IN_PRODUCT_ENABLED is False
    assert NATIVE_BARGE_IN_DISABLED_ERROR_CODE == "native_barge_in_temporarily_disabled"
    assert guarded.streaming_barge_in_enabled is False
    assert store.load().streaming_barge_in_enabled is False


def test_guard_still_fails_closed_when_preference_rewrite_fails(monkeypatch, tmp_path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    enabled = replace(AssistantPreferences(), streaming_barge_in_enabled=True)

    def fail(_enabled: bool):
        raise AssistantPreferencesError("simulated read-only preference file")

    monkeypatch.setattr(store, "update_streaming_barge_in_enabled", fail)

    guarded = apply_native_barge_in_stability_guard(store, enabled)

    assert guarded.streaming_barge_in_enabled is False


def test_guard_does_not_touch_unrelated_kws_or_connection_preferences(tmp_path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    enabled = replace(
        AssistantPreferences(),
        streaming_barge_in_enabled=True,
        assistant_auto_connect_enabled=True,
        offline_kws_enabled=True,
    )

    guarded = apply_native_barge_in_stability_guard(store, enabled)

    assert guarded.assistant_auto_connect_enabled is True
    assert guarded.offline_kws_enabled is True
