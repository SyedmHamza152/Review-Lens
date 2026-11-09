"""LLM client for product intelligence (Ollama, open-source models).

Tries a local Ollama endpoint with a short timeout; if it is unreachable the
caller transparently falls back to the deterministic rule-based engine
(app/services/rule_engine.py). The chosen inference method is always reported
in the analysis payload — results are never presented as more authoritative
than their source.
"""
from __future__ import annotations

import json
import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def ollama_available() -> bool:
    try:
        r = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=settings.LLM_TIMEOUT_SECONDS)
        return r.status_code == 200
    except Exception:
        return False


def ollama_model_name() -> str:
    return settings.OLLAMA_MODEL


def generate_json(prompt: str, system: str | None = None) -> dict | None:
    """Ask Ollama for a JSON object. Returns None on any failure.

    The caller MUST fall back to the rule engine when None is returned.
    """
    if not ollama_available():
        return None
    try:
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt if not system else f"{system}\n\n{prompt}",
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2},
        }
        r = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload,
            timeout=max(settings.LLM_TIMEOUT_SECONDS, 30),
        )
        r.raise_for_status()
        text = r.json().get("response", "")
        return json.loads(text) if text else None
    except Exception as e:
        logger.warning("Ollama generation failed (%s) — using rule engine", e)
        return None
