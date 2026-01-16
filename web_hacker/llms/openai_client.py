"""
web_hacker/llms/openai_client.py

OpenAI-specific LLM client implementation.
"""

import json
from typing import Any, TypeVar

from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel

from web_hacker.data_models.chat import LLMChatResponse, LLMToolCall
from web_hacker.data_models.llms import LLMModel
from web_hacker.llms.abstract_llm_vendor_client import AbstractLLMVendorClient
from web_hacker.config import Config
from web_hacker.utils.logger import get_logger

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

    def _prepend_system_prompt(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        """
        Prepend system prompt to messages if provided.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system_prompt: Optional system prompt for context.

        Returns:
            Messages list with system prompt prepended if provided.
        """
        if system_prompt:
            return [{"role": "system", "content": system_prompt}] + messages
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
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Get a text response synchronously using OpenAI chat completions."""
        all_messages = self._prepend_system_prompt(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": all_messages,
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature),
        }
        if self._tools:
            kwargs["tools"] = self._tools

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def get_text_async(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Get a text response asynchronously using OpenAI chat completions."""
        all_messages = self._prepend_system_prompt(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": all_messages,
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
        messages: list[dict[str, str]],
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        """Get a structured response using OpenAI's native response_format parsing."""
        all_messages = self._prepend_system_prompt(messages, system_prompt)

        response = self._client.beta.chat.completions.parse(
            model=self.model.value,
            messages=all_messages,
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
        messages: list[dict[str, str]],
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        """Get a structured response asynchronously using OpenAI's native response_format parsing."""
        all_messages = self._prepend_system_prompt(messages, system_prompt)

        response = await self._async_client.beta.chat.completions.parse(
            model=self.model.value,
            messages=all_messages,
            response_format=response_model,
            max_tokens=self._resolve_max_tokens(max_tokens),
            temperature=self._resolve_temperature(temperature, structured=True),
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Failed to parse structured response from OpenAI")
        return parsed

    ## Chat with tools

    def chat_sync(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMChatResponse:
        """Chat with OpenAI using message history and tool calling support."""
        all_messages = self._prepend_system_prompt(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": all_messages,
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature),
        }
        if self._tools:
            kwargs["tools"] = self._tools

        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        # Extract tool call if present
        tool_call: LLMToolCall | None = None
        if message.tool_calls and len(message.tool_calls) > 0:
            tc = message.tool_calls[0]
            tool_call = LLMToolCall(
                tool_name=tc.function.name,
                tool_arguments=json.loads(tc.function.arguments),
            )

        return LLMChatResponse(
            content=message.content,
            tool_call=tool_call,
        )
