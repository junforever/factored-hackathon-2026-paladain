from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from strands.hooks import (
    AfterToolCallEvent,
    BeforeToolCallEvent,
    HookOrder,
    HookProvider,
    HookRegistry,
)

from ai_banking_customer_service.agent.result_capture import (
    NormalizedToolResult,
    ResultCaptureHooks,
)


def _tool_use(
    *,
    tool_use_id: object = "tool-use-1",
    name: object = "block_card",
    tool_input: object = None,
) -> dict:
    return {
        "toolUseId": tool_use_id,
        "name": name,
        "input": (
            {"complaint_id": "CMP-1", "confirmed_by_customer": True}
            if tool_input is None
            else tool_input
        ),
    }


def _before_event(
    tool_use: object,
    *,
    state: dict | None = None,
    cancel_tool: bool | str = False,
) -> BeforeToolCallEvent:
    return BeforeToolCallEvent(
        agent=SimpleNamespace(),
        selected_tool=None,
        tool_use=tool_use,
        invocation_state={} if state is None else state,
        cancel_tool=cancel_tool,
    )


def _after_event(
    tool_use: object,
    *,
    result: object = None,
    state: dict | None = None,
    exception: Exception | None = None,
    cancel_message: str | None = None,
    duration: float | None = None,
    retry: object = False,
) -> AfterToolCallEvent:
    return AfterToolCallEvent(
        agent=SimpleNamespace(),
        selected_tool=None,
        tool_use=tool_use,
        invocation_state={} if state is None else state,
        result=(
            {"toolUseId": "tool-use-1", "status": "success", "content": []}
            if result is None
            else result
        ),
        exception=exception,
        cancel_message=cancel_message,
        duration=duration,
        retry=retry,
    )


def test_public_contract_and_exact_hook_registration() -> None:
    assert issubclass(ResultCaptureHooks, HookProvider)
    assert [field.name for field in fields(NormalizedToolResult)] == [
        "tool_use_id",
        "tool_name",
        "tool_args",
        "status",
        "content",
        "exception",
        "cancel_message",
        "duration_ms",
        "blocked_before_execution",
        "retry_requested",
        "authorization_verified",
    ]
    result = NormalizedToolResult(
        "id", "name", {}, "error", None, None, None, None, False, False, False
    )
    with pytest.raises(FrozenInstanceError):
        result.status = "success"  # type: ignore[misc]

    capture = ResultCaptureHooks()
    registry = Mock(spec=HookRegistry)
    capture.register_hooks(registry)

    assert registry.add_callback.call_args_list == [
        call(
            BeforeToolCallEvent,
            capture.before_tool_call,
            order=HookOrder.SDK_LAST,
        ),
        call(AfterToolCallEvent, capture.after_tool_call),
    ]


def test_captures_one_successful_tool_attempt_and_normalized_result() -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use()
    state = {
        "tool_governance": {
            "tool-use-1": {
                "action": "allow",
                "event_id": "gating-1",
                "authorization_result": "allowed",
                "authorization_reason_code": "authorized",
                "authorization_verified": True,
            }
        }
    }
    capture.before_tool_call(_before_event(tool_use, state=state))
    capture.after_tool_call(
        _after_event(
            tool_use,
            state=state,
            result={
                "toolUseId": "tool-use-1",
                "status": "success",
                "content": [
                    {
                        "json": {
                            "action": "block_card",
                            "executed": True,
                            "verification": "confirmed_blocked",
                        }
                    }
                ],
            },
            duration=0.0129,
        )
    )

    attempts = capture.snapshot_attempts()
    assert len(attempts) == 1
    assert (
        attempts[0].tool_use_id,
        attempts[0].tool_name,
        attempts[0].tool_args,
        attempts[0].blocked_before_execution,
        attempts[0].authorization_verified,
    ) == ("tool-use-1", "block_card", tool_use["input"], False, True)
    assert capture.snapshot_results() == (
        NormalizedToolResult(
            tool_use_id="tool-use-1",
            tool_name="block_card",
            tool_args=tool_use["input"],
            status="success",
            content={
                "action": "block_card",
                "executed": True,
                "verification": "confirmed_blocked",
            },
            exception=None,
            cancel_message=None,
            duration_ms=12,
            blocked_before_execution=False,
            retry_requested=False,
            authorization_verified=True,
        ),
    )


def test_successful_action_dict_serialized_as_strands_text_is_normalized() -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use()
    capture.before_tool_call(_before_event(tool_use))
    capture.after_tool_call(
        _after_event(
            tool_use,
            result={
                "toolUseId": "tool-use-1",
                "status": "success",
                "content": [
                    {
                        "text": (
                            '{"action": "block_card", "executed": true, '
                            '"verification": "confirmed_blocked"}'
                        )
                    }
                ],
            },
        )
    )

    assert capture.snapshot_results()[0].content == {
        "action": "block_card",
        "executed": True,
        "verification": "confirmed_blocked",
    }


@pytest.mark.parametrize(
    ("status", "content", "expected_status", "expected_content"),
    [
        ("error", [{"text": "failed"}], "error", "failed"),
        ("success", [{"text": "[1, 2]"}], "success", "[1, 2]"),
        ("success", [{"text": "7"}], "success", "7"),
        (
            "success",
            [{"text": "first"}, {"json": {"winner": True}}],
            "success",
            {"winner": True},
        ),
        ("unknown", [{"image": {}}], "error", None),
        (None, "not-a-list", "error", None),
    ],
)
def test_result_status_and_content_are_normalized_conservatively(
    status: object,
    content: object,
    expected_status: str,
    expected_content: object,
) -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use(name="get_dispute_context")
    capture.before_tool_call(_before_event(tool_use))
    capture.after_tool_call(
        _after_event(
            tool_use,
            result={"status": status, "content": content, "toolUseId": "tool-use-1"},
        )
    )

    result = capture.snapshot_results()[0]
    assert result.status == expected_status
    assert result.content == expected_content


@pytest.mark.parametrize(
    ("tool_use", "expected"),
    [
        (None, ("", "unknown", {})),
        ({"toolUseId": 7, "name": [], "input": "bad"}, ("", "unknown", {})),
        ({"toolUseId": " ", "name": " ", "input": []}, ("", "unknown", {})),
    ],
)
def test_malformed_tool_identity_is_retained_without_invented_correlation(
    tool_use: object,
    expected: tuple[str, str, dict],
) -> None:
    capture = ResultCaptureHooks()
    capture.before_tool_call(_before_event(tool_use))
    capture.after_tool_call(_after_event(tool_use, result={}))

    attempt = capture.snapshot_attempts()[0]
    result = capture.snapshot_results()[0]
    assert (attempt.tool_use_id, attempt.tool_name, attempt.tool_args) == expected
    assert (result.tool_use_id, result.tool_name, result.tool_args) == expected


@pytest.mark.parametrize(
    ("state", "cancel_tool", "expected"),
    [
        (
            {"tool_governance": {"tool-use-1": {"action": "block"}}},
            "governance:block",
            True,
        ),
        (
            {"tool_governance": {"tool-use-1": {"action": "allow"}}},
            "governance:block",
            False,
        ),
        ({"tool_governance": {"tool-use-1": {"action": "block"}}}, False, False),
        ({"tool_governance": []}, "governance:block", False),
    ],
)
def test_blocked_before_execution_requires_both_prior_cancel_and_governance_evidence(
    state: dict,
    cancel_tool: bool | str,
    expected: bool,
) -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use()
    capture.before_tool_call(
        _before_event(tool_use, state=state, cancel_tool=cancel_tool)
    )
    state.clear()
    capture.after_tool_call(
        _after_event(
            tool_use,
            state=state,
            result={"status": "error", "content": [{"text": "cancelled"}]},
            cancel_message="cancelled",
        )
    )

    assert capture.snapshot_results()[0].blocked_before_execution is expected


@pytest.mark.parametrize(
    "authorization",
    [
        {},
        {"authorization_verified": True},
        {
            "authorization_result": "allowed",
            "authorization_reason_code": "authorized",
            "authorization_verified": 1,
        },
        {
            "authorization_result": "denied",
            "authorization_reason_code": "product_not_authorized",
            "authorization_verified": True,
        },
    ],
)
def test_authorization_capture_requires_exact_bounded_allow_evidence(
    authorization: dict,
) -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use(name="get_dispute_context")
    state = {"tool_governance": {"tool-use-1": authorization}}

    capture.before_tool_call(_before_event(tool_use, state=state))
    state.clear()
    capture.after_tool_call(_after_event(tool_use, state=state))

    assert capture.snapshot_attempts()[0].authorization_verified is False
    assert capture.snapshot_results()[0].authorization_verified is False


@pytest.mark.parametrize(
    ("authorization", "expected"),
    [
        (
            {
                "authorization_result": "allowed",
                "authorization_reason_code": "authorized",
                "authorization_verified": True,
            },
            ("allowed", "authorized", True),
        ),
        (
            {
                "authorization_result": "denied",
                "authorization_reason_code": "not_authenticated",
                "authorization_verified": False,
            },
            ("denied", "not_authenticated", False),
        ),
        (
            {
                "authorization_result": "unavailable",
                "authorization_reason_code": "authorization_unavailable",
                "authorization_verified": False,
            },
            ("unavailable", "authorization_unavailable", False),
        ),
    ],
)
def test_capture_retains_only_bounded_authorization_for_the_occurrence(
    authorization: dict,
    expected: tuple[str, str, bool],
) -> None:
    capture = ResultCaptureHooks()
    state = {"tool_governance": {"tool-use-1": authorization}}

    capture.before_tool_call(_before_event(_tool_use(), state=state))

    attempt = capture.snapshot_attempts()[0]
    assert (
        attempt.authorization_result,
        attempt.authorization_reason_code,
        attempt.authorization_verified,
    ) == expected


def test_after_without_prior_attempt_cannot_claim_pre_execution_block() -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use()
    capture.after_tool_call(
        _after_event(
            tool_use,
            state={"tool_governance": {"tool-use-1": {"action": "block"}}},
            result={"status": "error", "content": []},
            cancel_message="governance:block",
        )
    )

    assert capture.snapshot_attempts() == ()
    assert capture.snapshot_results()[0].blocked_before_execution is False
    assert capture.snapshot_results()[0].authorization_verified is False


def test_exception_cancel_retry_and_block_evidence_coexist() -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use()
    capture.before_tool_call(
        _before_event(
            tool_use,
            state={"tool_governance": {"tool-use-1": {"action": "block"}}},
            cancel_tool="governance:block",
        )
    )
    capture.after_tool_call(
        _after_event(
            tool_use,
            result={"status": "success", "content": []},
            exception=RuntimeError("card 4111 1111 1111 1111 token=secret"),
            cancel_message="caller cancelled",
            duration=-0.25,
            retry=True,
        )
    )

    result = capture.snapshot_results()[0]
    assert result.exception == ("RuntimeError: card [REDACTED_PAN] [REDACTED_SECRET]")
    assert result.cancel_message == "caller cancelled"
    assert result.duration_ms == 0
    assert result.blocked_before_execution is True
    assert result.retry_requested is True


def test_retry_flag_is_boolean_evidence_not_a_truthy_counter() -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use()
    capture.before_tool_call(_before_event(tool_use))
    capture.after_tool_call(_after_event(tool_use, retry=1))

    assert capture.snapshot_results()[0].retry_requested is False


def test_duplicate_ids_remain_distinct_uncertainty_evidence() -> None:
    capture = ResultCaptureHooks()
    first = _tool_use(tool_input={"complaint_id": "CMP-1"})
    second = _tool_use(tool_input={"complaint_id": "CMP-2"})
    for tool_use in (first, second):
        capture.before_tool_call(_before_event(tool_use))
        capture.after_tool_call(
            _after_event(tool_use, result={"status": "error", "content": []})
        )

    assert [attempt.tool_use_id for attempt in capture.snapshot_attempts()] == [
        "tool-use-1",
        "tool-use-1",
    ]
    complaint_ids = [
        result.tool_args["complaint_id"] for result in capture.snapshot_results()
    ]
    assert complaint_ids == ["CMP-1", "CMP-2"]


def test_interleaved_duplicate_ids_keep_exact_attempt_evidence() -> None:
    capture = ResultCaptureHooks()
    allowed = _tool_use()
    blocked = _tool_use()
    allowed_state = {
        "tool_governance": {
            "tool-use-1": {
                "authorization_result": "allowed",
                "authorization_reason_code": "authorized",
                "authorization_verified": True,
            }
        }
    }
    capture.before_tool_call(_before_event(allowed, state=allowed_state))
    capture.before_tool_call(
        _before_event(
            blocked,
            state={
                "tool_governance": {
                    "tool-use-1": {
                        "action": "block",
                        "authorization_result": "denied",
                        "authorization_reason_code": "product_not_authorized",
                        "authorization_verified": False,
                    }
                }
            },
            cancel_tool="governance:block",
        )
    )

    capture.after_tool_call(
        _after_event(blocked, result={"status": "error", "content": []})
    )
    capture.after_tool_call(_after_event(allowed))

    evidence = [
        (result.blocked_before_execution, result.authorization_verified)
        for result in capture.snapshot_results()
    ]
    assert evidence == [(True, False), (False, True)]


def _authorized_state() -> dict:
    return {
        "tool_governance": {
            "tool-use-1": {
                "action": "allow",
                "authorization_result": "allowed",
                "authorization_reason_code": "authorized",
                "authorization_verified": True,
            }
        }
    }


def test_verified_missing_merchant_result_marks_invocation_local_state() -> None:
    capture = ResultCaptureHooks()
    state = _authorized_state()
    tool_use = _tool_use(name="get_dispute_context")

    capture.before_tool_call(_before_event(tool_use, state=state))
    capture.after_tool_call(
        _after_event(
            tool_use,
            state=state,
            result={
                "status": "success",
                "content": [{"json": {"merchant_name": None}}],
            },
        )
    )

    assert state["missing_merchant_verified"] is True


@pytest.mark.parametrize(
    ("name", "content", "status", "authorized", "retry"),
    [
        ("get_dispute_context", {"merchant_name": "Comercio"}, "success", True, False),
        (
            "get_dispute_context",
            {"merchant_name": None, "error": "bad"},
            "success",
            True,
            False,
        ),
        ("get_dispute_context", {"merchant_name": None}, "error", True, False),
        ("get_dispute_context", {"merchant_name": None}, "success", False, False),
        ("get_dispute_context", {"merchant_name": None}, "success", True, True),
        ("get_recent_transactions", {"merchant_name": None}, "success", True, False),
        ("get_dispute_context", "not-a-dict", "success", True, False),
    ],
)
def test_context_variants_do_not_mark_missing_merchant(
    name: str,
    content: object,
    status: str,
    authorized: bool,
    retry: bool,
) -> None:
    capture = ResultCaptureHooks()
    state = _authorized_state() if authorized else {}
    tool_use = _tool_use(name=name)

    capture.before_tool_call(_before_event(tool_use, state=state))
    capture.after_tool_call(
        _after_event(
            tool_use,
            state=state,
            result={"status": status, "content": [{"json": content}]},
            retry=retry,
        )
    )

    assert state.get("missing_merchant_verified") is not True


@pytest.mark.parametrize(
    "terminal_evidence",
    [
        {"exception": RuntimeError("provider failed")},
        {"cancel_message": "cancelled"},
    ],
)
def test_exception_or_cancellation_cannot_mark_missing_merchant(
    terminal_evidence: dict,
) -> None:
    capture = ResultCaptureHooks()
    state = _authorized_state()
    tool_use = _tool_use(name="get_dispute_context")
    capture.before_tool_call(_before_event(tool_use, state=state))

    capture.after_tool_call(
        _after_event(
            tool_use,
            state=state,
            result={
                "status": "success",
                "content": [{"json": {"merchant_name": None}}],
            },
            **terminal_evidence,
        )
    )

    assert state.get("missing_merchant_verified") is not True


def test_incomplete_context_attempt_never_marks_missing_merchant() -> None:
    capture = ResultCaptureHooks()
    state = _authorized_state()

    capture.before_tool_call(
        _before_event(_tool_use(name="get_dispute_context"), state=state)
    )

    assert state.get("missing_merchant_verified") is not True


def test_duplicate_context_attempt_clears_prior_missing_merchant_state() -> None:
    capture = ResultCaptureHooks()
    state = _authorized_state()
    first = _tool_use(name="get_dispute_context")
    result = {
        "status": "success",
        "content": [{"json": {"merchant_name": None}}],
    }
    capture.before_tool_call(_before_event(first, state=state))
    capture.after_tool_call(_after_event(first, state=state, result=result))
    assert state["missing_merchant_verified"] is True

    duplicate = _tool_use(name="get_dispute_context")
    capture.before_tool_call(_before_event(duplicate, state=state))

    assert state.get("missing_merchant_verified") is not True
    capture.after_tool_call(_after_event(duplicate, state=state, result=result))
    assert state.get("missing_merchant_verified") is not True


def test_snapshots_and_callback_inputs_are_deeply_isolated() -> None:
    capture = ResultCaptureHooks()
    tool_use = _tool_use(tool_input={"complaint_id": "CMP-1", "nested": {"value": 1}})
    payload = {"nested": {"value": 2}}
    capture.before_tool_call(_before_event(tool_use))
    capture.after_tool_call(
        _after_event(
            tool_use,
            result={"status": "success", "content": [{"json": payload}]},
        )
    )

    tool_use["input"]["nested"]["value"] = 99
    payload["nested"]["value"] = 99
    attempts = capture.snapshot_attempts()
    results = capture.snapshot_results()
    attempts[0].tool_args["nested"]["value"] = 77
    results[0].content["nested"]["value"] = 77

    assert capture.snapshot_attempts()[0].tool_args["nested"]["value"] == 1
    assert capture.snapshot_results()[0].content["nested"]["value"] == 2
