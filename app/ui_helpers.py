"""Localized validation helpers for the Chainlit presentation layer."""

import logging
from typing import Literal

from ai_banking_customer_service.agent.language_detector import (
    detect_language as detect_language,
)

Language = Literal["es", "pt"]
MAX_MESSAGE_CHARS = 4000

logger = logging.getLogger(__name__)

UI_TEMPLATES: dict[str, dict[Language, str]] = {
    "empty_input": {
        "es": "Por favor ingresa un mensaje.",
        "pt": "Por favor insira uma mensagem.",
    },
    "too_long_input": {
        "es": "El mensaje es demasiado largo. Por favor acórtalo.",
        "pt": "A mensagem é muito longa. Por favor encurte-a.",
    },
    "internal_error": {
        "es": "Ocurrió un error interno. Por favor intenta de nuevo.",
        "pt": "Ocorreu um erro interno. Por favor tente novamente.",
    },
    "timeout_exceeded": {
        "es": (
            "La solicitud superó el tiempo de espera. La operación todavía está "
            "finalizando. Por favor espera el resultado antes de reintentar."
        ),
        "pt": (
            "A solicitação excedeu o tempo de espera. A operação ainda está "
            "finalizando. Por favor aguarde o resultado antes de tentar novamente."
        ),
    },
    "turn_in_progress": {
        "es": "Hay una solicitud en curso. Por favor espera a que termine.",
        "pt": "Há uma solicitação em andamento. Por favor aguarde até que termine.",
    },
    "reconciliation_in_progress": {
        "es": "El resultado anterior se está mostrando. Por favor espera.",
        "pt": "O resultado anterior está sendo exibido. Por favor aguarde.",
    },
    "render_error": {
        "es": "Error al mostrar el mensaje.",
        "pt": "Erro ao exibir a mensagem.",
    },
    "escalation_prefix": {
        "es": "🔴 Escalamiento: ",
        "pt": "🔴 Escalonamento: ",
    },
}


def get_template(name: str, language: Language) -> str:
    """Return exact localized UI copy for a resolved language."""
    return UI_TEMPLATES[name][language]


def validate_input(text: str, language: Language) -> str | None:
    """Return localized validation copy, or ``None`` when input is accepted."""
    if not isinstance(text, str) or not text.strip():
        logger.warning("EMPTY_INPUT")
        return get_template("empty_input", language)
    if len(text) > MAX_MESSAGE_CHARS:
        logger.warning("TOO_LONG_INPUT")
        return get_template("too_long_input", language)
    return None
