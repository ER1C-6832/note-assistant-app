"""Pure bounded reconnect policy shared by Fake and Real runtime paths."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconnectDecision:
    should_reconnect: bool
    next_attempt: int
    delay_seconds: float | None
    decision_label: str
    user_message: str


class ReconnectPolicy:
    """Decide whether and when one connection generation may reconnect."""

    NORMAL_CLOSE_CODE = 1000
    MAX_RECONNECT_ATTEMPTS = 3
    BACKOFF_SECONDS = (0.5, 1.5, 3.0)

    def __init__(
        self,
        *,
        jitter_fraction: float = 0.10,
        max_jitter_seconds: float = 0.25,
        backoff_seconds: tuple[float, float, float] = BACKOFF_SECONDS,
    ) -> None:
        if not 0.0 <= jitter_fraction <= 0.50:
            raise ValueError("jitter_fraction must be between 0.0 and 0.50")
        if max_jitter_seconds < 0.0:
            raise ValueError("max_jitter_seconds cannot be negative")
        if len(backoff_seconds) != self.MAX_RECONNECT_ATTEMPTS:
            raise ValueError("backoff_seconds must contain exactly three delays")
        if any(delay <= 0.0 for delay in backoff_seconds):
            raise ValueError("backoff delays must be positive")
        self._jitter_fraction = jitter_fraction
        self._max_jitter_seconds = max_jitter_seconds
        self._backoff_seconds = backoff_seconds

    def decide_close(
        self,
        *,
        close_code: int,
        reason: str,
        assistant_enabled: bool,
        manual_disconnect_requested: bool,
        current_attempt: int,
        generation: int,
        jitter_seed: int | None = None,
    ) -> ReconnectDecision:
        if not assistant_enabled:
            return self._no_reconnect("disabled_no_reconnect", "助手已关闭，不重连。")
        if manual_disconnect_requested:
            return self._no_reconnect(
                "manual_disconnect_no_reconnect",
                "连接由用户关闭，不自动重连。",
            )
        if close_code == self.NORMAL_CLOSE_CODE:
            return self._no_reconnect(
                "normal_close_no_reconnect",
                f"连接已正常关闭：{reason}",
            )
        return self._retry(
            current_attempt=current_attempt,
            generation=generation,
            jitter_seed=jitter_seed,
            label_prefix="close",
            user_prefix="连接异常关闭",
        )

    def decide_failure(
        self,
        *,
        assistant_enabled: bool,
        manual_disconnect_requested: bool,
        current_attempt: int,
        generation: int,
        jitter_seed: int | None = None,
    ) -> ReconnectDecision:
        if not assistant_enabled:
            return self._no_reconnect(
                "disabled_failure_no_reconnect",
                "助手已关闭，连接失败后不重连。",
            )
        if manual_disconnect_requested:
            return self._no_reconnect(
                "manual_failure_no_reconnect",
                "连接由用户关闭，失败后不自动重连。",
            )
        return self._retry(
            current_attempt=current_attempt,
            generation=generation,
            jitter_seed=jitter_seed,
            label_prefix="failure",
            user_prefix="连接失败",
        )

    def _retry(
        self,
        *,
        current_attempt: int,
        generation: int,
        jitter_seed: int | None,
        label_prefix: str,
        user_prefix: str,
    ) -> ReconnectDecision:
        next_attempt = current_attempt + 1
        if next_attempt > self.MAX_RECONNECT_ATTEMPTS:
            return ReconnectDecision(
                should_reconnect=False,
                next_attempt=current_attempt,
                delay_seconds=None,
                decision_label=f"{label_prefix}_max_attempts_reached",
                user_message=f"{user_prefix}，已达到最大重连次数。",
            )
        delay = self._delay_seconds(
            next_attempt,
            generation,
            jitter_seed=generation if jitter_seed is None else jitter_seed,
        )
        return ReconnectDecision(
            should_reconnect=True,
            next_attempt=next_attempt,
            delay_seconds=delay,
            decision_label=f"{label_prefix}_reconnect_attempt_{next_attempt}",
            user_message=(f"{user_prefix}，将在 {delay:.3f}s 后进行第 {next_attempt} 次重连。"),
        )

    def _delay_seconds(
        self,
        attempt: int,
        generation: int,
        *,
        jitter_seed: int,
    ) -> float:
        base = self._backoff_seconds[attempt - 1]
        jitter_limit = min(base * self._jitter_fraction, self._max_jitter_seconds)
        if jitter_limit == 0.0:
            return base

        # Deterministic per generation/attempt: pure reducer behavior with bounded spread.
        seed = (
            (generation + 1) * 1_103_515_245 + attempt * 12_345 + jitter_seed * 2_654_435_761
        ) & 0x7FFFFFFF
        unit = (seed % 2001) / 1000.0 - 1.0
        return round(max(0.0, base + unit * jitter_limit), 6)

    @staticmethod
    def _no_reconnect(label: str, message: str) -> ReconnectDecision:
        return ReconnectDecision(
            should_reconnect=False,
            next_attempt=0,
            delay_seconds=None,
            decision_label=label,
            user_message=message,
        )
