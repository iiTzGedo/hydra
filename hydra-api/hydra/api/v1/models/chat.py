"""Chat models for projects, sessions, and messages."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionStatus(StrEnum):
    """Chat session status."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolCallStatus(StrEnum):
    """Tool call execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class ToolCall(BaseModel):
    """A tool call within a message."""

    id: str = Field(description="Unique tool call ID")
    server_id: str = Field(alias="serverId", description="MCP server that handled the call")
    server_name: str | None = Field(default=None, alias="serverName")
    name: str = Field(description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = Field(default=None)
    error: str | None = Field(default=None)
    status: ToolCallStatus = Field(default=ToolCallStatus.PENDING)

    model_config = ConfigDict(populate_by_name=True)


class ChatProjectCreate(BaseModel):
    """Request to create a chat project."""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)

    model_config = ConfigDict(populate_by_name=True)


class ChatProjectUpdate(BaseModel):
    """Request to update a chat project."""

    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=1024)

    model_config = ConfigDict(populate_by_name=True)


class ChatProjectResponse(BaseModel):
    """Chat project response."""

    project_id: str = Field(alias="projectId")
    name: str
    description: str | None = None
    session_count: int = Field(default=0, alias="sessionCount")
    owner_id: str = Field(alias="ownerId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class ChatProjectListResponse(BaseModel):
    """List of chat projects response."""

    projects: list[ChatProjectResponse]
    total: int
    limit: int
    offset: int


class ChatSessionCreate(BaseModel):
    """Request to create a chat session."""

    project_id: str | None = Field(default=None, alias="projectId")
    title: str | None = Field(default=None, max_length=256)
    llm_provider_id: str | None = Field(default=None, alias="llmProviderId")
    mcp_server_ids: list[str] = Field(default_factory=list, alias="mcpServerIds")

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionUpdate(BaseModel):
    """Request to update a chat session."""

    title: str | None = Field(default=None, max_length=256)
    project_id: str | None = Field(default=None, alias="projectId")
    status: ChatSessionStatus | None = None
    llm_provider_id: str | None = Field(default=None, alias="llmProviderId")
    mcp_server_ids: list[str] | None = Field(default=None, alias="mcpServerIds")

    model_config = ConfigDict(populate_by_name=True)


class SessionContext(BaseModel):
    """Session context tracking for tokens, costs, and usage."""

    total_tokens: int = Field(default=0, alias="totalTokens", description="Total tokens used")
    input_tokens: int = Field(default=0, alias="inputTokens", description="Input tokens used")
    output_tokens: int = Field(default=0, alias="outputTokens", description="Output tokens used")
    estimated_cost: float = Field(default=0.0, alias="estimatedCost", description="Estimated cost in USD")
    tool_calls_count: int = Field(default=0, alias="toolCallsCount", description="Number of tool calls made")
    message_count: int = Field(default=0, alias="messageCount", description="Number of messages in session")
    model_used: str | None = Field(default=None, alias="modelUsed", description="Model used for this session")
    provider_type: str | None = Field(default=None, alias="providerType", description="LLM provider type")
    thread: list[str] = Field(default_factory=list, description="Ordered list of messageIds - source of truth for message ordering")

    model_config = ConfigDict(populate_by_name=True)


class SessionContextResponse(BaseModel):
    """Response for session context endpoint."""

    session_id: str = Field(alias="sessionId")
    context: SessionContext
    llm_config_locked: bool = Field(alias="llmConfigLocked")
    last_updated: datetime = Field(alias="lastUpdated")

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionResponse(BaseModel):
    """Chat session response."""

    session_id: str = Field(alias="sessionId")
    project_id: str | None = Field(alias="projectId")
    title: str | None = None
    status: ChatSessionStatus
    message_count: int = Field(alias="messageCount")
    llm_provider_id: str | None = Field(alias="llmProviderId")
    mcp_server_ids: list[str] = Field(default_factory=list, alias="mcpServerIds")
    llm_config_locked: bool = Field(default=False, alias="llmConfigLocked", description="Whether LLM config is locked after first response")
    session_context: SessionContext | None = Field(default=None, alias="sessionContext", description="Session usage context")
    owner_id: str = Field(alias="ownerId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    last_message_at: datetime | None = Field(default=None, alias="lastMessageAt")

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionListResponse(BaseModel):
    """List of chat sessions response."""

    sessions: list[ChatSessionResponse]
    total: int
    limit: int
    offset: int


class ChatMessageCreate(BaseModel):
    """Request to create a chat message."""

    role: MessageRole
    content: str = Field(min_length=1)
    tool_calls: list[ToolCall] | None = Field(default=None, alias="toolCalls")

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageBulkCreate(BaseModel):
    """Request to bulk create/upsert messages (for background save)."""

    messages: list["ChatMessageUpsert"]

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageUpsert(BaseModel):
    """Message to upsert in bulk operation."""

    message_id: str | None = Field(default=None, alias="messageId")
    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = Field(default=None, alias="toolCalls")
    order: int | None = None

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    message_id: str = Field(alias="messageId")
    session_id: str = Field(alias="sessionId")
    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = Field(default=None, alias="toolCalls")
    order: int
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageListResponse(BaseModel):
    """List of chat messages response."""

    messages: list[ChatMessageResponse]
    total: int
    limit: int
    offset: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)


class ChatBulkUpsertResponse(BaseModel):
    """Response for bulk message upsert."""

    upserted_count: int = Field(alias="upsertedCount")
    session_id: str = Field(alias="sessionId")

    model_config = ConfigDict(populate_by_name=True)


# Rebuild models with forward references
ChatMessageBulkCreate.model_rebuild()
