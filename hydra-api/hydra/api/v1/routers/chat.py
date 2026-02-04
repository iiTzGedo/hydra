"""Chat management endpoints for projects, sessions, and messages."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser, check_not_agent
from hydra.api.v1.models.chat import (
    ChatBulkUpsertResponse,
    ChatMessageBulkCreate,
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatProjectCreate,
    ChatProjectListResponse,
    ChatProjectResponse,
    ChatProjectUpdate,
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
    SessionContextResponse,
)
from hydra.api.v1.services.chat import ChatService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = structlog.get_logger(__name__)


async def get_chat_service(mongodb: MongoDB = Depends(get_mongodb)) -> ChatService:
    """Get chat service."""
    return ChatService(mongodb)



@router.get(
    "/projects",
    response_model=ChatProjectListResponse,
    summary="List Chat Projects",
    description="List chat projects for the current user.",
)
async def list_projects(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChatProjectListResponse:
    """Retrieve chat projects owned by the current user.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of chat projects.

    Raises:
        HTTPException 403: Agents cannot access chat.
    """
    check_not_agent(current_user, "chat:read")

    projects, total = await chat_service.list_projects(
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
    )

    return ChatProjectListResponse(
        projects=[ChatProjectResponse(**p) for p in projects],
        total=total,
    )


@router.post(
    "/projects",
    response_model=ChatProjectResponse,
    status_code=201,
    summary="Create Chat Project",
    description="Create a new chat project.",
)
async def create_project(
    request: ChatProjectCreate,
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatProjectResponse:
    """Create a new chat project to organize sessions.

    Args:
        request: Project details including name and description.
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.

    Returns:
        Created project details.

    Raises:
        HTTPException 403: Agents cannot access chat.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.create_project(
        request=request,
        user_id=current_user["user_id"],
    )

    return ChatProjectResponse(**result)


@router.get(
    "/projects/{projectId}",
    response_model=ChatProjectResponse,
    summary="Get Chat Project",
    description="Get a specific chat project.",
)
async def get_project(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    projectId: str = Path(description="Project ID"),
) -> ChatProjectResponse:
    """Retrieve a specific chat project by ID.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        projectId: Unique identifier of the project.

    Returns:
        Project details.

    Raises:
        HTTPException 403: Agents cannot access chat or project not owned by user.
        HTTPException 404: Project not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.get_project(
        project_id=projectId,
        user_id=current_user["user_id"],
    )

    return ChatProjectResponse(**result)


@router.put(
    "/projects/{projectId}",
    response_model=ChatProjectResponse,
    summary="Update Chat Project",
    description="Update a chat project.",
)
async def update_project(
    request: ChatProjectUpdate,
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    projectId: str = Path(description="Project ID"),
) -> ChatProjectResponse:
    """Update an existing chat project.

    Args:
        request: Fields to update.
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        projectId: Unique identifier of the project.

    Returns:
        Updated project details.

    Raises:
        HTTPException 403: Agents cannot access chat or project not owned by user.
        HTTPException 404: Project not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.update_project(
        project_id=projectId,
        request=request,
        user_id=current_user["user_id"],
    )

    return ChatProjectResponse(**result)


@router.delete(
    "/projects/{projectId}",
    summary="Delete Chat Project",
    description="Delete a chat project and optionally cascade delete sessions.",
)
async def delete_project(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    projectId: str = Path(description="Project ID"),
    cascade: bool = Query(default=True, description="Delete sessions and messages"),
) -> dict:
    """Delete a chat project and optionally its sessions.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        projectId: Unique identifier of the project.
        cascade: Delete associated sessions and messages.

    Returns:
        Deletion confirmation with counts.

    Raises:
        HTTPException 403: Agents cannot access chat or project not owned by user.
        HTTPException 404: Project not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.delete_project(
        project_id=projectId,
        user_id=current_user["user_id"],
        cascade=cascade,
    )

    return result


@router.get(
    "/sessions",
    response_model=ChatSessionListResponse,
    summary="List Chat Sessions",
    description="List chat sessions for the current user.",
)
async def list_sessions(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    projectId: str | None = Query(default=None, description="Filter by project ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChatSessionListResponse:
    """Retrieve chat sessions owned by the current user.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        projectId: Filter sessions by project.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of chat sessions.

    Raises:
        HTTPException 403: Agents cannot access chat.
    """
    check_not_agent(current_user, "chat:read")

    sessions, total = await chat_service.list_sessions(
        user_id=current_user["user_id"],
        project_id=projectId,
        limit=limit,
        offset=offset,
    )

    return ChatSessionListResponse(
        sessions=[ChatSessionResponse(**s) for s in sessions],
        total=total,
    )


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=201,
    summary="Create Chat Session",
    description="Create a new chat session.",
)
async def create_session(
    request: ChatSessionCreate,
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatSessionResponse:
    """Create a new chat session for AI conversations.

    Args:
        request: Session configuration including LLM provider and MCP servers.
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.

    Returns:
        Created session details.

    Raises:
        HTTPException 403: Agents cannot access chat.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.create_session(
        request=request,
        user_id=current_user["user_id"],
    )

    return ChatSessionResponse(**result)


@router.get(
    "/sessions/{sessionId}",
    response_model=ChatSessionResponse,
    summary="Get Chat Session",
    description="Get a specific chat session.",
)
async def get_session(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
) -> ChatSessionResponse:
    """Retrieve a specific chat session by ID.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.

    Returns:
        Session details.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.get_session(
        session_id=sessionId,
        user_id=current_user["user_id"],
    )

    return ChatSessionResponse(**result)


@router.get(
    "/sessions/{sessionId}/context",
    response_model=SessionContextResponse,
    summary="Get Session Context",
    description="Get real-time session context for UI display.",
)
async def get_session_context(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
) -> SessionContextResponse:
    """Get real-time session context including token counts and costs.

    This endpoint provides context information for the chat UI, including:
    - Token usage (input, output, total)
    - Estimated cost
    - Tool call count
    - Message count
    - Model and provider information
    - LLM config lock status

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.

    Returns:
        Session context with usage metrics.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.get_session_context(
        session_id=sessionId,
        user_id=current_user["user_id"],
    )

    return SessionContextResponse(**result)


@router.put(
    "/sessions/{sessionId}",
    response_model=ChatSessionResponse,
    summary="Update Chat Session",
    description="Update a chat session.",
)
async def update_session(
    request: ChatSessionUpdate,
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
) -> ChatSessionResponse:
    """Update an existing chat session.

    Args:
        request: Fields to update.
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.

    Returns:
        Updated session details.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.update_session(
        session_id=sessionId,
        request=request,
        user_id=current_user["user_id"],
    )

    return ChatSessionResponse(**result)


@router.delete(
    "/sessions/{sessionId}",
    summary="Delete Chat Session",
    description="Delete a chat session and its messages.",
)
async def delete_session(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
) -> dict:
    """Delete a chat session and all its messages.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.

    Returns:
        Deletion confirmation.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.delete_session(
        session_id=sessionId,
        user_id=current_user["user_id"],
    )

    return result


@router.get(
    "/sessions/{sessionId}/messages",
    response_model=ChatMessageListResponse,
    summary="List Chat Messages",
    description="List messages in a chat session.",
)
async def list_messages(
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> ChatMessageListResponse:
    """Retrieve messages in a chat session.

    Args:
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        order: Sort order (asc for oldest first, desc for newest first).

    Returns:
        Paginated list of messages.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    messages, total = await chat_service.list_messages(
        session_id=sessionId,
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
        order=order,
    )

    return ChatMessageListResponse(
        messages=[ChatMessageResponse(**m) for m in messages],
        total=total,
        has_more=offset + len(messages) < total,
    )


@router.post(
    "/sessions/{sessionId}/messages",
    response_model=ChatMessageResponse,
    status_code=201,
    summary="Create Chat Message",
    description="Create a new message in a chat session.",
)
async def create_message(
    request: ChatMessageCreate,
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
) -> ChatMessageResponse:
    """Add a new message to a chat session.

    Args:
        request: Message content and role.
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.

    Returns:
        Created message details.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.create_message(
        session_id=sessionId,
        request=request,
        user_id=current_user["user_id"],
    )

    return ChatMessageResponse(**result)


@router.post(
    "/sessions/{sessionId}/messages/bulk",
    response_model=ChatBulkUpsertResponse,
    summary="Bulk Upsert Messages",
    description="Bulk create/update messages for background save from web client.",
)
async def bulk_upsert_messages(
    request: ChatMessageBulkCreate,
    current_user: CurrentUser,
    chat_service: ChatService = Depends(get_chat_service),
    sessionId: str = Path(description="Session ID"),
) -> ChatBulkUpsertResponse:
    """Bulk create or update messages for efficient background saves.

    Args:
        request: List of messages to upsert.
        current_user: Authenticated user making the request.
        chat_service: Chat service instance.
        sessionId: Unique identifier of the session.

    Returns:
        Upsert result with counts.

    Raises:
        HTTPException 403: Agents cannot access chat or session not owned by user.
        HTTPException 404: Session not found.
    """
    check_not_agent(current_user, "chat:read")

    result = await chat_service.bulk_upsert_messages(
        session_id=sessionId,
        messages=request.messages,
        user_id=current_user["user_id"],
    )

    return ChatBulkUpsertResponse(**result)
