# Authentication Guide

## Quick start: How to log in (FemCAD via HiStruct portal)

1. **Start the app**  
   From `femcad-copilot/backend/rag` run:  
   `uvicorn web_app:app --reload --host 0.0.0.0 --port 8001`

2. **Open the app in your browser**  
   Go to: **http://127.0.0.1:8001**

3. **Click "Login with HiStruct"**  
   Use the login button in the web interface (usually in the header or sidebar).

4. **You are sent to the HiStruct portal**  
   The browser opens HiStruct’s login page (`https://idd.histruct.com` or similar).  
   Sign in with your **HiStruct account** (email and password).  
   You do **not** create a separate “FemCAD” account — HiStruct is the single sign‑on.

5. **You are sent back to the app**  
   After a successful login, HiStruct redirects you to the Copilot (e.g. `http://127.0.0.1:8001/callback`), the app saves the token, then shows the main Copilot page. You are logged in.

6. **Use the Copilot**  
   Ask questions as usual; the app sends your HiStruct token with each request.

**Summary:** FemCAD Copilot uses HiStruct as the identity provider. You always log in on the HiStruct portal; there is no separate “FemCAD login” — just use “Login with HiStruct” in the app and then your HiStruct credentials on the redirect.

---

## Overview

The FemCAD Copilot now includes an integrated authentication interface that allows users to log in through HiStruct's OIDC provider. This replaces the previous manual token retrieval scripts.

## Features

- **Integrated Login**: Click "Login with HiStruct" button in the web UI
- **Automatic Token Management**: Tokens are stored in browser localStorage
- **Token Expiry**: Tokens expire after 24 hours and require re-authentication
- **Seamless Experience**: After login, tokens are automatically included in API requests

## How It Works

### For Users

1. **Login**: Click the "Login with HiStruct" button in the web interface
2. **Redirect**: You'll be redirected to HiStruct's login page
3. **Authenticate**: Enter your HiStruct credentials
4. **Automatic Return**: After successful login, you'll be redirected back to the app
5. **Ready to Use**: The app will automatically use your token for all API requests

### For Developers

#### Backend Endpoints

- **`GET /auth/login`**: Initiates the OIDC login flow by redirecting to the OIDC provider
- **`GET /auth/callback`**: Receives the OIDC callback, stores the token in localStorage, and redirects to the app
- **`GET /auth/logout`**: Clears the stored token and logs out the user

#### Frontend Integration

The frontend automatically:
- Checks for stored tokens on page load
- Includes tokens in API request headers (`Authorization: Bearer <token>`)
- Handles authentication errors (401) by prompting for re-login
- Updates the UI to show "Login" or "Logout" based on authentication state

#### Token Storage

- Tokens are stored in browser `localStorage` with key `histruct_id_token`
- Token timestamp is stored with key `histruct_token_timestamp`
- Tokens expire after 24 hours

## Configuration

The authentication system uses the following environment variables:

- `OIDC_AUTHORITY` or `AUTH_OIDC_AUTHORITY`: OIDC provider URL (default: `https://idd.histruct.com`)
- `OIDC_CLIENT_ID` or `AUTH_OIDC_CLIENT_ID`: Client ID (default: `histruct-golem-localhost`)
- `AUTH_OIDC_CLIENT_URL` or `OIDC_REDIRECT_URI`: Base URL for redirects (default: `http://127.0.0.1:8001`)
- `AUTH_OIDC_REDIRECT_PATH`: Path for the redirect URI (default: `/callback`)
  - Common alternatives: `/callback`, `/signin-oidc`, or empty string for base URL
  - This allows you to match the redirect URI registered with your OIDC provider
- `AUTH_OIDC_RESPONSE_MODE`: Response mode for the OIDC provider (default: `fragment`)

## Migration from Old Scripts

The old token retrieval scripts (`get_token_manual.py`, `get_token_auto.py`, `get_token_simple.py`) are no longer needed. The new integrated interface provides a better user experience:

- **Before**: Run a script, copy token, set environment variable, use in API calls
- **Now**: Click login button, authenticate, use the app

## Troubleshooting

### "Authentication required" Error

If you see this error:
1. Click the "Login with HiStruct" button
2. Complete the login flow
3. Try your request again

### Token Expired

If your token has expired (after 24 hours):
1. Click "Logout" to clear the old token
2. Click "Login with HiStruct" to get a new token

### Redirect URI Errors

If you see "Invalid redirect_uri" or "unauthorized_client" errors:

1. **Check your configuration:**
   - Verify `AUTH_OIDC_CLIENT_URL` matches your actual server URL
   - Check what redirect URI path is registered with HiStruct

2. **Try different redirect paths:**
   - Set `AUTH_OIDC_REDIRECT_PATH=/callback` (common alternative)
   - Set `AUTH_OIDC_REDIRECT_PATH=/signin-oidc` (another common pattern)
   - Set `AUTH_OIDC_REDIRECT_PATH=` (empty, uses base URL only)

3. **Check the logs:**
   - The server logs will show what redirect URI is being used
   - Look for: `OIDC Login: Using redirect_uri=...`

4. **Contact OIDC administrator:**
   - Ask them to register your redirect URI with the client ID
   - Common patterns to request: `http://127.0.0.1:8001/callback`, `http://127.0.0.1:8001/auth/callback`, or `http://localhost:8001/callback`

5. **Alternative callback endpoints:**
   - The app supports both `/auth/callback` and `/callback` endpoints
   - Try using `/callback` if that's what's registered

## Security Notes

- Tokens are stored in browser localStorage (not cookies) for better security
- Tokens expire after 24 hours
- Tokens are only sent over HTTPS in production (ensure your server uses HTTPS)
- The logout endpoint clears tokens from localStorage

## API Usage

When making API calls programmatically, you can still use tokens:

```bash
# Get token from localStorage (in browser console)
localStorage.getItem('histruct_id_token')

# Use in curl
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "session_id": ""}'
```
