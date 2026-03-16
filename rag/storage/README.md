# Chat Storage (Azure Table + Blob)

This module stores per-user conversations with Azure Table Storage for indexes and Azure Blob Storage for full message bodies.

## Schema
- Table `Conversations`: `PartitionKey=user_id`, `RowKey=conversation_id`, columns: `title`, `created_at`, `updated_at`, `last_message_preview`, `metadata_json`.
- Table `Messages`: `PartitionKey=conversation_id`, `RowKey=message_id` (time-ordered), columns: `role`, `user_id`, `content_preview`, `blob_url`, `created_at`, `metadata_json`.
- Blob container `chat-messages`: `messages/{conversation_id}/{message_id}.json` holds full message content when it exceeds a threshold (24 KB by default).

## Env vars
Preferred single setting:
- `AZURE_STORAGE_CONNECTION_STRING`

Or granular settings:
- `AZURE_STORAGE_ACCOUNT_URL` (e.g., `https://<account>.blob.core.windows.net`)
- `AZURE_STORAGE_ACCOUNT_NAME` + `AZURE_STORAGE_ACCOUNT_KEY` (if not using MSI)
- Optional: `AZURE_TABLE_ENDPOINT` (override table endpoint)
- Optional overrides: `AZURE_TABLE_CONVERSATIONS`, `AZURE_TABLE_MESSAGES`, `AZURE_BLOB_CONTAINER`

## Usage
```python
from backend.rag.storage.azure_chat_storage import AzureChatStorage

store = AzureChatStorage()
store.ensure_resources()  # creates tables + container if missing

conv = store.create_conversation(user_id="user-123", title="Design session")
store.append_message(conv.conversation_id, role="user", content="Hello", user_id="user-123")

messages = store.list_messages(conv.conversation_id)
full_text = store.get_message_body(messages[0])
```

## Notes
- Uses blob storage only when the content exceeds `blob_threshold` (24 KB). Small messages stay in table previews.
- Row keys are time-ordered to keep message retrieval sorted without extra queries.
- Managed identity is supported via `DefaultAzureCredential` when no account key is provided.

