"""Chat service for projects, sessions, and messages."""

import secrets
from datetime import datetime, timezone

import structlog

from hydra.api.v1.core.exceptions import NotFoundError
from hydra.api.v1.models.chat import (
    ChatMessageCreate,
    ChatMessageUpsert,
    ChatProjectCreate,
    ChatProjectUpdate,
    ChatSessionCreate,
    ChatSessionStatus,
    ChatSessionUpdate,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class ChatProjectNotFoundError(NotFoundError):
    """Chat project not found."""

    def __init__(self, project_id: str):
        super().__init__("chat_project", project_id)


class ChatSessionNotFoundError(NotFoundError):
    """Chat session not found."""

    def __init__(self, session_id: str):
        super().__init__("chat_session", session_id)


class ChatService:
    """Chat management service for projects, sessions, and messages."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    # ==================== Projects ====================

    async def list_projects(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List chat projects for a user."""
        cursor = (
            self.db.chat_projects.find({"ownerId": user_id})
            .sort("updatedAt", -1)
            .skip(offset)
            .limit(limit)
        )

        projects = []
        async for doc in cursor:
            # Get session count for this project
            session_count = await self.db.chat_sessions.count_documents({
                "projectId": doc["projectId"]
            })
            projects.append(self._project_doc_to_response(doc, session_count))

        total = await self.db.chat_projects.count_documents({"ownerId": user_id})

        return {"projects": projects, "total": total}

    async def get_project(self, project_id: str, user_id: str) -> dict:
        """Get a specific chat project."""
        doc = await self.db.chat_projects.find_one({
            "projectId": project_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatProjectNotFoundError(project_id)

        session_count = await self.db.chat_sessions.count_documents({
            "projectId": project_id
        })

        return self._project_doc_to_response(doc, session_count)

    async def create_project(
        self,
        request: ChatProjectCreate,
        user_id: str,
    ) -> dict:
        """Create a new chat project."""
        now = datetime.now(timezone.utc)
        project_id = f"proj_{secrets.token_urlsafe(8)}"

        doc = {
            "projectId": project_id,
            "name": request.name,
            "description": request.description,
            "ownerId": user_id,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.chat_projects.insert_one(doc)

        logger.info("chat_project_created", project_id=project_id, user_id=user_id)

        return self._project_doc_to_response(doc, 0)

    async def update_project(
        self,
        project_id: str,
        request: ChatProjectUpdate,
        user_id: str,
    ) -> dict:
        """Update a chat project."""
        doc = await self.db.chat_projects.find_one({
            "projectId": project_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatProjectNotFoundError(project_id)

        now = datetime.now(timezone.utc)
        update_fields = {"updatedAt": now}

        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description

        await self.db.chat_projects.update_one(
            {"projectId": project_id},
            {"$set": update_fields},
        )

        updated_doc = await self.db.chat_projects.find_one({"projectId": project_id})
        session_count = await self.db.chat_sessions.count_documents({
            "projectId": project_id
        })

        logger.info("chat_project_updated", project_id=project_id, user_id=user_id)

        return self._project_doc_to_response(updated_doc, session_count)

    async def delete_project(
        self,
        project_id: str,
        user_id: str,
        cascade: bool = True,
    ) -> dict:
        """Delete a chat project."""
        doc = await self.db.chat_projects.find_one({
            "projectId": project_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatProjectNotFoundError(project_id)

        if cascade:
            # Delete all sessions and their messages
            sessions = self.db.chat_sessions.find({"projectId": project_id})
            async for session in sessions:
                await self.db.chat_messages.delete_many({
                    "sessionId": session["sessionId"]
                })
            await self.db.chat_sessions.delete_many({"projectId": project_id})

        await self.db.chat_projects.delete_one({"projectId": project_id})

        logger.info(
            "chat_project_deleted",
            project_id=project_id,
            user_id=user_id,
            cascade=cascade,
        )

        return {"deleted": True, "projectId": project_id}

    # ==================== Sessions ====================

    async def list_sessions(
        self,
        user_id: str,
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List chat sessions for a user."""
        query = {"ownerId": user_id}
        if project_id:
            query["projectId"] = project_id

        cursor = (
            self.db.chat_sessions.find(query)
            .sort("lastMessageAt", -1)
            .skip(offset)
            .limit(limit)
        )

        sessions = []
        async for doc in cursor:
            message_count = await self.db.chat_messages.count_documents({
                "sessionId": doc["sessionId"]
            })
            sessions.append(self._session_doc_to_response(doc, message_count))

        total = await self.db.chat_sessions.count_documents(query)

        return {"sessions": sessions, "total": total}

    async def get_session(self, session_id: str, user_id: str) -> dict:
        """Get a specific chat session."""
        doc = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatSessionNotFoundError(session_id)

        message_count = await self.db.chat_messages.count_documents({
            "sessionId": session_id
        })

        return self._session_doc_to_response(doc, message_count)

    async def create_session(
        self,
        request: ChatSessionCreate,
        user_id: str,
    ) -> dict:
        """Create a new chat session."""
        now = datetime.now(timezone.utc)
        session_id = f"sess_{secrets.token_urlsafe(8)}"

        # Verify project exists if specified
        if request.project_id:
            project = await self.db.chat_projects.find_one({
                "projectId": request.project_id,
                "ownerId": user_id,
            })
            if not project:
                raise ChatProjectNotFoundError(request.project_id)

        doc = {
            "sessionId": session_id,
            "projectId": request.project_id,
            "title": request.title or "New Chat",
            "status": ChatSessionStatus.ACTIVE.value,
            "llmProviderId": request.llm_provider_id,
            "mcpServerIds": request.mcp_server_ids,
            "ownerId": user_id,
            "createdAt": now,
            "updatedAt": now,
            "lastMessageAt": None,
        }

        await self.db.chat_sessions.insert_one(doc)

        logger.info("chat_session_created", session_id=session_id, user_id=user_id)

        return self._session_doc_to_response(doc, 0)

    async def update_session(
        self,
        session_id: str,
        request: ChatSessionUpdate,
        user_id: str,
    ) -> dict:
        """Update a chat session."""
        doc = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatSessionNotFoundError(session_id)

        now = datetime.now(timezone.utc)
        update_fields = {"updatedAt": now}

        if request.title is not None:
            update_fields["title"] = request.title
        if request.status is not None:
            update_fields["status"] = request.status.value
        if request.project_id is not None:
            # Verify project exists
            if request.project_id:
                project = await self.db.chat_projects.find_one({
                    "projectId": request.project_id,
                    "ownerId": user_id,
                })
                if not project:
                    raise ChatProjectNotFoundError(request.project_id)
            update_fields["projectId"] = request.project_id
        if request.llm_provider_id is not None:
            update_fields["llmProviderId"] = request.llm_provider_id
        if request.mcp_server_ids is not None:
            update_fields["mcpServerIds"] = request.mcp_server_ids

        await self.db.chat_sessions.update_one(
            {"sessionId": session_id},
            {"$set": update_fields},
        )

        updated_doc = await self.db.chat_sessions.find_one({"sessionId": session_id})
        message_count = await self.db.chat_messages.count_documents({
            "sessionId": session_id
        })

        logger.info("chat_session_updated", session_id=session_id, user_id=user_id)

        return self._session_doc_to_response(updated_doc, message_count)

    async def delete_session(
        self,
        session_id: str,
        user_id: str,
    ) -> dict:
        """Delete a chat session and its messages."""
        doc = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatSessionNotFoundError(session_id)

        # Delete all messages in the session
        await self.db.chat_messages.delete_many({"sessionId": session_id})

        # Delete the session
        await self.db.chat_sessions.delete_one({"sessionId": session_id})

        logger.info("chat_session_deleted", session_id=session_id, user_id=user_id)

        return {"deleted": True, "sessionId": session_id}

    # ==================== Messages ====================

    async def list_messages(
        self,
        session_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        order: str = "asc",
    ) -> dict:
        """List messages in a chat session."""
        # Verify session ownership
        session = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not session:
            raise ChatSessionNotFoundError(session_id)

        sort_dir = 1 if order == "asc" else -1
        cursor = (
            self.db.chat_messages.find({"sessionId": session_id})
            .sort("order", sort_dir)
            .skip(offset)
            .limit(limit)
        )

        messages = []
        async for doc in cursor:
            messages.append(self._message_doc_to_response(doc))

        total = await self.db.chat_messages.count_documents({"sessionId": session_id})
        has_more = offset + len(messages) < total

        return {"messages": messages, "total": total, "has_more": has_more}

    async def create_message(
        self,
        session_id: str,
        request: ChatMessageCreate,
        user_id: str,
    ) -> dict:
        """Create a new message in a chat session."""
        # Verify session ownership
        session = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not session:
            raise ChatSessionNotFoundError(session_id)

        now = datetime.now(timezone.utc)
        message_id = f"msg_{secrets.token_urlsafe(8)}"

        # Get current max order
        last_message = await self.db.chat_messages.find_one(
            {"sessionId": session_id},
            sort=[("order", -1)],
        )
        next_order = (last_message["order"] + 1) if last_message else 0

        doc = {
            "messageId": message_id,
            "sessionId": session_id,
            "role": request.role.value,
            "content": request.content,
            "toolCalls": (
                [tc.model_dump(by_alias=True) for tc in request.tool_calls]
                if request.tool_calls
                else None
            ),
            "order": next_order,
            "createdAt": now,
        }

        await self.db.chat_messages.insert_one(doc)

        # Update session's lastMessageAt
        await self.db.chat_sessions.update_one(
            {"sessionId": session_id},
            {"$set": {"lastMessageAt": now, "updatedAt": now}},
        )

        logger.info(
            "chat_message_created",
            message_id=message_id,
            session_id=session_id,
            role=request.role.value,
        )

        return self._message_doc_to_response(doc)

    async def bulk_upsert_messages(
        self,
        session_id: str,
        messages: list[ChatMessageUpsert],
        user_id: str,
    ) -> dict:
        """Bulk upsert messages for background save."""
        # Verify session ownership
        session = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not session:
            raise ChatSessionNotFoundError(session_id)

        now = datetime.now(timezone.utc)
        upserted_count = 0

        # Get current max order for new messages
        last_message = await self.db.chat_messages.find_one(
            {"sessionId": session_id},
            sort=[("order", -1)],
        )
        current_max_order = last_message["order"] if last_message else -1

        for msg in messages:
            if msg.message_id:
                # Update existing message
                result = await self.db.chat_messages.update_one(
                    {"messageId": msg.message_id, "sessionId": session_id},
                    {
                        "$set": {
                            "content": msg.content,
                            "toolCalls": (
                                [tc.model_dump(by_alias=True) for tc in msg.tool_calls]
                                if msg.tool_calls
                                else None
                            ),
                        }
                    },
                )
                if result.modified_count > 0:
                    upserted_count += 1
            else:
                # Create new message
                message_id = f"msg_{secrets.token_urlsafe(8)}"
                current_max_order += 1

                doc = {
                    "messageId": message_id,
                    "sessionId": session_id,
                    "role": msg.role.value,
                    "content": msg.content,
                    "toolCalls": (
                        [tc.model_dump(by_alias=True) for tc in msg.tool_calls]
                        if msg.tool_calls
                        else None
                    ),
                    "order": msg.order if msg.order is not None else current_max_order,
                    "createdAt": now,
                }
                await self.db.chat_messages.insert_one(doc)
                upserted_count += 1

        # Update session's lastMessageAt
        await self.db.chat_sessions.update_one(
            {"sessionId": session_id},
            {"$set": {"lastMessageAt": now, "updatedAt": now}},
        )

        logger.info(
            "chat_messages_bulk_upserted",
            session_id=session_id,
            count=upserted_count,
        )

        return {"upserted_count": upserted_count, "session_id": session_id}

    # ==================== Helpers ====================

    def _project_doc_to_response(self, doc: dict, session_count: int) -> dict:
        """Convert project document to response."""
        return {
            "project_id": doc["projectId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "session_count": session_count,
            "owner_id": doc["ownerId"],
            "created_at": doc["createdAt"],
            "updated_at": doc["updatedAt"],
        }

    def _session_doc_to_response(self, doc: dict, message_count: int) -> dict:
        """Convert session document to response."""
        return {
            "session_id": doc["sessionId"],
            "project_id": doc.get("projectId"),
            "title": doc.get("title"),
            "status": doc["status"],
            "message_count": message_count,
            "llm_provider_id": doc.get("llmProviderId"),
            "mcp_server_ids": doc.get("mcpServerIds", []),
            "owner_id": doc["ownerId"],
            "created_at": doc["createdAt"],
            "updated_at": doc["updatedAt"],
            "last_message_at": doc.get("lastMessageAt"),
        }

    def _message_doc_to_response(self, doc: dict) -> dict:
        """Convert message document to response."""
        return {
            "message_id": doc["messageId"],
            "session_id": doc["sessionId"],
            "role": doc["role"],
            "content": doc["content"],
            "tool_calls": doc.get("toolCalls"),
            "order": doc["order"],
            "created_at": doc["createdAt"],
        }
