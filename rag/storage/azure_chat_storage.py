"""
Azure-backed chat storage for Golem.

Uses Azure Table Storage for conversation and message indexes, and Azure Blob
Storage for full message payloads (optional, recommended for long messages).

Tables
------
- Conversations: PartitionKey=user_id, RowKey=conversation_id
- Messages:      PartitionKey=conversation_id, RowKey=message_id (sortable)

Blobs (optional)
----------------
- Container: chat-messages (configurable)
- Blob name: messages/{conversation_id}/{message_id}.json

Environment (preferred)
-----------------------
- AZURE_STORAGE_CONNECTION_STRING
    or
  AZURE_STORAGE_ACCOUNT_URL (https://<account>.blob.core.windows.net)
  AZURE_STORAGE_ACCOUNT_NAME (for table endpoint fallback)
  AZURE_STORAGE_ACCOUNT_KEY (if not using managed identity)
  # Optional: AZURE_TABLE_ENDPOINT (override table endpoint)
- AZURE_TABLE_CONVERSATIONS (default: Conversations)
- AZURE_TABLE_MESSAGES (default: Messages)
- AZURE_BLOB_CONTAINER (default: chat-messages)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from azure.data.tables import TableClient, TableServiceClient
from azure.data.tables import UpdateMode
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient, ContentSettings

logger = logging.getLogger(__name__)


# ===== Data Models (lightweight helpers) =====


@dataclass
class ConversationRecord:
    user_id: str
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    last_message_preview: str = ""
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_entity(cls, entity: Dict[str, Any]) -> "ConversationRecord":
        return cls(
            user_id=entity["PartitionKey"],
            conversation_id=entity["RowKey"],
            title=entity.get("title", ""),
            created_at=entity.get("created_at", ""),
            updated_at=entity.get("updated_at", entity.get("created_at", "")),
            last_message_preview=entity.get("last_message_preview", ""),
            metadata=json.loads(entity["metadata_json"])
            if entity.get("metadata_json")
            else None,
        )


@dataclass
class MessageRecord:
    conversation_id: str
    message_id: str
    role: str
    created_at: str
    user_id: Optional[str] = None
    content_preview: str = ""
    blob_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    content: Optional[str] = None  # Populated if fetched from blob/snippet

    @classmethod
    def from_entity(cls, entity: Dict[str, Any]) -> "MessageRecord":
        return cls(
            conversation_id=entity["PartitionKey"],
            message_id=entity["RowKey"],
            role=entity.get("role", "assistant"),
            user_id=entity.get("user_id"),
            created_at=entity.get("created_at", ""),
            content_preview=entity.get("content_preview", ""),
            blob_url=entity.get("blob_url"),
            metadata=json.loads(entity["metadata_json"])
            if entity.get("metadata_json")
            else None,
        )


# ===== Storage Client =====


class AzureChatStorage:
    """
    Combined Table + Blob storage for chat conversations.

    - Tables hold indexes and small previews.
    - Blobs hold full message bodies (optional; used when content exceeds a threshold).
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
        table_endpoint: Optional[str] = None,
        credential: Optional[Any] = None,
        conversations_table: Optional[str] = None,
        messages_table: Optional[str] = None,
        blob_container: Optional[str] = None,
        blob_threshold: int = 24000,
        content_preview_chars: int = 2000,
        enable_blob: bool = True,
    ) -> None:
        self.connection_string = connection_string or os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self.account_url = account_url or os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self.table_endpoint = (
            table_endpoint
            or os.getenv("AZURE_TABLE_ENDPOINT")
            or self._default_table_endpoint()
        )
        self.credential = credential or self._build_default_credential()

        self.conversations_table_name = conversations_table or os.getenv(
            "AZURE_TABLE_CONVERSATIONS", "Conversations"
        )
        self.messages_table_name = messages_table or os.getenv(
            "AZURE_TABLE_MESSAGES", "Messages"
        )
        self.blob_container_name = blob_container or os.getenv(
            "AZURE_BLOB_CONTAINER", "chat-messages"
        )
        self.blob_threshold = blob_threshold
        self.content_preview_chars = content_preview_chars
        self.enable_blob = enable_blob

        # Initialize clients
        self.table_service = self._create_table_service_client()
        self.blob_service = (
            self._create_blob_service_client() if self.enable_blob else None
        )

        # Lazy-initialized table clients
        self._conversations_table: Optional[TableClient] = None
        self._messages_table: Optional[TableClient] = None
        self._blob_container_client = None

    # ----- Public API -----

    def ensure_resources(self) -> None:
        """Create required tables and blob container if missing."""
        self._conversations_table = self._get_table_client(
            self.conversations_table_name
        )
        self._messages_table = self._get_table_client(self.messages_table_name)

        if self.blob_service:
            self._blob_container_client = self.blob_service.get_container_client(
                self.blob_container_name
            )
            try:
                self._blob_container_client.create_container()
                logger.info(
                    "Created blob container %s", self.blob_container_name
                )
            except Exception as exc:  # ContainerAlreadyExists is fine
                if "ContainerAlreadyExists" not in str(exc):
                    raise

    def create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationRecord:
        """Create conversation row."""
        conversation_id = conversation_id or str(uuid.uuid4())
        now = self._now_iso()
        entity = {
            "PartitionKey": user_id,
            "RowKey": conversation_id,
            "title": title or "Conversation",
            "created_at": now,
            "updated_at": now,
            "last_message_preview": "",
            "metadata_json": json.dumps(metadata) if metadata else None,
        }
        self._conversations().upsert_entity(entity, mode=UpdateMode.REPLACE)
        return ConversationRecord.from_entity(entity)

    def upsert_conversation_preview(
        self,
        user_id: str,
        conversation_id: str,
        last_message_preview: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update last message preview/title/metadata."""
        now = self._now_iso()
        entity = {
            "PartitionKey": user_id,
            "RowKey": conversation_id,
            "updated_at": now,
            "last_message_preview": last_message_preview[: self.content_preview_chars],
        }
        if title:
            entity["title"] = title
        if metadata is not None:
            entity["metadata_json"] = json.dumps(metadata)
        self._conversations().upsert_entity(entity, mode=UpdateMode.MERGE)

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageRecord:
        """Store a single message and return its record (without full body)."""
        message_id = message_id or self._new_message_id()
        created_at = self._now_iso()

        blob_url = None
        content_str = content if isinstance(content, str) else json.dumps(content)
        content_preview = content_str[: self.content_preview_chars]

        if self.blob_service and len(content_str) > self.blob_threshold:
            blob_url = self._upload_message_blob(
                conversation_id=conversation_id,
                message_id=message_id,
                content=content_str,
            )

        entity = {
            "PartitionKey": conversation_id,
            "RowKey": message_id,
            "role": role,
            "created_at": created_at,
            "user_id": user_id,
            "content_preview": content_preview,
            "blob_url": blob_url,
            "metadata_json": json.dumps(metadata) if metadata else None,
        }
        self._messages().upsert_entity(entity, mode=UpdateMode.REPLACE)
        return MessageRecord.from_entity(entity)

    def list_conversations(
        self, user_id: str, limit: int = 50
    ) -> List[ConversationRecord]:
        """List conversations for a user (most recent first)."""
        query = f"PartitionKey eq '{user_id}'"
        entities = list(
            self._conversations().query_entities(query, results_per_page=limit)
        )
        # Sort by updated_at desc
        entities.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
        return [ConversationRecord.from_entity(e) for e in entities[:limit]]

    def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> Optional[ConversationRecord]:
        """Fetch a single conversation, or None if not found."""
        try:
            entity = self._conversations().get_entity(
                partition_key=user_id, row_key=conversation_id
            )
            return ConversationRecord.from_entity(entity)
        except ResourceNotFoundError:
            return None

    def list_messages(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> List[MessageRecord]:
        """List messages in a conversation ordered by RowKey (ascending)."""
        query = f"PartitionKey eq '{conversation_id}'"
        entities = list(self._messages().query_entities(query))
        entities.sort(key=lambda e: e["RowKey"])
        if limit:
            entities = entities[-limit:]
        return [MessageRecord.from_entity(e) for e in entities]

    def get_message_body(self, record: MessageRecord) -> Optional[str]:
        """
        Retrieve full message body.

        Returns:
            Full text if available, otherwise None.
        """
        if record.content:
            return record.content
        if record.blob_url:
            content = self._download_blob(record.blob_url)
            record.content = content
            return content
        # Fallback to preview if no blob
        record.content = record.content_preview
        return record.content_preview

    def delete_conversation(
        self, user_id: str, conversation_id: str, delete_blobs: bool = True
    ) -> None:
        """Delete a conversation, its messages, and blobs (optional)."""
        messages = self.list_messages(conversation_id)
        for msg in messages:
            try:
                self._messages().delete_entity(
                    partition_key=conversation_id, row_key=msg.message_id
                )
            except Exception as exc:
                logger.warning(
                    "Failed to delete message %s: %s", msg.message_id, exc
                )
            if delete_blobs and msg.blob_url and self.blob_service:
                try:
                    self._delete_blob(msg.blob_url)
                except Exception as exc:
                    logger.warning("Failed to delete blob %s: %s", msg.blob_url, exc)

        try:
            self._conversations().delete_entity(
                partition_key=user_id, row_key=conversation_id
            )
        except Exception as exc:
            logger.warning("Failed to delete conversation %s: %s", conversation_id, exc)

    # ----- Internal helpers -----

    def _conversations(self) -> TableClient:
        if self._conversations_table is None:
            self._conversations_table = self._get_table_client(
                self.conversations_table_name
            )
        return self._conversations_table

    def _messages(self) -> TableClient:
        if self._messages_table is None:
            self._messages_table = self._get_table_client(self.messages_table_name)
        return self._messages_table

    def _create_table_service_client(self) -> TableServiceClient:
        if self.connection_string:
            return TableServiceClient.from_connection_string(self.connection_string)
        if not self.table_endpoint:
            raise ValueError(
                "Table endpoint is required when connection string is not provided."
            )
        return TableServiceClient(endpoint=self.table_endpoint, credential=self.credential)

    def _create_blob_service_client(self) -> BlobServiceClient:
        if self.connection_string:
            return BlobServiceClient.from_connection_string(self.connection_string)
        if not self.account_url:
            raise ValueError(
                "Account URL is required for blob client when no connection string is set."
            )
        return BlobServiceClient(account_url=self.account_url, credential=self.credential)

    def _get_table_client(self, table_name: str) -> TableClient:
        client = self.table_service.get_table_client(table_name)
        try:
            client.create_table()
            logger.info("Created table %s", table_name)
        except Exception as exc:
            if "TableAlreadyExists" not in str(exc):
                raise
        return client

    def _upload_message_blob(
        self, conversation_id: str, message_id: str, content: str
    ) -> str:
        if not self.blob_service:
            raise RuntimeError("Blob service not configured")
        if self._blob_container_client is None:
            self._blob_container_client = self.blob_service.get_container_client(
                self.blob_container_name
            )
        blob_path = f"messages/{conversation_id}/{message_id}.json"
        blob_client: BlobClient = self._blob_container_client.get_blob_client(blob_path)
        blob_client.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
        return blob_client.url

    def _download_blob(self, blob_url: str) -> str:
        blob_client = self.blob_service.get_blob_client(blob_url)
        downloader = blob_client.download_blob()
        return downloader.readall().decode("utf-8")

    def _delete_blob(self, blob_url: str) -> None:
        blob_client = self.blob_service.get_blob_client(blob_url)
        blob_client.delete_blob(delete_snapshots="include")

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_message_id() -> str:
        # Time-ordered RowKey: 20-digit timestamp + random suffix
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return f"{now_ms:020d}-{uuid.uuid4().hex[:8]}"

    def _default_table_endpoint(self) -> Optional[str]:
        # If account URL provided, derive table endpoint automatically.
        account_url = self.account_url
        if not account_url:
            account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            if account_name:
                account_url = f"https://{account_name}.blob.core.windows.net"
        if account_url and ".blob." in account_url:
            return account_url.replace(".blob.", ".table.")
        return None

    @staticmethod
    def _build_default_credential():
        # If an account key is provided, rely on connection string or key-based auth.
        # DefaultAzureCredential will pick up managed identity / dev credentials.
        if os.getenv("AZURE_STORAGE_ACCOUNT_KEY"):
            return None
        try:
            return DefaultAzureCredential(exclude_interactive_browser_credential=True)
        except Exception:
            return None


__all__ = [
    "AzureChatStorage",
    "ConversationRecord",
    "MessageRecord",
]

