#!/usr/bin/env python3
"""
Simple script to access and display stored chat messages.

Usage:
    python3 access_storage.py [user_id]
    
If user_id is not provided, it will try to extract from a token or list all conversations.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    from storage.azure_chat_storage import AzureChatStorage
except ImportError:
    try:
        from backend.rag.storage.azure_chat_storage import AzureChatStorage
    except ImportError:
        print("❌ Error: Could not import AzureChatStorage")
        print("   Make sure you're running from the correct directory")
        sys.exit(1)


def list_all_conversations(store: AzureChatStorage, user_id: str = None):
    """List all conversations for a user."""
    if not user_id:
        print("⚠️  No user_id provided. Showing all conversations from storage...")
        # For demo, we'd need to query all partitions, which requires direct table access
        print("   Please provide a user_id (from OIDC token 'sub' claim)")
        return
    
    print(f"\n📋 Conversations for user: {user_id}")
    print("=" * 70)
    
    conversations = store.list_conversations(user_id=user_id)
    
    if not conversations:
        print("   No conversations found.")
        return
    
    for i, conv in enumerate(conversations, 1):
        print(f"\n{i}. Conversation: {conv.conversation_id}")
        print(f"   Title: {conv.title}")
        print(f"   Created: {conv.created_at}")
        print(f"   Updated: {conv.updated_at}")
        print(f"   Preview: {conv.last_message_preview[:80]}...")
        
        # Get message count
        messages = store.list_messages(conv.conversation_id)
        print(f"   Messages: {len(messages)}")
        
        if messages:
            print(f"   First message preview: {messages[0].content_preview[:60]}...")


def show_conversation_details(store: AzureChatStorage, conversation_id: str, full: bool = False):
    """Show detailed messages from a conversation."""
    print(f"\n💬 Messages in conversation: {conversation_id}")
    print("=" * 70)
    
    messages = store.list_messages(conversation_id=conversation_id)
    
    if not messages:
        print("   No messages found.")
        return
    
    for i, msg in enumerate(messages, 1):
        role_emoji = "👤" if msg.role == "user" else "🤖"
        print(f"\n{i}. {role_emoji} {msg.role.upper()} ({msg.created_at})")
        print(f"   ID: {msg.message_id}")
        
        if full:
            content = store.get_message_body(msg)
            print(f"   Content:\n   {content}")
        else:
            print(f"   Preview: {msg.content_preview}")
            if msg.blob_url:
                print(f"   📎 Full content stored in blob: {msg.blob_url}")


def main():
    """Main entry point."""
    print("🔍 Azure Chat Storage Access")
    print("=" * 70)
    
    # Initialize storage
    try:
        store = AzureChatStorage()
        store.ensure_resources()
        print("✅ Connected to Azure storage")
    except Exception as e:
        print(f"❌ Error connecting to storage: {e}")
        print("\n💡 Check your AZURE_STORAGE_CONNECTION_STRING in .env")
        sys.exit(1)
    
    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        # Check if it's a conversation_id (UUID format) or user_id
        if len(arg) > 20:  # Likely a conversation_id (UUID)
            show_conversation_details(store, arg, full=("--full" in sys.argv))
        else:
            # User ID
            list_all_conversations(store, arg)
            if len(sys.argv) > 2:
                # Also show specific conversation
                conv_id = sys.argv[2]
                show_conversation_details(store, conv_id, full=("--full" in sys.argv))
    else:
        print("\nUsage:")
        print("  python3 access_storage.py <user_id>                    # List conversations")
        print("  python3 access_storage.py <user_id> <conversation_id>  # Show messages")
        print("  python3 access_storage.py <conversation_id> --full    # Show full messages")
        print("\nExample:")
        print("  python3 access_storage.py user-123")
        print("  python3 access_storage.py user-123 conv-uuid-456")
        print("  python3 access_storage.py conv-uuid-456 --full")
        print("\n💡 Get user_id from OIDC token 'sub' claim")
        print("   Get conversation_id from API responses or Azure Portal")


if __name__ == "__main__":
    main()
