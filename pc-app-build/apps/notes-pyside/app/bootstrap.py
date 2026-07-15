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
    PersistedConnectionConfigProvider,
    RealOtaActivationClient,
    RealWebSocketTransport,
    ReconnectPolicy,
    RuntimeConfigStore,
    RuntimeTransportRouter,
)
from .assistant.audio import (
    AssistantAudioEngine,
    MicrophoneLeaseCoordinator,
    PyAudioCaptureAdapter,
    PyAvOpusEncoder,
)
from .assistant.controller import SystemRuntimeClock
from .assistant.identity import LegacyPyXiaozhiIdentitySource
from .assistant.network import ScriptedFakeTransport
from .lifecycle import ApplicationLifecycle
from .notes import (
    DatabaseExecutor,
    MigrationResult,
    NoteCommandService,
    NoteQueryService,
    SqlAlchemyNoteRepository,
    TagCatalog,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
    prepare_gate1_local_data,
)
from .notes.sqlalchemy_repository import SessionFactory
from .ui import NoteListModel, NotesViewModel
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
    audio_engine: AssistantAudioEngine
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
    notes_runtime: NotesRuntime
    assistant_runtime: AssistantRuntime
    notes_view_model: NotesViewModel
    notes_list_model: NoteListModel
    deleted_notes_list_model: NoteListModel

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


def create_assistant_runtime(paths: AppPaths) -> AssistantRuntime:
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    preferences_store = AssistantPreferencesStore(paths.assistant_preferences)
    preferences = preferences_store.load()
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
    transport = RuntimeTransportRouter(
        fake_transport=ScriptedFakeTransport(),
        real_transport=RealWebSocketTransport(
            config_provider=config_provider,
            clock=clock,
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
        capture=PyAudioCaptureAdapter(),
        encoder_factory=PyAvOpusEncoder,
    )
    microphone_coordinator = MicrophoneLeaseCoordinator()
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
        microphone_coordinator=microphone_coordinator,
    )
    return AssistantRuntime(
        config_store=config_store,
        preferences_store=preferences_store,
        identity_manager=identity_manager,
        audio_engine=audio_engine,
        controller=controller,
        view_model=AssistantViewModel(
            controller,
            preferences_store=preferences_store,
            initial_preferences=preferences,
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
    assistant_runtime = create_assistant_runtime(paths)
    notes_list_model = NoteListModel()
    deleted_notes_list_model = NoteListModel()
    notes_view_model = NotesViewModel(
        command_service=notes_runtime.note_command_service,
        query_service=notes_runtime.note_query_service,
        tag_catalog=tag_catalog,
        notes_model=notes_list_model,
        deleted_notes_model=deleted_notes_list_model,
    )

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
        "notes-view-model",
        notes_view_model.close,
    )
    lifecycle.register_async_closer(
        "assistant-controller",
        assistant_runtime.controller.shutdown,
    )
    lifecycle.register_async_closer(
        "assistant-view-model",
        assistant_runtime.view_model.close,
    )

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("notesViewModel", notes_view_model)
    context.setContextProperty("notesListModel", notes_list_model)
    context.setContextProperty("deletedNotesListModel", deleted_notes_list_model)
    context.setContextProperty("assistantViewModel", assistant_runtime.view_model)

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
        notes_runtime=notes_runtime,
        assistant_runtime=assistant_runtime,
        notes_view_model=notes_view_model,
        notes_list_model=notes_list_model,
        deleted_notes_list_model=deleted_notes_list_model,
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
