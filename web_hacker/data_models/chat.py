"""
web_hacker/data_models/chat.py

Chat state data models for the chat.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from data_models.resource_base import ResourceBase


class ChatRole(StrEnum):
    """
    Role in a chat message.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """
    A single message in the conversation history.
    """

    role: ChatRole = Field(
        ...,
        description="The role of the message sender",
    )
    content: str = Field(
        ...,
        description="The content of the message",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the message was created",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the message",
    )


class ToolInvocationStatus(StrEnum):
    """
    Status of a tool invocation.
    """

    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    DENIED = "denied"
    EXECUTED = "executed"
    FAILED = "failed"


class PendingToolInvocation(BaseModel):
    """
    A tool invocation awaiting user confirmation.
    """
    invocation_id: str = Field(
        ...,
        description="Unique ID for this invocation (UUIDv4)",
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool to invoke",
    )
    tool_arguments: dict[str, Any] = Field(
        ...,
        description="Arguments to pass to the tool",
    )
    status: ToolInvocationStatus = Field(
        default=ToolInvocationStatus.PENDING_CONFIRMATION,
        description="Current status of the invocation",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the invocation was created",
    )


class ChatState(BaseModel):
    """
    Full state of a chat conversation session.
    """
    chat_id: str = Field(
        ...,
        description="Unique session identifier (UUIDv4)",
    )
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="Conversation history",
    )
    pending_tool_invocation: PendingToolInvocation | None = Field(
        default=None,
        description="Tool invocation awaiting confirmation, if any",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the session was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the session was last updated",
    )


class ChatMessageType(StrEnum):
    """
    Types of messages the chat can emit via callback.
    """

    CHAT_RESPONSE = "chat_response"
    TOOL_INVOCATION_REQUEST = "tool_invocation_request"
    TOOL_INVOCATION_RESULT = "tool_invocation_result"
    ERROR = "error"


class ChatMessage(BaseModel):
    """
    Message emitted by the chat via callback.

    This is the internal message format used by Chat to communicate
    with its host (e.g., CLI, WebSocket handler in servers repo).
    """

    type: ChatMessageType = Field(
        ...,
        description="The type of message being emitted",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the message was created",
    )
    content: str | None = Field(
        default=None,
        description="Text content for chat responses or error messages",
    )
    tool_invocation: PendingToolInvocation | None = Field(
        default=None,
        description="Tool invocation details for request/result messages",
    )
    tool_result: dict[str, Any] | None = Field(
        default=None,
        description="Result data from tool execution",
    )
    error: str | None = Field(
        default=None,
        description="Error message if type is ERROR",
    )
