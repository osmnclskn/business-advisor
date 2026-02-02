from functools import lru_cache
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import get_settings

LLMProvider = Literal["openai", "anthropic", "google"]


@lru_cache()
def get_llm(
    provider: LLMProvider, model: str, temperature: float, max_tokens: int
) -> BaseChatModel:
    settings = get_settings()

    if provider == "openai":
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "anthropic":
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "google":
        return ChatGoogleGenerativeAI(
            api_key=settings.google_api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    else:
        raise ValueError(f"Desteklenmeyen provider: {provider}")


def get_peer_llm() -> BaseChatModel:
    """
    PeerAgent için GPT-5.1
    Düşük temperature (0.3) - tutarlı classification için.
    """
    return get_llm(provider="openai", model="gpt-5.1", temperature=0.3, max_tokens=1000)


def get_discovery_llm() -> BaseChatModel:
    """
    DiscoveryAgent için Claude 3.5 Sonnet.
    Orta temperature (0.7) - doğal soru üretimi için.
    Claude multi-turn conversation'da daha tutarlı context tutuyor.
    """
    return get_llm(
        provider="anthropic",
        model="claude-sonnet-4-5-20250929",
        temperature=0.7,
        max_tokens=1500,
    )


def get_structuring_llm() -> BaseChatModel:
    """
    StructuringAgent için Gemini 2.5 Flash.
    Düşük-orta temperature (0.5) - structured output için.
    Flash model hızlı ve maliyet etkin.
    """
    return get_llm(
        provider="google", model="gemini-2.5-flash", temperature=0.5, max_tokens=2000
    )

def get_action_llm() ->BaseChatModel:
    return get_llm(
        provider ="google", model="gemini-2.5-flash", temperature=0.6, max_tokens=20000
    )

def get_report_llm() -> BaseChatModel:
    return get_llm(
        provider="openai", model="gpt-5.1", temperature=0.4, max_tokens=5000
    )

def get_risk_llm() -> BaseChatModel:
    return get_llm(
        provider="anthropic",
        model="claude-sonnet-4-5-20250929",
        temperature=0.5,
        max_tokens=3000,
    )