import pytest

from ai_banking_customer_service.agent.language_detector import detect_language


def test_detect_language_recognizes_accented_portuguese() -> None:
    assert detect_language("Não reconheço esta cobrança") == "pt"


@pytest.mark.parametrize(
    "text",
    [
        "você pode ajudar?",
        "Vocês podem ajudar?",
        "Obrigado",
        "Obrigada",
        "Desculpe",
        "Meu cartão",
        "Essa cobrança",
        "Quero bloquear meu cartão",
        "Preciso bloquear minha conta",
    ],
)
def test_each_unambiguous_portuguese_indicator_is_sufficient(text: str) -> None:
    assert detect_language(text) == "pt"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \t\n",
        "Por favor, bloquee mi tarjeta",
        "María 123",
        "El texto naovalido menciona cartaozinho",
    ],
)
def test_ambiguous_or_non_token_text_defaults_to_spanish(text: str) -> None:
    assert detect_language(text) == "es"
