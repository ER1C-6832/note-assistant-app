"""Device-local Gate 6.2 keyword model discovery without runtime downloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_KWS_MODEL_DIRECTORY = "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
DEFAULT_KWS_WAKE_PHRASE = "小智"


@dataclass(frozen=True, slots=True)
class KwsModelFiles:
    root: Path
    tokens: Path
    encoder: Path
    decoder: Path
    joiner: Path
    keywords: Path
    wake_phrase: str = DEFAULT_KWS_WAKE_PHRASE

    @property
    def public_summary(self) -> str:
        return f"{self.root.name} · {self.wake_phrase}"

    @property
    def missing_public_names(self) -> tuple[str, ...]:
        values = (self.tokens, self.encoder, self.decoder, self.joiner, self.keywords)
        return tuple(item.name for item in values if not item.is_file())

    @property
    def ready(self) -> bool:
        return not self.missing_public_names


@dataclass(frozen=True, slots=True)
class KwsModelSnapshot:
    status: str
    public_summary: str
    wake_phrase: str
    error_code: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"


class KwsModelRegistry:
    """Resolve the selected bundled/installed model from one private root."""

    def __init__(self, models_root: str | Path) -> None:
        self._models_root = Path(models_root)

    @property
    def default_model_dir(self) -> Path:
        return self._models_root / DEFAULT_KWS_MODEL_DIRECTORY

    def resolve(self) -> KwsModelFiles:
        root = self.default_model_dir
        return KwsModelFiles(
            root=root,
            tokens=root / "tokens.txt",
            encoder=root / "encoder-epoch-13-avg-2-chunk-16-left-64.onnx",
            decoder=root / "decoder-epoch-13-avg-2-chunk-16-left-64.onnx",
            joiner=root / "joiner-epoch-13-avg-2-chunk-16-left-64.onnx",
            keywords=root / "keywords_xiaozhi.txt",
        )

    def snapshot(self) -> KwsModelSnapshot:
        model = self.resolve()
        if not model.root.is_dir():
            return KwsModelSnapshot(
                status="missing",
                public_summary=f"未安装 · {model.wake_phrase}",
                wake_phrase=model.wake_phrase,
                error_code="kws_model_missing",
            )
        missing = model.missing_public_names
        if missing:
            return KwsModelSnapshot(
                status="invalid",
                public_summary=f"模型不完整（缺少 {len(missing)} 个文件）",
                wake_phrase=model.wake_phrase,
                error_code="kws_model_invalid",
            )
        return KwsModelSnapshot(
            status="ready",
            public_summary=model.public_summary,
            wake_phrase=model.wake_phrase,
        )
