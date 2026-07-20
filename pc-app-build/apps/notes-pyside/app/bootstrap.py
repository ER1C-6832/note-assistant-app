"""Composition root for the single-process desktop application."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from qasync import QEventLoop
from sqlalchemy import Engine

from .app_paths import AppPaths
from .assistant import (
    AssistantController,
    AssistantPreferencesStore,
    AssistantState,
    ConversationStateMachine,
    DeviceIdentityManager,
    DeviceIdentityStore,
    FakeActivationClient,
    McpCoordinator,
    McpScriptedFakeTransport,
    PersistedConnectionConfigProvider,
    RealOtaActivationClient,
    RealWebSocketTransport,
    ReconnectPolicy,
    RuntimeConfigStore,
    RuntimeTransportRouter,
    ToolRegistry,
)
from .assistant.audio import (
    AcousticBargeInCoordinator,
    AssistantAudioEngine,
    KwsModelRegistry,
    OfflineKwsCoordinator,
    PyAvOpusEncoder,
)
from .assistant.audio.session_supervisor import AudioSessionSupervisor
from .assistant.controller import SystemRuntimeClock
from .assistant.identity import LegacyPyXiaozhiIdentitySource
from .assistant.mcp import Gate53ToolExecutor, UiCommandBus
from .assistant.playback.coordinator import PlaybackCoordinator
from .assistant.stability_guard import (
    NATIVE_BARGE_IN_PRODUCT_ENABLED,
    apply_native_barge_in_stability_guard,
)
from .lifecycle import ApplicationLifecycle
from .notes import (
    DatabaseExecutor,
    MigrationResult,
    NoteCommandService,
    NoteQueryService,
    SqlAlchemyNoteRepository,
    TagCatalog,
    TagCatalogService,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
    prepare_gate1_local_data,
)
from .notes.sqlalchemy_repository import SessionFactory
from .ui import NoteListModel, NotesViewModel
from .ui import NotesUiCommandAdapter
from .ui.assistant_view_model import AssistantViewModel


@dataclass(slots=True)
class NotesRuntime:
    database_engine: Engine
    session_factory: SessionFactory
    database_executor: DatabaseExecutor
    note_repository: SqlAlchemyNoteRepository
    note_command_service: NoteCommandService
    note_query_service: NoteQueryService


@dataclass(slots=True)
class AssistantRuntime:
    config_store: RuntimeConfigStore
    preferences_store: AssistantPreferencesStore
    identity_manager: DeviceIdentityManager
    audio_session_supervisor: AudioSessionSupervisor
    audio_engine: AssistantAudioEngine
    offline_kws: OfflineKwsCoordinator
    acoustic_barge_in: AcousticBargeInCoordinator | None
    mcp_coordinator: McpCoordinator
    controller: AssistantController
    view_model: AssistantViewModel


@dataclass(slots=True)
class ApplicationContext:
    app: QGuiApplication
    engine: QQmlApplicationEngine
    paths: AppPaths
    lifecycle: ApplicationLifecycle
    migration_result: MigrationResult
    tag_catalog: TagCatalog
    tag_catalog_service: TagCatalogService
    notes_runtime: NotesRuntime
    assistant_runtime: AssistantRuntime
    notes_view_model: NotesViewModel
    notes_list_model: NoteListModel
    deleted_notes_list_model: NoteListModel
    ui_command_bus: UiCommandBus
    ui_command_adapter: NotesUiCommandAdapter
    mcp_tool_executor: Gate53ToolExecutor

    @property
    def database_engine(self) -> Engine:
        return self.notes_runtime.database_engine

    @property
    def session_factory(self) -> SessionFactory:
        return self.notes_runtime.session_factory

    @property
    def database_executor(self) -> DatabaseExecutor:
        return self.notes_runtime.database_executor

    @property
    def note_repository(self) -> SqlAlchemyNoteRepository:
        return self.notes_runtime.note_repository

    @property
    def note_command_service(self) -> NoteCommandService:
        return self.notes_runtime.note_command_service

    @property
    def note_query_service(self) -> NoteQueryService:
        return self.notes_runtime.note_query_service

    @property
    def assistant_controller(self) -> AssistantController:
        return self.assistant_runtime.controller

    @property
    def assistant_view_model(self) -> AssistantViewModel:
        return self.assistant_runtime.view_model


def create_event_loop(app: QGuiApplication) -> QEventLoop:
    return QEventLoop(app)


def resolve_worktree_root(explicit_root: str | Path | None = None) -> Path:
    if explicit_root is not None:
        return Path(explicit_root).expanduser().resolve()

    source_path = Path(__file__).resolve()
    for candidate in source_path.parents:
        if (candidate / "pc-app-build" / "pyproject.toml").is_file():
            return candidate
    return Path.cwd().resolve()


def create_notes_runtime(paths: AppPaths) -> NotesRuntime:
    database_engine = create_sqlite_engine(paths.notes_db)
    try:
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
    except Exception:
        database_engine.dispose()
        raise

    return NotesRuntime(
        database_engine=database_engine,
        session_factory=session_factory,
        database_executor=database_executor,
        note_repository=note_repository,
        note_command_service=note_command_service,
        note_query_service=note_query_service,
    )


def create_assistant_runtime(
    paths: AppPaths,
    *,
    mcp_coordinator: McpCoordinator | None = None,
) -> AssistantRuntime:
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    preferences_store = AssistantPreferencesStore(paths.assistant_preferences)
    preferences = preferences_store.load()
    # Gate 6.3/6.4 wired an experimental in-process WebRTC APM capture monitor
    # into the production playback callback.  On Windows the native PyAudio/APM
    # lifetime can race with playback/session teardown and terminate the whole
    # process without a Python exception.  Fail closed until the monitor is
    # isolated or its native teardown has real soak evidence.  Persisting the
    # rollback is intentional: an already-enabled preference must not reactivate
    # the unstable path after an application restart.
    preferences = apply_native_barge_in_stability_guard(preferences_store, preferences)
    legacy_source = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=legacy_source.load,
    )
    clock = SystemRuntimeClock()
    config_provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    coordinator = mcp_coordinator or McpCoordinator()
    audio_session_supervisor = AudioSessionSupervisor(preferences_store)
    playback_coordinator = PlaybackCoordinator(
        clock_ns=clock.now_ns,
        output_plan_provider=audio_session_supervisor.output_plan,
        playback_activity_sink=audio_session_supervisor.set_playback_activity,
    )
    transport = RuntimeTransportRouter(
        fake_transport=McpScriptedFakeTransport(mcp_coordinator=coordinator),
        real_transport=RealWebSocketTransport(
            config_provider=config_provider,
            clock=clock,
            mcp_coordinator=coordinator,
            playback_coordinator=playback_coordinator,
        ),
    )
    disabled_state = AssistantState.disabled(now_ns=clock.now_ns())
    initial_state = replace(
        disabled_state,
        conversation=replace(
            disabled_state.conversation,
            preferred_voice_mode=preferences.voice_interaction_mode,
            streaming_idle_timeout_ms=preferences.streaming_idle_timeout_ms,
            streaming_barge_in_enabled=preferences.streaming_barge_in_enabled,
        ),
    )
    audio_engine = AssistantAudioEngine(
        capture=audio_session_supervisor.capture_adapter,
        encoder_factory=PyAvOpusEncoder,
    )
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(ReconnectPolicy()),
        clock=clock,
        initial_state=initial_state,
        identity_manager=identity_manager,
        fake_activation_client=FakeActivationClient(
            config_store=config_store,
            identity_manager=identity_manager,
        ),
        real_activation_client=RealOtaActivationClient(
            config_store=config_store,
            identity_manager=identity_manager,
        ),
        preferences_store=preferences_store,
        audio_engine=audio_engine,
        microphone_coordinator=audio_session_supervisor.microphone_coordinator,
    )
    offline_kws = OfflineKwsCoordinator(
        controller,
        preferences_store,
        audio_session_supervisor,
        KwsModelRegistry(paths.models_dir / "kws"),
    )
    acoustic_barge_in = (
        AcousticBargeInCoordinator(
            controller,
            audio_session_supervisor,
            audio_engine,
            playback_coordinator,
        )
        if NATIVE_BARGE_IN_PRODUCT_ENABLED
        else None
    )

    async def interrupt_active_audio_for_route_change() -> None:
        await playback_coordinator.cancel("audio_route_changed")
        state = controller.state
        if state.conversation.streaming_session_active:
            await controller.stop_streaming_conversation("audio_route_changed")
        elif state.conversation.active_voice_turn_token is not None:
            await controller.stop_push_to_talk()

    audio_session_supervisor.bind_route_interruption_handler(
        interrupt_active_audio_for_route_change
    )
    return AssistantRuntime(
        config_store=config_store,
        preferences_store=preferences_store,
        identity_manager=identity_manager,
        audio_session_supervisor=audio_session_supervisor,
        audio_engine=audio_engine,
        offline_kws=offline_kws,
        acoustic_barge_in=acoustic_barge_in,
        mcp_coordinator=coordinator,
        controller=controller,
        view_model=AssistantViewModel(
            controller,
            preferences_store=preferences_store,
            initial_preferences=preferences,
            audio_session_supervisor=audio_session_supervisor,
            offline_kws=offline_kws,
            acoustic_barge_in=acoustic_barge_in,
        ),
    )


async def dispose_database_engine(database_engine: Engine) -> None:
    database_engine.dispose()


def create_application_context(
    app: QGuiApplication,
    *,
    data_root: str | Path | None = None,
    worktree_root: str | Path | None = None,
    migration_env: Mapping[str, str] | None = None,
) -> ApplicationContext:
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()

    resolved_worktree_root = resolve_worktree_root(worktree_root)
    migration_result = prepare_gate1_local_data(
        paths,
        worktree_root=resolved_worktree_root,
        env=migration_env,
    )

    tag_catalog = TagCatalog(paths.custom_tags)
    tag_catalog.load()

    notes_runtime = create_notes_runtime(paths)
    tag_catalog_service = TagCatalogService(tag_catalog, notes_runtime.note_query_service)
    notes_list_model = NoteListModel()
    deleted_notes_list_model = NoteListModel()
    notes_view_model = NotesViewModel(
        command_service=notes_runtime.note_command_service,
        query_service=notes_runtime.note_query_service,
        tag_catalog=tag_catalog_service,
        notes_model=notes_list_model,
        deleted_notes_model=deleted_notes_list_model,
    )
    ui_command_bus = UiCommandBus()
    ui_command_adapter = NotesUiCommandAdapter(notes_view_model)
    mcp_tool_executor = Gate53ToolExecutor(
        notes_runtime.note_query_service,
        notes_runtime.note_command_service,
        tag_catalog_service,
        ui_command_bus,
    )
    ui_command_adapter.bind_confirmation_actions(mcp_tool_executor)
    ui_command_bus.bind(ui_command_adapter)
    mcp_registry = ToolRegistry(executor=mcp_tool_executor)
    mcp_coordinator = McpCoordinator(mcp_registry)
    assistant_runtime = create_assistant_runtime(paths, mcp_coordinator=mcp_coordinator)

    lifecycle = ApplicationLifecycle()
    lifecycle.register_async_closer(
        "sqlalchemy-engine",
        lambda: dispose_database_engine(notes_runtime.database_engine),
    )
    lifecycle.register_async_closer(
        "database-executor",
        notes_runtime.database_executor.close,
    )
    lifecycle.register_async_closer(
        "tag-catalog-service",
        tag_catalog_service.close,
    )
    lifecycle.register_async_closer(
        "notes-view-model",
        notes_view_model.close,
    )
    lifecycle.register_async_closer(
        "mcp-confirmation-service",
        mcp_tool_executor.close,
    )
    lifecycle.register_async_closer(
        "ui-command-bus",
        ui_command_bus.close,
    )
    lifecycle.register_async_closer(
        "assistant-audio-supervisor",
        assistant_runtime.audio_session_supervisor.close,
    )
    lifecycle.register_async_closer(
        "assistant-controller",
        assistant_runtime.controller.shutdown,
    )
    lifecycle.register_async_closer(
        "assistant-view-model",
        assistant_runtime.view_model.close,
    )
    lifecycle.register_async_closer(
        "assistant-offline-kws",
        assistant_runtime.offline_kws.close,
    )
    if assistant_runtime.acoustic_barge_in is not None:
        lifecycle.register_async_closer(
            "assistant-acoustic-barge-in",
            assistant_runtime.acoustic_barge_in.close,
        )

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("notesViewModel", notes_view_model)
    context.setContextProperty("notesListModel", notes_list_model)
    context.setContextProperty("deletedNotesListModel", deleted_notes_list_model)
    context.setContextProperty("assistantViewModel", assistant_runtime.view_model)
    context.setContextProperty("uiCommandAdapter", ui_command_adapter)

    qml_file = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        notes_runtime.database_engine.dispose()
        raise RuntimeError(f"QML failed to load: {qml_file}")

    engine.quit.connect(app.quit)
    QTimer.singleShot(0, notes_view_model.loadAll)
    QTimer.singleShot(0, assistant_runtime.view_model.initialize)

    return ApplicationContext(
        app=app,
        engine=engine,
        paths=paths,
        lifecycle=lifecycle,
        migration_result=migration_result,
        tag_catalog=tag_catalog,
        tag_catalog_service=tag_catalog_service,
        notes_runtime=notes_runtime,
        assistant_runtime=assistant_runtime,
        notes_view_model=notes_view_model,
        notes_list_model=notes_list_model,
        deleted_notes_list_model=deleted_notes_list_model,
        ui_command_bus=ui_command_bus,
        ui_command_adapter=ui_command_adapter,
        mcp_tool_executor=mcp_tool_executor,
    )


def run_application(
    argv: Sequence[str] | None = None,
    *,
    data_root: str | Path | None = None,
    worktree_root: str | Path | None = None,
    migration_env: Mapping[str, str] | None = None,
) -> int:
    arguments = list(sys.argv if argv is None else argv)
    existing = QGuiApplication.instance()
    owns_app = existing is None
    app = existing if existing is not None else QGuiApplication(arguments)
    if not isinstance(app, QGuiApplication):
        raise RuntimeError("The existing Qt application is not a QGuiApplication.")

    app.setApplicationName("NoteAssistant")
    app.setOrganizationName("EHOME")
    app.setQuitOnLastWindowClosed(True)

    loop = create_event_loop(app)
    asyncio.set_event_loop(loop)

    try:
        context = create_application_context(
            app,
            data_root=data_root,
            worktree_root=worktree_root,
            migration_env=migration_env,
        )
    except Exception:
        loop.close()
        asyncio.set_event_loop(None)
        raise

    app.aboutToQuit.connect(loop.stop)

    try:
        with loop:
            loop.run_forever()
            loop.run_until_complete(context.lifecycle.shutdown(timeout_seconds=10.0))
    finally:
        asyncio.set_event_loop(None)
        if owns_app:
            context.engine.deleteLater()

    return 0
