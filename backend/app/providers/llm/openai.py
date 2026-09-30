"""OpenAI chat-completions provider for explanation generation."""
from __future__ import annotations

from app.providers.llm.keygateway import KeyGatewayLLMProvider


class OpenAILLMProvider(KeyGatewayLLMProvider):
    """Use the configured OpenAI-compatible chat-completions endpoint.

    The shared transport already implements bearer authentication, configured
    timeout/retries, response parsing, and provider-failure reporting. Keeping
    this as a thin specialization leaves the LLM call restricted to the
    existing explainability stage.
    """

    name = "openai"
