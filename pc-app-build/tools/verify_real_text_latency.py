"""Measure one real text turn from submit to first TTS binary and terminal stop."""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from verify_gate2_4_real_text import (
    CONNECT_TIMEOUT_SECONDS,
    TEXT_TIMEOUT_SECONDS,
    AppPaths,
    AssistantController,
    DeviceIdentityManager,
    DeviceIdentityStore,
    LegacyPyXiaozhiIdentitySource,
    MonotonicClock,
    PersistedConnectionConfigProvider,
    RealWebSocketTransport,
    RuntimeConfigStore,
    RuntimeTransportRouter,
    _mask,
    _optional_env,
    _redact_message,
)
from app.assistant import McpCoordinator, McpScriptedFakeTransport, ToolRegistry
from app.assistant.mcp import Gate53ToolExecutor, UiCommandBus
from app.notes import (
    DatabaseExecutor,
    NoteCommandService,
    NoteQueryService,
    SqlAlchemyNoteRepository,
    TagCatalog,
    TagCatalogService,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)

DEFAULT_PROMPT = "只回复：延迟测试正常。"


def _elapsed_ms(started_ns: int, completed_ns: int) -> int:
    return max(0, round((completed_ns - started_ns) / 1_000_000))


async def _run(prompt_override: str | None = None) -> int:
    paths = AppPaths.resolve(
        root_override=_optional_env("NOTE_ASSISTANT_DATA_ROOT")
    )
    paths.ensure_directories()
    prompt = (
        prompt_override
        or _optional_env("NOTE_ASSISTANT_LATENCY_TEXT")
        or DEFAULT_PROMPT
    )
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=LegacyPyXiaozhiIdentitySource.from_local_app_data().load,
    )
    identity = await identity_manager.ensure_identity()
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    database_engine = create_sqlite_engine(paths.notes_db)
    initialize_database(database_engine)
    session_factory = create_session_factory(database_engine)
    note_repository = SqlAlchemyNoteRepository(session_factory)
    database_executor = DatabaseExecutor()
    note_command_service = NoteCommandService(
        note_repository,
        database_executor,
    )
    note_query_service = NoteQueryService(
        note_repository,
        database_executor,
    )
    tag_catalog = TagCatalog(paths.custom_tags)
    tag_catalog.load()
    tag_catalog_service = TagCatalogService(
        tag_catalog,
        note_query_service,
    )
    ui_command_bus = UiCommandBus()
    mcp_tool_executor = Gate53ToolExecutor(
        note_query_service,
        note_command_service,
        tag_catalog_service,
        ui_command_bus,
    )
    mcp_coordinator = McpCoordinator(
        ToolRegistry(executor=mcp_tool_executor)
    )
    clock = MonotonicClock()
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=McpScriptedFakeTransport(
                mcp_coordinator=mcp_coordinator
            ),
            real_transport=RealWebSocketTransport(
                config_provider=provider,
                clock=clock,
                mcp_coordinator=mcp_coordinator,
            ),
        ),
        clock=clock,
        identity_manager=identity_manager,
    )
    result: dict[str, object] = {
        "status": "failed",
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "websocket_url": None,
        "session_id_masked": None,
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "send_to_first_binary_ms": None,
        "send_to_tts_stop_ms": None,
        "assistant_text": None,
        "error_code": None,
        "error_message": None,
    }
    try:
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.connect()
        connected = await controller.wait_for_state(
            lambda state: state.is_connected or state.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        result["websocket_url"] = connected.connection.websocket_url_public
        result["session_id_masked"] = _mask(connected.connection.session_id)
        if not connected.is_connected:
            result["error_code"] = (
                connected.error.code if connected.error else "not_connected"
            )
            result["error_message"] = (
                _redact_message(connected.error.message)
                if connected.error
                else "真实 WebSocket 未连接"
            )
            return 1

        submitted_at_ns = time.perf_counter_ns()
        await controller.send_text(prompt)
        token = controller.state.conversation.active_text_turn_token
        first_binary = await controller.wait_for_state(
            lambda state: (
                state.error is not None
                or state.protocol.last_binary_size_bytes is not None
            ),
            timeout_seconds=TEXT_TIMEOUT_SECONDS,
        )
        first_binary_at_ns = time.perf_counter_ns()
        if first_binary.protocol.last_binary_size_bytes is None:
            result["error_code"] = (
                first_binary.error.code
                if first_binary.error
                else "first_binary_timeout"
            )
            result["error_message"] = (
                _redact_message(first_binary.error.message)
                if first_binary.error
                else "等待第一包 TTS 音频超时"
            )
            return 1
        result["send_to_first_binary_ms"] = _elapsed_ms(
            submitted_at_ns, first_binary_at_ns
        )

        terminal = await controller.wait_for_state(
            lambda state: (
                state.error is not None
                or (
                    state.protocol.last_protocol_event
                    in {"VoiceTtsState:stop", "TtsStateReceived:stop"}
                    and (
                        token is None
                        or state.conversation.last_completed_text_turn_token >= token
                    )
                )
            ),
            timeout_seconds=TEXT_TIMEOUT_SECONDS,
        )
        terminal_at_ns = time.perf_counter_ns()
        result["send_to_tts_stop_ms"] = _elapsed_ms(
            submitted_at_ns, terminal_at_ns
        )
        result["assistant_text"] = terminal.conversation.last_assistant_text
        result["last_protocol_event"] = terminal.protocol.last_protocol_event
        result["last_binary_size_bytes"] = terminal.protocol.last_binary_size_bytes
        if terminal.error is not None:
            result["error_code"] = terminal.error.code
            result["error_message"] = _redact_message(terminal.error.message)
            return 1
        result["status"] = "latency_verified"
        return 0
    finally:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        await controller.shutdown()
        await mcp_coordinator.close()
        await tag_catalog_service.close()
        await database_executor.close()
        database_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure one real LAN text turn from submit to first TTS binary."
        )
    )
    parser.add_argument(
        "--prompt",
        help=(
            "Text to submit. Defaults to NOTE_ASSISTANT_LATENCY_TEXT or "
            f"{DEFAULT_PROMPT!r}."
        ),
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args.prompt))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_message": _redact_message(
                        str(exc) or type(exc).__name__
                    ),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
