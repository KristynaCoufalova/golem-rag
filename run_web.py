#!/usr/bin/env python3
"""
Start the web app for local dev or Azure App Service.
You don't set a port on Azure — the platform sets PORT and we use it.
Local default: 8000.
"""
import os
import sys

def main():
    port = int(os.environ.get("PORT", "8000"))
    import uvicorn
    # Run from repo root so 'rag' package is found
    uvicorn.run(
        "rag.web_app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

if __name__ == "__main__":
    main()
