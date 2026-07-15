from __future__ import annotations

from app.assistant.effects import SendText
from app.assistant.events import (
    AssistantTextReceived,
    ClientTextSent,
    ConnectRequested,
    EnableRequested,
    ServerHelloReceived,
    TextSubmitted,
    TextTurnCompleted,
    TtsStateReceived,
    UseRealRuntimeRequested,
)
from app.assistant.state import AssistantPhase, AssistantState
from app.assistant.state_machine import ConversationStateMachine


def _connected_real(machine: ConversationStateMachine) -> AssistantState:
    state = machine.reduce(AssistantState.disabled(now_ns=1), EnableRequested(at_ns=2)).state
    state = machine.reduce(state, UseRealRuntimeRequested(at_ns=3)).state
    opening = machine.reduce(state, ConnectRequested(at_ns=4)).state
    return machine.reduce(
        opening,
        ServerHelloReceived(
            at_ns=5,
            generation=opening.connection.connection_generation,
            session_id="session-real",
        ),
    ).state


def test_text_submission_allocates_turn_token_and_rejects_parallel_turn() -> None:
    machine = ConversationStateMachine()
    connected = _connected_real(machine)
    submitted = machine.reduce(connected, TextSubmitted(at_ns=10, text="  你好  "))

    assert submitted.state.phase is AssistantPhase.THINKING
    assert submitted.state.conversation.active_text_turn_token == 1
    assert submitted.state.conversation.last_user_text == "你好"
    assert submitted.effects == (
        SendText(
            generation=connected.connection.connection_generation,
            turn_token=1,
            text="你好",
        ),
    )

    rejected = machine.reduce(submitted.state, TextSubmitted(at_ns=11, text="第二条"))
    assert rejected.state.error is not None
    assert rejected.state.error.code == "text_turn_in_progress"
    assert rejected.effects == ()


def test_product_transcript_separates_stt_llm_text_and_tts() -> None:
    machine = ConversationStateMachine()
    state = machine.reduce(_connected_real(machine), TextSubmitted(at_ns=10, text="问题")).state
    generation = state.connection.connection_generation

    state = machine.reduce(
        state,
        ClientTextSent(
            at_ns=11,
            generation=generation,
            turn_token=1,
            raw_json_redacted='{"type":"listen"}',
        ),
    ).state
    state = machine.reduce(
        state,
        AssistantTextReceived(
            at_ns=12,
            generation=generation,
            turn_token=1,
            source_type="stt",
            text="语音识别文本",
            session_id="session-real",
        ),
    ).state
    assert state.conversation.last_user_text == "问题"
    assert state.conversation.last_stt_text == "语音识别文本"
    assert state.conversation.last_assistant_text is None

    state = machine.reduce(
        state,
        AssistantTextReceived(
            at_ns=13,
            generation=generation,
            turn_token=1,
            source_type="llm",
            text="😊",
            session_id="session-real",
        ),
    ).state
    assert state.conversation.last_assistant_text is None

    state = machine.reduce(
        state,
        AssistantTextReceived(
            at_ns=14,
            generation=generation,
            turn_token=1,
            source_type="text",
            text="真实",
            session_id="session-real",
        ),
    ).state
    state = machine.reduce(
        state,
        TtsStateReceived(
            at_ns=15,
            generation=generation,
            turn_token=1,
            state="sentence_start",
            text="实文本回复",
            session_id="session-real",
        ),
    ).state

    assert state.conversation.last_assistant_text == "真实文本回复"
    assert state.conversation.last_assistant_source_type == "tts"
    assert state.diagnostics.gate_real_text_verified is True
    assert state.phase is AssistantPhase.CONNECTED


def test_late_turn_text_is_archived_without_overwriting_transcript() -> None:
    machine = ConversationStateMachine()
    state = machine.reduce(_connected_real(machine), TextSubmitted(at_ns=10, text="问题")).state
    generation = state.connection.connection_generation
    state = machine.reduce(
        state,
        AssistantTextReceived(
            at_ns=11,
            generation=generation,
            turn_token=1,
            source_type="text",
            text="当前回复",
            session_id="session-real",
        ),
    ).state
    state = machine.reduce(
        state,
        TextTurnCompleted(
            at_ns=12,
            generation=generation,
            turn_token=1,
            reason="settled",
            had_assistant_text=True,
        ),
    ).state
    late = machine.reduce(
        state,
        AssistantTextReceived(
            at_ns=13,
            generation=generation,
            turn_token=1,
            source_type="text",
            text="迟到覆盖",
            session_id="session-real",
        ),
    ).state

    assert late.conversation.last_assistant_text == "当前回复"
    assert late.conversation.late_text_event_count == 1
    assert late.protocol.last_protocol_event == "LateAssistantText:text"
