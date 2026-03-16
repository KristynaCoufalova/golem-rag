# Complete Testing Guide

## Step 1: Verify Environment Setup

Make sure your `.env` file has all required variables:

```bash
# Check your .env file
cat femcad-copilot/backend/rag/.env | grep -E "(OIDC|AZURE|TEST_)"
```

Required variables:
- ✅ `AUTH_OIDC_AUTHORITY=https://idd.histruct.com`
- ✅ `AUTH_OIDC_CLIENT_ID=histruct-golem-localhost`
- ✅ `AZURE_STORAGE_CONNECTION_STRING=...` (your Azure connection string)
- ✅ `TEST_OIDC_EMAIL=tynecka.c@seznam.cz`
- ✅ `TEST_OIDC_PASSWORD=Golem123`

## Step 2: Install Dependencies

```bash
cd femcad-copilot/backend
pip install -r requirements.txt

# Install Playwright for automated testing (optional)
pip install playwright
playwright install chromium
```

## Step 3: Start the Backend Server

```bash
cd femcad-copilot/backend/rag
uvicorn web_app:app --reload --host 0.0.0.0 --port 8001
```

You should see:
- ✅ "Azure chat storage ready" (if storage is configured)
- ✅ "FemCAD enhanced RAG ready" or "Local fallback engine ready"
- ✅ Server running on http://127.0.0.1:8001

## Step 4: Get an ID Token

### Option A: Automated (Recommended)
```bash
# In a new terminal
cd femcad-copilot/backend/rag
python get_token_auto.py
```

### Option B: Manual
1. Open browser to: `https://idd.histruct.com/connect/authorize?client_id=histruct-golem-localhost&redirect_uri=http://127.0.0.1:8001/callback&response_type=id_token&scope=openid%20profile%20email&response_mode=fragment`
2. Log in
3. Copy `id_token` from the redirect URL

## Step 5: Test the API

### Test 1: Health Check (No Auth Required)
```bash
curl http://127.0.0.1:8001/api/health
```

Expected: `{"ready": true, "mode": "enhanced"}`

### Test 2: Query with Authentication
```bash
export ID_TOKEN="<your-token-here>"

curl -X POST http://127.0.0.1:8001/api/query \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a beam?", "session_id": ""}'
```

Expected:
- Status 200
- Response with `answer`, `conversation_id`, `session_id`
- Check that `conversation_id` is returned

### Test 3: Verify Storage (Check Azure)
```bash
# List conversations
curl -X GET http://127.0.0.1:8001/api/conversations \
  -H "Authorization: Bearer $ID_TOKEN"

# Get messages from a conversation
curl -X GET "http://127.0.0.1:8001/api/conversations/<conversation_id>/messages" \
  -H "Authorization: Bearer $ID_TOKEN"
```

### Test 4: Continue Conversation
```bash
# Use the conversation_id from previous response
curl -X POST http://127.0.0.1:8001/api/query \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me more", "session_id": "<conversation_id>"}'
```

## Step 6: Verify Data in Azure

Check Azure Portal:
1. Go to your Storage Account
2. Check **Tables**: Should see `Conversations` and `Messages` tables
3. Check **Containers**: Should see `chat-messages` container (if large messages stored)

## Troubleshooting

### "Azure chat storage ready" not showing
- Check `AZURE_STORAGE_CONNECTION_STRING` is set correctly
- Verify connection string format

### "401 Unauthorized" errors
- Token expired (get a new one)
- Token format incorrect (should start with `eyJ`)
- Check `AUTH_OIDC_AUTHORITY` matches token issuer

### "503 Service Unavailable"
- Check backend logs for startup errors
- Verify Azure credentials are correct
- Check OIDC authority is reachable

### No conversations saved
- Check backend logs for storage errors
- Verify Azure storage permissions
- Check `user_id` is extracted correctly from token

## Next Steps After Testing

Once everything works:
1. ✅ Frontend integration (send bearer token with requests)
2. ✅ Production deployment (use proper OAuth2 flow)
3. ✅ Error handling improvements
4. ✅ Monitoring/logging setup

