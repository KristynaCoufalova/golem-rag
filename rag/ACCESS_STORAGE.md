# How to Access Stored Chat Messages

## Method 1: API Endpoints (Recommended)

### Prerequisites
You need a valid OIDC token. Get one using:
```bash
python3 get_token_manual.py
# Or use get_token_simple.py for fragment mode
```

### 1. List All Conversations

Get all conversations for the authenticated user:

```bash
export ID_TOKEN="<your-token-here>"

curl -X GET http://127.0.0.1:8000/api/conversations \
  -H "Authorization: Bearer $ID_TOKEN"
```

**Response:**
```json
[
  {
    "conversation_id": "uuid-here",
    "title": "Conversation",
    "created_at": "2026-01-13T12:00:00Z",
    "updated_at": "2026-01-13T12:05:00Z",
    "last_message_preview": "Hello, how can I help...",
    "metadata": {}
  }
]
```

### 2. Get Messages from a Conversation

Get messages with previews only (fast):
```bash
curl -X GET "http://127.0.0.1:8000/api/conversations/<conversation_id>/messages" \
  -H "Authorization: Bearer $ID_TOKEN"
```

Get full message bodies (slower, includes blob content):
```bash
curl -X GET "http://127.0.0.1:8000/api/conversations/<conversation_id>/messages?full=true" \
  -H "Authorization: Bearer $ID_TOKEN"
```

Limit number of messages:
```bash
curl -X GET "http://127.0.0.1:8000/api/conversations/<conversation_id>/messages?limit=10&full=true" \
  -H "Authorization: Bearer $ID_TOKEN"
```

**Response:**
```json
[
  {
    "message_id": "timestamp-uuid",
    "role": "user",
    "created_at": "2026-01-13T12:00:00Z",
    "content_preview": "Hello, what is...",
    "content": "Hello, what is a beam?",  // Only if full=true
    "metadata": {}
  },
  {
    "message_id": "timestamp-uuid",
    "role": "assistant",
    "created_at": "2026-01-13T12:00:01Z",
    "content_preview": "A beam is a structural...",
    "content": "A beam is a structural element...",  // Only if full=true
    "metadata": {}
  }
]
```

### 3. Delete a Conversation

```bash
curl -X DELETE "http://127.0.0.1:8000/api/conversations/<conversation_id>" \
  -H "Authorization: Bearer $ID_TOKEN"
```

---

## Method 2: Azure Portal (Visual Interface)

### Access via Web Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Storage Account (`golemchathistory`)
3. **For Conversations:**
   - Click on **Tables** in the left menu
   - Open the `Conversations` table
   - Browse rows (PartitionKey = user_id, RowKey = conversation_id)

4. **For Messages:**
   - Click on **Tables** → `Messages` table
   - Filter by PartitionKey (conversation_id) to see messages for a conversation
   - RowKey contains time-ordered message IDs

5. **For Large Message Bodies:**
   - Click on **Containers** → `chat-messages`
   - Navigate to `messages/{conversation_id}/{message_id}.json`
   - Download/view JSON files

### Query Examples in Portal

- Filter conversations by user: `PartitionKey eq 'user-123'`
- Filter messages by conversation: `PartitionKey eq 'conversation-uuid'`
- Sort by timestamp: Use RowKey (it's time-ordered)

---

## Method 3: Azure Storage Explorer (Desktop App)

1. Download [Azure Storage Explorer](https://azure.microsoft.com/features/storage-explorer/)
2. Connect using your connection string:
   - Right-click "Storage Accounts" → "Connect to Azure Storage"
   - Select "Connection String"
   - Paste your `AZURE_STORAGE_CONNECTION_STRING`

3. Browse:
   - **Tables**: `Conversations` and `Messages`
   - **Blob Containers**: `chat-messages`

---

## Method 4: Python Script (Programmatic Access)

Create a script to access storage directly:

```python
from backend.rag.storage.azure_chat_storage import AzureChatStorage
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize storage
store = AzureChatStorage()
store.ensure_resources()

# List conversations for a user
user_id = "user-123"  # From OIDC token 'sub' claim
conversations = store.list_conversations(user_id=user_id)

for conv in conversations:
    print(f"Conversation: {conv.conversation_id}")
    print(f"  Title: {conv.title}")
    print(f"  Updated: {conv.updated_at}")
    print(f"  Preview: {conv.last_message_preview[:50]}...")
    
    # Get messages
    messages = store.list_messages(conv.conversation_id)
    print(f"  Messages: {len(messages)}")
    
    # Get full message body
    if messages:
        full_content = store.get_message_body(messages[0])
        print(f"  First message: {full_content[:100]}...")
    print()
```

Save as `access_storage.py` and run:
```bash
cd femcad-copilot/backend/rag
python3 access_storage.py
```

---

## Method 5: Azure CLI

```bash
# Install Azure CLI if needed
# brew install azure-cli  # macOS
# az login

# List tables
az storage table list \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# Query conversations
az storage entity query \
  --table-name Conversations \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
  --filter "PartitionKey eq 'user-123'"

# Query messages
az storage entity query \
  --table-name Messages \
  --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
  --filter "PartitionKey eq 'conversation-uuid'"
```

---

## Method 6: Direct Database Query (Advanced)

If you need to query across users or do complex analysis:

```python
from azure.data.tables import TableServiceClient
import os

connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
service = TableServiceClient.from_connection_string(connection_string)

# Get table client
conversations_table = service.get_table_client("Conversations")

# Query all conversations (across all users)
entities = conversations_table.query_entities("")
for entity in entities:
    print(f"User: {entity['PartitionKey']}, Conversation: {entity['RowKey']}")
    print(f"  Title: {entity.get('title', 'N/A')}")
    print(f"  Updated: {entity.get('updated_at', 'N/A')}")
```

---

## Quick Reference

### API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/conversations` | GET | List all conversations for user |
| `/api/conversations/{id}/messages` | GET | Get messages (add `?full=true` for full content) |
| `/api/conversations/{id}` | DELETE | Delete conversation |

### Storage Structure

**Table: Conversations**
- PartitionKey: `user_id` (from OIDC token `sub`)
- RowKey: `conversation_id` (UUID)
- Columns: `title`, `created_at`, `updated_at`, `last_message_preview`, `metadata_json`

**Table: Messages**
- PartitionKey: `conversation_id`
- RowKey: `message_id` (time-ordered: timestamp-uuid)
- Columns: `role`, `user_id`, `content_preview`, `blob_url`, `created_at`, `metadata_json`

**Blob Container: chat-messages**
- Path: `messages/{conversation_id}/{message_id}.json`
- Contains full message content when >24KB

---

## Troubleshooting

### "401 Unauthorized"
- Token expired or invalid
- Get a new token: `python3 get_token_manual.py`

### "404 Not Found"
- Conversation doesn't exist
- Wrong `conversation_id`
- User doesn't own this conversation (security check)

### "503 Service Unavailable"
- Azure storage not configured
- Check `AZURE_STORAGE_CONNECTION_STRING` in `.env`
- Check server logs for initialization errors

### Empty Results
- No conversations yet (make some queries first!)
- Wrong `user_id` (check token `sub` claim)
