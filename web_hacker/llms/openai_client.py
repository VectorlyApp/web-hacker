"""
web_hacker/llms/openai_client.py

OpenAI-specific LLM client implementation.
"""

from typing import Any, TypeVar

from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel

from data_models.llms import LLMModel
from llms.abstract_llm_vendor_client import AbstractLLMVendorClient
from config import Config
from utils.logger import get_logger

logger = get_logger(name=__name__)


T = TypeVar("T", bound=BaseModel)


class OpenAIClient(AbstractLLMVendorClient):
    """
    OpenAI-specific implementation of the LLM vendor client.

    Uses the OpenAI Python SDK for chat completions, structured outputs,
    and function calling.
    """

    # Magic methods ________________________________________________________________________________________________________

    def __init__(self, model: LLMModel) -> None:
        super().__init__(model)
        self._client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self._async_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        logger.debug("Initialized OpenAIClient with model: %s", model)

    # Private methods ______________________________________________________________________________________________________

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        """
        Build the messages list for OpenAI chat completions.

        Args:
            prompt: The user prompt/message.
            system_prompt: Optional system prompt for context.

        Returns:
            The messages list.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    # Public methods _______________________________________________________________________________________________________

    ## Tool management

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
    ) -> None:
        """Register a tool in OpenAI's function calling format."""
        logger.debug("Registering OpenAI tool: %s", name)
        self._tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        })

    ## Text generation

    def get_text_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Get a text response synchronously using OpenAI chat completions."""
        messages = self._build_messages(prompt, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": messages,
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature),
        }
        if self._tools:
            kwargs["tools"] = self._tools

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def get_text_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Get a text response asynchronously using OpenAI chat completions."""
        messages = self._build_messages(prompt, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": messages,
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature),
        }
        if self._tools:
            kwargs["tools"] = self._tools

        response = await self._async_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    ## Structured responses

    def get_structured_response_sync(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        """Get a structured response using OpenAI's native response_format parsing."""
        messages = self._build_messages(prompt, system_prompt)

        response = self._client.beta.chat.completions.parse(
            model=self.model.value,
            messages=messages,
            response_format=response_model,
            max_tokens=self._resolve_max_tokens(max_tokens),
            temperature=self._resolve_temperature(temperature, structured=True),
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Failed to parse structured response from OpenAI")
        return parsed

    async def get_structured_response_async(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        """Get a structured response asynchronously using OpenAI's native response_format parsing."""
        messages = self._build_messages(prompt, system_prompt)

        response = await self._async_client.beta.chat.completions.parse(
            model=self.model.value,
            messages=messages,
            response_format=response_model,
            max_tokens=self._resolve_max_tokens(max_tokens),
            temperature=self._resolve_temperature(temperature, structured=True),
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Failed to parse structured response from OpenAI")
        return parsed
