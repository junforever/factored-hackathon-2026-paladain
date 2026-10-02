import json

import pytest

from ai_banking_customer_service.agent.signal_parser import (
    parse_orchestration_signal,
)


def test_parse_orchestration_signal_accepts_abstention_object() -> None:
    signal = '{"orchestration_signal":"abstention","reason":"insufficient data"}'

    assert parse_orchestration_signal(signal) == {
        "orchestration_signal": "abstention",
        "reason": "insufficient data",
    }


def test_parse_orchestration_signal_accepts_whitespace_around_clarification() -> None:
    signal = (
        ' \n {"orchestration_signal":"clarification","question":"  Which charge?  "}\t '
    )

    assert parse_orchestration_signal(signal) == {
        "orchestration_signal": "clarification",
        "question": "  Which charge?  ",
    }


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"orchestration_signal":"unknown","reason":"why"}',
        '{"orchestration_signal":[],"reason":"why"}',
        '{"orchestration_signal":"abstention","reason":""}',
        '{"orchestration_signal":"abstention","reason":"   "}',
        '{"orchestration_signal":"abstention","reason":1}',
        '{"orchestration_signal":"clarification","question":null}',
        ('{"orchestration_signal":"clarification","question":"Which?","extra":true}'),
        '{"orchestration_signal":"abstention","question":"Wrong field"}',
        '{"orchestration_signal":"clarification","question":"Which?"} suffix',
        (
            '{"orchestration_signal":"clarification","question":"Which?"}'
            '{"orchestration_signal":"abstention","reason":"none"}'
        ),
        '```json\n{"orchestration_signal":"abstention","reason":"none"}\n```',
    ],
)
def test_parse_orchestration_signal_rejects_non_exact_signals(text: str) -> None:
    assert parse_orchestration_signal(text) is None


def test_parse_orchestration_signal_enforces_500_character_limit() -> None:
    accepted = json.dumps(
        {"orchestration_signal": "clarification", "question": "q" * 500}
    )
    rejected = json.dumps(
        {"orchestration_signal": "clarification", "question": "q" * 501}
    )

    assert parse_orchestration_signal(accepted) is not None
    assert parse_orchestration_signal(rejected) is None
