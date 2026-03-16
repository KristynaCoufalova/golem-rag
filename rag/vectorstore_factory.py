"""
Factory for creating vector stores (local or cloud).

This factory creates the appropriate vector store implementation
based on configuration (local ChromaDB or cloud Qdrant/pgvector).
"""

import os
from typing import Optional
from pathlib import Path

from .vectorstore_interface import VectorStoreInterface
from .local_vectorstore import LocalChromaVectorStore
from .cloud_vectorstore import CloudVectorStore
from .embeddings import get_embeddings


def create_vectorstore(
    mode: str = None,
    provider: str = None,
    collection_name: str = "default",
    persist_directory: Optional[str] = None,
    embedding_function=None,
    **kwargs
) -> VectorStoreInterface:
    """
    Create a vector store instance based on configuration.
    
    Args:
        mode: "local" or "cloud" (defaults to VECTOR_DB_MODE env var)
        provider: "chroma", "qdrant", or "pgvector" (defaults to VECTOR_DB_PROVIDER env var)
        collection_name: Name of the collection/namespace
        persist_directory: Directory for local storage (required for local mode)
        embedding_function: Embedding function (if None, will be loaded)
        **kwargs: Provider-specific configuration
            For Qdrant: url, api_key, location
            For pgvector: connection_string, table_name
    
    Returns:
        VectorStoreInterface instance
    
    Examples:
        # Local ChromaDB
        store = create_vectorstore(
            mode="local",
            collection_name="femcad-code",
            persist_directory="./vectordb_code"
        )
        
        # Cloud Qdrant
        store = create_vectorstore(
            mode="cloud",
            provider="qdrant",
            collection_name="femcad-code",
            url="https://your-cluster.qdrant.io",
            api_key="your-api-key"
        )
        
        # Cloud pgvector
        store = create_vectorstore(
            mode="cloud",
            provider="pgvector",
            collection_name="femcad-code",
            connection_string="postgresql://..."
        )
    """
    # Get defaults from environment
    if mode is None:
        mode = os.getenv("VECTOR_DB_MODE", "local").lower()
    
    if provider is None:
        provider = os.getenv("VECTOR_DB_PROVIDER", "chroma").lower()
    
    # Load embedding function if not provided
    if embedding_function is None:
        embedding_function = get_embeddings()
    
    # Create appropriate vector store
    if mode == "local":
        if persist_directory is None:
            # Default persist directory
            project_root = Path(__file__).parent.parent.parent
            persist_directory = str(project_root / f"vectordb_{collection_name}")
        
        return LocalChromaVectorStore(
            persist_directory=persist_directory,
            embedding_function=embedding_function,
            collection_name=collection_name
        )
    
    elif mode == "cloud":
        if provider == "qdrant":
            # Qdrant configuration
            url = kwargs.get("url") or os.getenv("QDRANT_URL")
            api_key = kwargs.get("api_key") or os.getenv("QDRANT_API_KEY")
            location = kwargs.get("location")  # For local Qdrant
            
            if not (url and api_key) and not location:
                raise ValueError(
                    "Qdrant requires either (url + api_key) or location. "
                    "Set QDRANT_URL and QDRANT_API_KEY environment variables."
                )
            
            return CloudVectorStore(
                provider="qdrant",
                collection_name=collection_name,
                embedding_function=embedding_function,
                url=url,
                api_key=api_key,
                location=location
            )
        
        elif provider == "pgvector":
            # pgvector configuration
            connection_string = kwargs.get("connection_string") or os.getenv("PGVECTOR_CONNECTION_STRING")
            table_name = kwargs.get("table_name", "embeddings")
            
            if not connection_string:
                raise ValueError(
                    "pgvector requires connection_string. "
                    "Set PGVECTOR_CONNECTION_STRING environment variable."
                )
            
            return CloudVectorStore(
                provider="pgvector",
                collection_name=collection_name,
                embedding_function=embedding_function,
                connection_string=connection_string,
                table_name=table_name
            )
        
        else:
            raise ValueError(f"Unsupported cloud provider: {provider}")
    
    else:
        raise ValueError(f"Unsupported mode: {mode}. Use 'local' or 'cloud'.")


def get_vectorstore_for_collection(
    collection_name: str,
    mode: Optional[str] = None
) -> VectorStoreInterface:
    """
    Get vector store for a specific collection.
    
    This is a convenience function that uses environment variables
    and collection-specific defaults.
    
    Args:
        collection_name: Collection name (e.g., "femcad-code", "femcad-docs")
        mode: Override mode (optional)
    
    Returns:
        VectorStoreInterface instance
    """
    # Collection-specific persist directories
    project_root = Path(__file__).parent.parent.parent
    
    if collection_name == "femcad-code" or collection_name == "code_rag":
        persist_directory = os.getenv("FEMCAD_CODE_DB", str(project_root / "vectordb_code"))
    elif collection_name == "femcad-docs" or collection_name == "docs_rag":
        persist_directory = os.getenv("FEMCAD_DOCS_DB", str(project_root / "vectordb_docs"))
    else:
        persist_directory = str(project_root / f"vectordb_{collection_name}")
    
    return create_vectorstore(
        mode=mode,
        collection_name=collection_name,
        persist_directory=persist_directory
    )
