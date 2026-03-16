#!/usr/bin/env python3
"""
Simple CLI client for FemCAD RAG Assistant.
Hits the web server API instead of loading embeddings directly.

Usage:
    # Start server in one terminal:
    uvicorn backend.rag.web_app:app --host 127.0.0.1 --port 8000

    # Use CLI in another terminal:
    python -m backend.rag.ask_cli "How do I create a beam?"
    python -m backend.rag.ask_cli "What is a GBlock?"
    python -m backend.rag.ask_cli  # Interactive mode (prompts for question)
"""

import sys
import json
import requests

API_URL = "http://127.0.0.1:8000/api/query"


def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Question: ").strip()

    if not question:
        print("No question given.")
        return 1

    payload = {"question": question}

    print(f"❓ {question}")
    
    try:
        resp = requests.post(API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server.")
        print("   Make sure the server is running:")
        print("   uvicorn backend.rag.web_app:app --host 127.0.0.1 --port 8000")
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if e.response.status_code == 503:
            print("   Server is not ready yet. Try again in a moment.")
        elif e.response.status_code == 500:
            try:
                error_detail = e.response.json().get("detail", str(e))
                print(f"   Server error: {error_detail}")
            except:
                print(f"   Server error: {e.response.text}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    print("\n💡 ANSWER\n")
    print(data["answer"])
    print(f"\n⏱️  Latency: {data['latency_ms']:.0f} ms ({data['mode']})")
    print(f"🧠 Session ID: {data['session_id']}")
    
    # Optionally show sources if available
    if data.get("sources") and len(data["sources"]) > 0:
        print(f"\n📚 Sources: {len(data['sources'])} retrieved")
        for i, source in enumerate(data["sources"][:3], 1):  # Show first 3
            source_type = source.get("source_type", "unknown")
            title = source.get("title", "unknown")
            print(f"   {i}. [{source_type}] {title}")

    return 0


if __name__ == "__main__":
    exit(main())

