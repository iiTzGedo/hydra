"""Chat management endpoints for projects, sessions, and messages."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser
from hydra.api.v1.core.exceptions import AuthorizationError
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
)
from hydra.api.v1.services.chat import ChatService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = structlog.get_logger(__name__)


async def get_chat_service(mongodb: MongoDB = Depends(get_mongodb)) -> ChatService:
    """Get chat service."""
    return ChatService(mongodb)


def _check_not_agent(current_user: dict) -> None:
    """Verify user is not an agent."""
    if current_user.get("type") == "agent":
        raise AuthorizationError("chat:read")


# ==================== Project Endpoints ====================


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
    """List chat projects."""
    _check_not_agent(current_user)

    result = await chat_service.list_projects(
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
    )

    return ChatProjectListResponse(
        projects=[ChatProjectResponse(**p) for p in result["projects"]],
        total=result["total"],
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
    """Create a new chat project."""
    _check_not_agent(current_user)

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
    """Get a specific chat project."""
    _check_not_agent(current_user)

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
    """Update a chat project."""
    _check_not_agent(current_user)

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
    """Delete a chat project."""
    _check_not_agent(current_user)

    result = await chat_service.delete_project(
        project_id=projectId,
        user_id=current_user["user_id"],
        cascade=cascade,
    )

    return result


# ==================== Session Endpoints ====================


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
    """List chat sessions."""
    _check_not_agent(current_user)

    result = await chat_service.list_sessions(
        user_id=current_user["user_id"],
        project_id=projectId,
        limit=limit,
        offset=offset,
    )

    return ChatSessionListResponse(
        sessions=[ChatSessionResponse(**s) for s in result["sessions"]],
        total=result["total"],
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
    """Create a new chat session."""
    _check_not_agent(current_user)

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
    """Get a specific chat session."""
    _check_not_agent(current_user)

    result = await chat_service.get_session(
        session_id=sessionId,
        user_id=current_user["user_id"],
    )

    return ChatSessionResponse(**result)


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
    """Update a chat session."""
    _check_not_agent(current_user)

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
    """Delete a chat session."""
    _check_not_agent(current_user)

    result = await chat_service.delete_session(
        session_id=sessionId,
        user_id=current_user["user_id"],
    )

    return result


# ==================== Message Endpoints ====================


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
    order: str = Query(default="asc", regex="^(asc|desc)$"),
) -> ChatMessageListResponse:
    """List messages in a chat session."""
    _check_not_agent(current_user)

    result = await chat_service.list_messages(
        session_id=sessionId,
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
        order=order,
    )

    return ChatMessageListResponse(
        messages=[ChatMessageResponse(**m) for m in result["messages"]],
        total=result["total"],
        has_more=result["has_more"],
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
    """Create a new message in a chat session."""
    _check_not_agent(current_user)

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
    """Bulk upsert messages for background save."""
    _check_not_agent(current_user)

    result = await chat_service.bulk_upsert_messages(
        session_id=sessionId,
        messages=request.messages,
        user_id=current_user["user_id"],
    )

    return ChatBulkUpsertResponse(**result)
