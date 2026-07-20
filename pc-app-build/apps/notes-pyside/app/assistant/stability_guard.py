"""Fail-closed product guards for native audio paths under incident response."""

from __future__ import annotations

from dataclasses import replace

from .preferences import (
    AssistantPreferences,
    AssistantPreferencesError,
    AssistantPreferencesStore,
)

NATIVE_BARGE_IN_PRODUCT_ENABLED = False
NATIVE_BARGE_IN_DISABLED_ERROR_CODE = "native_barge_in_temporarily_disabled"


def apply_native_barge_in_stability_guard(
    store: AssistantPreferencesStore,
    preferences: AssistantPreferences,
) -> AssistantPreferences:
    """Disable the incident path without making preference I/O a startup risk."""

    if NATIVE_BARGE_IN_PRODUCT_ENABLED or not preferences.streaming_barge_in_enabled:
        return preferences
    guarded = replace(preferences, streaming_barge_in_enabled=False)
    try:
        # Save the already-loaded complete snapshot.  Calling an update helper
        # here would reload an empty/new file and could reset unrelated KWS or
        # auto-connect preferences to their defaults.
        return store.save(guarded)
    except AssistantPreferencesError:
        return guarded
