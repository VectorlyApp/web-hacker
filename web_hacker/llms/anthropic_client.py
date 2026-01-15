"""
web_hacker/llms/anthropic_client.py

Anthropic-specific LLM client implementation.
"""

from typing import Any, TypeVar

from anthropic import Anthropic, AsyncAnthropic
from pydantic import BaseModel

from data_models.llms import LLMModel
from llms.abstract_llm_vendor_client import AbstractLLMVendorClient
from config import Config
from utils.logger import get_logger

logger = get_logger(name=__name__)


T = TypeVar("T", bound=BaseModel)


class AnthropicClient(AbstractLLMVendorClient):
    """
    Anthropic-specific implementation of the LLM vendor client.

    Uses the Anthropic Python SDK for message completions, structured outputs
    via tool use, and function calling.
    """

    # Magic methods ________________________________________________________________________________________________________

    def __init__(self, model: LLMModel) -> None:
        super().__init__(model)
        self._client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self._async_client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
        logger.debug("Initialized AnthropicClient with model: %s", model)


    # Private methods ______________________________________________________________________________________________________

    def _extract_text_content(self, content: list[Any]) -> str:
        """Extract text from Anthropic content blocks."""
        text_parts = [block.text for block in content if hasattr(block, "text")]
        return "".join(text_parts)

    def _build_extraction_tool(
        self,
        prompt: str,
        response_model: type[T],
    ) -> tuple[dict[str, Any], str]:
        """Build the extraction tool and modified prompt for structured responses."""
        tool_schema = response_model.model_json_schema()
        tool = {
            "name": "extract_data",
            "description": f"Extract data matching the {response_model.__name__} schema.",
            "input_schema": tool_schema,
        }
        structured_prompt = (
            f"{prompt}\n\nUse the 'extract_data' tool to provide your response "
            f"in the exact schema specified."
        )
        return tool, structured_prompt

    def _extract_tool_result(
        self,
        content: list[Any],
        response_model: type[T],
    ) -> T:
        """Extract and validate the tool use result from Anthropic response."""
        for block in content:
            if hasattr(block, "input") and hasattr(block, "name") and block.name == "extract_data":
                return response_model.model_validate(block.input)
        raise ValueError("Failed to extract structured response from Anthropic")


    # Public methods _______________________________________________________________________________________________________

    ## Tool management

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
    ) -> None:
        """Register a tool in Anthropic's tool format."""
        logger.debug("Registering Anthropic tool: %s", name)
        self._tools.append({
            "name": name,
            "description": description,
            "input_schema": parameters,
        })

    ## Text generation

    def get_text_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Get a text response synchronously using Anthropic messages API."""
        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature),
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if self._tools:
            kwargs["tools"] = self._tools

        response = self._client.messages.create(**kwargs)
        return self._extract_text_content(response.content)

    async def get_text_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Get a text response asynchronously using Anthropic messages API."""
        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature),
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if self._tools:
            kwargs["tools"] = self._tools

        response = await self._async_client.messages.create(**kwargs)
        return self._extract_text_content(response.content)

    ## Structured responses

    def get_structured_response_sync(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        """Get a structured response using Anthropic's tool_use with forced tool choice."""
        tool, structured_prompt = self._build_extraction_tool(prompt, response_model)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": [{"role": "user", "content": structured_prompt}],
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature, structured=True),
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": "extract_data"},
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        return self._extract_tool_result(response.content, response_model)

    async def get_structured_response_async(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        """Get a structured response asynchronously using Anthropic's tool_use."""
        tool, structured_prompt = self._build_extraction_tool(prompt, response_model)

        kwargs: dict[str, Any] = {
            "model": self.model.value,
            "messages": [{"role": "user", "content": structured_prompt}],
            "max_tokens": self._resolve_max_tokens(max_tokens),
            "temperature": self._resolve_temperature(temperature, structured=True),
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": "extract_data"},
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._async_client.messages.create(**kwargs)
        return self._extract_tool_result(response.content, response_model)
