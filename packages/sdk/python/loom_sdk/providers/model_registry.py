"""
Model provider registry.

Resolves a `[model]` block in deepagents.toml (provider + name) into a
LangChain chat model instance. Each subagent specifies its own provider,
so different creatures in the clan can run on different models — the
unlock for Pillar 1's "pick your brain" choice in the agent builder.

Providers currently supported (lazy-imported so missing libs/keys don't
break startup):

  Subscription / commercial:
    anthropic:<model>      Claude (default)
    openai:<model>         GPT
    google:<model>         Gemini

  Open-weight, hosted (free-tier friendly):
    huggingface:<model>    HF Inference Providers
    together:<model>       Together AI
    groq:<model>           Groq

  Open-weight, local:
    ollama:<model>         Local Ollama (no API key)

Adding a new provider: extend `_RESOLVERS` with a callable that takes
the model name + kwargs and returns a `BaseChatModel`.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel


def _anthropic(name: str, **kwargs: Any) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=name, **kwargs)


def _openai(name: str, **kwargs: Any) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=name, **kwargs)


def _google(name: str, **kwargs: Any) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=name, **kwargs)


def _huggingface(name: str, **kwargs: Any) -> BaseChatModel:
    """HF Inference Providers — the unified API across many open-weight models.
    Set HUGGINGFACEHUB_API_TOKEN (or HF_TOKEN) in env. Free tier exists."""
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    endpoint = HuggingFaceEndpoint(
        repo_id=name,
        task="text-generation",
        max_new_tokens=kwargs.pop("max_tokens", 2048),
        **kwargs,
    )
    return ChatHuggingFace(llm=endpoint)


def _together(name: str, **kwargs: Any) -> BaseChatModel:
    from langchain_together import ChatTogether

    return ChatTogether(model=name, **kwargs)


def _groq(name: str, **kwargs: Any) -> BaseChatModel:
    from langchain_groq import ChatGroq

    return ChatGroq(model=name, **kwargs)


def _ollama(name: str, **kwargs: Any) -> BaseChatModel:
    """Local OR remote Ollama. Set OLLAMA_BASE_URL to a tunneled / Docker Cloud /
    VPS endpoint to point a hosted clan at your own hardware. If the endpoint is
    auth-protected (recommended for any non-localhost URL), set OLLAMA_AUTH_HEADER
    (e.g. "Bearer <secret>") and it'll be sent on every request via client_kwargs.
    See: docs concept "BYO personal Ollama"."""
    from langchain_ollama import ChatOllama

    base_url = kwargs.pop("base_url", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    auth_header = kwargs.pop("auth_header", os.environ.get("OLLAMA_AUTH_HEADER"))
    if auth_header:
        client_kwargs = kwargs.pop("client_kwargs", {}) or {}
        headers = dict(client_kwargs.get("headers") or {})
        headers.setdefault("Authorization", auth_header)
        client_kwargs["headers"] = headers
        kwargs["client_kwargs"] = client_kwargs
    return ChatOllama(model=name, base_url=base_url, **kwargs)


_RESOLVERS: dict[str, Callable[..., BaseChatModel]] = {
    "anthropic": _anthropic,
    "openai": _openai,
    "google": _google,
    "huggingface": _huggingface,
    "hf": _huggingface,  # alias
    "together": _together,
    "groq": _groq,
    "ollama": _ollama,
}


def resolve_model(model_cfg: dict[str, Any]) -> BaseChatModel:
    """Translate the [model] block in a deepagents.toml into a LangChain
    chat model instance.

    Expected config shape:
        provider: str   # one of the keys in _RESOLVERS (case-insensitive)
        name: str       # the model identifier, e.g. "claude-opus-4-7"
        ...             # extra kwargs passed to the provider class
    """
    provider = (model_cfg.get("provider") or "anthropic").lower()
    name = model_cfg.get("name")
    if not name:
        raise ValueError(
            f"model.name missing for provider {provider!r} in deepagents.toml"
        )

    resolver = _RESOLVERS.get(provider)
    if not resolver:
        raise ValueError(
            f"Unknown model provider {provider!r}. "
            f"Supported: {sorted(_RESOLVERS.keys())}. "
            f"To add a new provider, extend platform/api/model_registry.py."
        )

    extra = {k: v for k, v in model_cfg.items() if k not in ("provider", "name")}
    try:
        return resolver(name, **extra)
    except ImportError as e:
        raise ImportError(
            f"Provider {provider!r} requires an extra package that isn't installed. "
            f"Add it to platform/requirements.txt. Original error: {e}"
        ) from e


def supported_providers() -> list[str]:
    """For documentation / UI dropdowns."""
    return sorted({"anthropic", "openai", "google", "huggingface", "together", "groq", "ollama"})


# Recommended starter models per provider — used by the agent-builder UI
# (Pillar 1) when the user picks a provider; we suggest the smartest cheap
# model that's been tested with deepagents.
RECOMMENDED_STARTERS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-5.2",
    "google": "gemini-2.5-flash",
    "huggingface": "Qwen/Qwen3-32B-Instruct",
    "together": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1:8b",
}
