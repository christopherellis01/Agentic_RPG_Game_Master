from __future__ import annotations

import os
from dotenv import load_dotenv

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.litellm import LiteLLMProvider


load_dotenv()


def get_model(model_name: str = "claude-sonnet-4-6") -> OpenAIChatModel:
    api_key = os.getenv("CAP6640_API_KEY")
    if not api_key:
        raise ValueError("CAP6640_API_KEY not found in environment.")

    provider = LiteLLMProvider(
        api_key=api_key,
        api_base="https://litellm.6640.ucf.spencerlyon.com",
    )

    return OpenAIChatModel(model_name, provider=provider)