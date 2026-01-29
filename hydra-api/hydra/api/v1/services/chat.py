"""Chat service for projects, sessions, and messages."""

import secrets
from datetime import datetime, timezone

import structlog
from pymongo import ReturnDocument

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.chat import (
    ChatMessageCreate,
    ChatMessageUpsert,
    ChatProjectCreate,
    ChatProjectUpdate,
    ChatSessionCreate,
    ChatSessionStatus,
    ChatSessionUpdate,
)
from hydra.api.v1.services.chat_cache import ChatCacheService
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

    def __init__(self, mongodb: MongoDB, cache: ChatCacheService | None = None):
        self.db = mongodb
        self._cache = cache or ChatCacheService()

    # ==================== Projects ====================

    async def list_projects(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List chat projects for a user.

        Args:
            user_id: The user identifier.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Dict with 'projects' list and 'total' count.
        """
        # Use aggregation pipeline to avoid N+1 queries for session counts
        pipeline = [
            {"$match": {"ownerId": user_id}},
            {"$sort": {"updatedAt": -1}},
            {"$skip": offset},
            {"$limit": limit},
            # Join with chat_sessions to get count in one query
            {
                "$lookup": {
                    "from": "chat_sessions",
                    "localField": "projectId",
                    "foreignField": "projectId",
                    "as": "sessions",
                }
            },
            {"$addFields": {"sessionCount": {"$size": "$sessions"}}},
            {"$project": {"sessions": 0}},  # Remove the sessions array
        ]

        projects = []
        async for doc in self.db.chat_projects.aggregate(pipeline):
            session_count = doc.get("sessionCount", 0)
            projects.append(self._project_doc_to_response(doc, session_count))

        total = await self.db.chat_projects.count_documents({"ownerId": user_id})

        return {"projects": projects, "total": total}

    async def get_project(self, project_id: str, user_id: str) -> dict:
        """Get a specific chat project by ID.

        Args:
            project_id: The project identifier.
            user_id: The owner's user identifier.

        Returns:
            The project details with session count.

        Raises:
            ChatProjectNotFoundError: If project does not exist or is not owned by user.
        """
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
        """Create a new chat project.

        Args:
            request: Project creation payload with name and optional description.
            user_id: The owner's user identifier.

        Returns:
            The created project details.
        """
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
        """Update a chat project.

        Args:
            project_id: The project identifier.
            request: Update payload with optional name and description.
            user_id: The owner's user identifier.

        Returns:
            The updated project details.

        Raises:
            ChatProjectNotFoundError: If project does not exist or is not owned by user.
        """
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
        """Delete a chat project.

        Args:
            project_id: The project identifier.
            user_id: The owner's user identifier.
            cascade: If True, delete all associated sessions and messages.

        Returns:
            Dict with 'deleted' status and 'projectId'.

        Raises:
            ChatProjectNotFoundError: If project does not exist or is not owned by user.
        """
        doc = await self.db.chat_projects.find_one({
            "projectId": project_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatProjectNotFoundError(project_id)

        if cascade:
            # Batch delete: Get all session IDs first, then delete messages in one query
            session_ids = []
            async for session in self.db.chat_sessions.find(
                {"projectId": project_id}, {"sessionId": 1}
            ):
                session_ids.append(session["sessionId"])

            if session_ids:
                # Delete all messages for all sessions in one query
                await self.db.chat_messages.delete_many({
                    "sessionId": {"$in": session_ids}
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
        """List chat sessions for a user.

        Args:
            user_id: The user identifier.
            project_id: Optional project filter.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Dict with 'sessions' list and 'total' count.
        """
        match_query: dict = {"ownerId": user_id}
        if project_id:
            match_query["projectId"] = project_id

        # Use aggregation pipeline to avoid N+1 queries for message counts
        pipeline = [
            {"$match": match_query},
            {"$sort": {"lastMessageAt": -1}},
            {"$skip": offset},
            {"$limit": limit},
            # Join with chat_messages to get count in one query
            {
                "$lookup": {
                    "from": "chat_messages",
                    "localField": "sessionId",
                    "foreignField": "sessionId",
                    "as": "messages",
                }
            },
            {"$addFields": {"messageCount": {"$size": "$messages"}}},
            {"$project": {"messages": 0}},  # Remove the messages array
        ]

        sessions = []
        async for doc in self.db.chat_sessions.aggregate(pipeline):
            message_count = doc.get("messageCount", 0)
            sessions.append(self._session_doc_to_response(doc, message_count))

        total = await self.db.chat_sessions.count_documents(match_query)

        return {"sessions": sessions, "total": total}

    async def get_session(self, session_id: str, user_id: str) -> dict:
        """Get a specific chat session by ID.

        Args:
            session_id: The session identifier.
            user_id: The owner's user identifier.

        Returns:
            The session details with message count.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
        """
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
        """Create a new chat session.

        Args:
            request: Session creation payload with optional project, title, LLM provider.
            user_id: The owner's user identifier.

        Returns:
            The created session details.

        Raises:
            ChatProjectNotFoundError: If specified project does not exist.
        """
        now = datetime.now(timezone.utc)
        session_id = f"sess_{secrets.token_urlsafe(8)}"

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
            "llmConfigLocked": False,
            "sessionContext": {
                "totalTokens": 0,
                "inputTokens": 0,
                "outputTokens": 0,
                "estimatedCost": 0.0,
                "toolCallsCount": 0,
                "messageCount": 0,
                "modelUsed": None,
                "providerType": None,
                "thread": [],  # Ordered list of messageIds - source of truth
            },
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
        """Update a chat session.

        Args:
            session_id: The session identifier.
            request: Update payload with optional title, status, project, LLM provider.
            user_id: The owner's user identifier.

        Returns:
            The updated session details.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
            ChatProjectNotFoundError: If specified project does not exist.
        """
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
            if request.project_id:
                project = await self.db.chat_projects.find_one({
                    "projectId": request.project_id,
                    "ownerId": user_id,
                })
                if not project:
                    raise ChatProjectNotFoundError(request.project_id)
            update_fields["projectId"] = request.project_id
        if request.llm_provider_id is not None:
            # Enforce LLM config locking after first response
            if doc.get("llmConfigLocked") and request.llm_provider_id != doc.get("llmProviderId"):
                raise ValidationError(
                    "Cannot change LLM configuration after first response",
                    {"field": "llmProviderId", "reason": "session_locked"},
                )
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
        """Delete a chat session and all its messages.

        Args:
            session_id: The session identifier.
            user_id: The owner's user identifier.

        Returns:
            Dict with 'deleted' status and 'sessionId'.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
        """
        doc = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatSessionNotFoundError(session_id)

        await self.db.chat_messages.delete_many({"sessionId": session_id})
        await self.db.chat_sessions.delete_one({"sessionId": session_id})

        # Invalidate cache for deleted session
        await self._cache.invalidate_session_cache(session_id)

        logger.info("chat_session_deleted", session_id=session_id, user_id=user_id)

        return {"deleted": True, "sessionId": session_id}

    async def get_session_context(self, session_id: str, user_id: str) -> dict:
        """Get session context for real-time UI display.

        Args:
            session_id: The session identifier.
            user_id: The owner's user identifier.

        Returns:
            Session context with usage metrics and lock status.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
        """
        doc = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not doc:
            raise ChatSessionNotFoundError(session_id)

        message_count = await self.db.chat_messages.count_documents({
            "sessionId": session_id
        })

        session_context = doc.get("sessionContext", {})
        context_data = {
            "total_tokens": session_context.get("totalTokens", 0),
            "input_tokens": session_context.get("inputTokens", 0),
            "output_tokens": session_context.get("outputTokens", 0),
            "estimated_cost": session_context.get("estimatedCost", 0.0),
            "tool_calls_count": session_context.get("toolCallsCount", 0),
            "message_count": message_count,
            "model_used": session_context.get("modelUsed"),
            "provider_type": session_context.get("providerType"),
            "thread": session_context.get("thread", []),  # Source of truth for message order
        }

        return {
            "session_id": session_id,
            "context": context_data,
            "llm_config_locked": doc.get("llmConfigLocked", False),
            "last_updated": doc.get("updatedAt"),
        }

    # ==================== Messages ====================

    async def list_messages(
        self,
        session_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        order: str = "asc",
        use_cache: bool = True,
    ) -> dict:
        """List messages in a chat session.

        Args:
            session_id: The session identifier.
            user_id: The owner's user identifier.
            limit: Maximum number of messages to return.
            offset: Number of messages to skip for pagination.
            order: Sort order ('asc' or 'desc').
            use_cache: Whether to use Redis cache (default True).

        Returns:
            Dict with 'messages' list, 'total' count, and 'has_more' flag.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
        """
        session = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not session:
            raise ChatSessionNotFoundError(session_id)

        # Try cache first for default queries (no offset, ascending order)
        if use_cache and offset == 0 and order == "asc":
            cached = await self._cache.get_cached_messages(session_id)
            if cached is not None:
                # Slice cached results to respect limit
                messages = cached[:limit]
                total = len(cached)
                has_more = len(cached) > limit
                return {"messages": messages, "total": total, "has_more": has_more}

        # Fetch from database
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

        # Populate cache for default queries
        if use_cache and offset == 0 and order == "asc":
            # Fetch all messages for caching if we only got a partial result
            if has_more:
                all_cursor = (
                    self.db.chat_messages.find({"sessionId": session_id})
                    .sort("order", 1)
                )
                all_messages = []
                async for doc in all_cursor:
                    all_messages.append(self._message_doc_to_response(doc))
                await self._cache.cache_session_messages(session_id, all_messages)
            else:
                await self._cache.cache_session_messages(session_id, messages)

        return {"messages": messages, "total": total, "has_more": has_more}

    async def create_message(
        self,
        session_id: str,
        request: ChatMessageCreate,
        user_id: str,
    ) -> dict:
        """Create a new message in a chat session.

        Args:
            session_id: The session identifier.
            request: Message creation payload with role, content, and optional tool calls.
            user_id: The owner's user identifier.

        Returns:
            The created message details.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
        """
        session = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not session:
            raise ChatSessionNotFoundError(session_id)

        now = datetime.now(timezone.utc)
        message_id = f"msg_{secrets.token_urlsafe(8)}"

        # Atomically increment messageCount and get the new value for ordering
        # This prevents race conditions where concurrent messages get the same order
        session_result = await self.db.chat_sessions.find_one_and_update(
            {"sessionId": session_id},
            {
                "$set": {"lastMessageAt": now, "updatedAt": now},
                "$push": {"sessionContext.thread": message_id},
                "$inc": {"sessionContext.messageCount": 1},
            },
            return_document=ReturnDocument.BEFORE,  # Get value BEFORE increment
        )

        # Use the messageCount before increment as the order (0-indexed)
        next_order = session_result.get("sessionContext", {}).get("messageCount", 0) if session_result else 0

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

        message_response = self._message_doc_to_response(doc)

        # Update cache with new message (write-around: DB is source of truth, cache is read optimization)
        await self._cache.append_message_to_cache(session_id, message_response)

        logger.info(
            "chat_message_created",
            message_id=message_id,
            session_id=session_id,
            role=request.role.value,
        )

        return message_response

    async def bulk_upsert_messages(
        self,
        session_id: str,
        messages: list[ChatMessageUpsert],
        user_id: str,
    ) -> dict:
        """Bulk upsert messages for efficient batch saving.

        Updates existing messages by ID or creates new ones. Used for background
        persistence of chat conversations.

        Args:
            session_id: The session identifier.
            messages: List of messages to upsert (with optional message_id for updates).
            user_id: The owner's user identifier.

        Returns:
            Dict with 'upserted_count' and 'session_id'.

        Raises:
            ChatSessionNotFoundError: If session does not exist or is not owned by user.
        """
        session = await self.db.chat_sessions.find_one({
            "sessionId": session_id,
            "ownerId": user_id,
        })

        if not session:
            raise ChatSessionNotFoundError(session_id)

        now = datetime.now(timezone.utc)
        upserted_count = 0
        new_message_ids: list[str] = []

        last_message = await self.db.chat_messages.find_one(
            {"sessionId": session_id},
            sort=[("order", -1)],
        )
        current_max_order = last_message["order"] if last_message else -1

        for msg in messages:
            if msg.message_id:
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
                new_message_ids.append(message_id)
                upserted_count += 1

        # Write-Around: Update session with new messageIds in thread array
        update_ops: dict = {"$set": {"lastMessageAt": now, "updatedAt": now}}
        if new_message_ids:
            update_ops["$push"] = {"sessionContext.thread": {"$each": new_message_ids}}
            update_ops["$inc"] = {"sessionContext.messageCount": len(new_message_ids)}

        await self.db.chat_sessions.update_one(
            {"sessionId": session_id},
            update_ops,
        )

        # Invalidate cache after bulk operations
        await self._cache.invalidate_session_cache(session_id)

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
        session_context = doc.get("sessionContext")
        context_data = None
        if session_context:
            context_data = {
                "total_tokens": session_context.get("totalTokens", 0),
                "input_tokens": session_context.get("inputTokens", 0),
                "output_tokens": session_context.get("outputTokens", 0),
                "estimated_cost": session_context.get("estimatedCost", 0.0),
                "tool_calls_count": session_context.get("toolCallsCount", 0),
                "message_count": session_context.get("messageCount", message_count),
                "model_used": session_context.get("modelUsed"),
                "provider_type": session_context.get("providerType"),
                "thread": session_context.get("thread", []),  # Source of truth for message order
            }

        return {
            "session_id": doc["sessionId"],
            "project_id": doc.get("projectId"),
            "title": doc.get("title"),
            "status": doc["status"],
            "message_count": message_count,
            "llm_provider_id": doc.get("llmProviderId"),
            "mcp_server_ids": doc.get("mcpServerIds", []),
            "llm_config_locked": doc.get("llmConfigLocked", False),
            "session_context": context_data,
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
