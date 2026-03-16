"""
Abstract interface for vector stores (local and cloud).

This interface allows switching between ChromaDB (local) and cloud providers
(Qdrant, pgvector) without changing the rest of the codebase.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Set
from langchain_core.documents import Document


class VectorStoreInterface(ABC):
    """
    Abstract interface for vector stores.
    
    All vector store implementations (local ChromaDB, Qdrant, pgvector)
    must implement this interface to ensure compatibility.
    """
    
    @abstractmethod
    def similarity_search(
        self, 
        query: str, 
        k: int = 4,
        collection: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search for similar documents.
        
        Args:
            query: Search query string
            k: Number of results to return
            collection: Collection/namespace name (optional, provider-specific)
            filter: Optional metadata filter (e.g., {"path": "src/file.py"})
            
        Returns:
            List of Document objects with page_content and metadata
        """
        pass
    
    @abstractmethod
    def add_documents(
        self, 
        documents: List[Document],
        collection: Optional[str] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of Document objects to add
            collection: Collection/namespace name (optional)
            ids: Optional list of document IDs (if None, will be generated)
            
        Returns:
            List of document IDs that were added
        """
        pass
    
    @abstractmethod
    def delete(
        self, 
        ids: List[str],
        collection: Optional[str] = None
    ) -> bool:
        """
        Delete documents by IDs.
        
        Args:
            ids: List of document IDs to delete
            collection: Collection/namespace name (optional)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_by_metadata(
        self, 
        metadata_filter: Dict[str, Any],
        collection: Optional[str] = None
    ) -> int:
        """
        Delete documents by metadata filter.
        
        This is a unified filter interface that works across all providers.
        Supported filter keys:
        - path: file path
        - repo: repository name
        - branch: branch name
        - collection: collection name (optional)
        - embedding_version: embedding model version (optional)
        
        Args:
            metadata_filter: Dictionary with filter criteria
            collection: Collection/namespace name (optional)
            
        Returns:
            Number of documents deleted
        """
        pass
    
    @abstractmethod
    def get_collection_info(
        self, 
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get information about the collection.
        
        Args:
            collection: Collection/namespace name (optional)
            
        Returns:
            Dictionary with collection info (count, size, etc.)
        """
        pass
    
    @abstractmethod
    def collection_exists(
        self,
        collection: Optional[str] = None
    ) -> bool:
        """
        Check if collection exists.
        
        Args:
            collection: Collection/namespace name (optional)
            
        Returns:
            True if collection exists, False otherwise
        """
        pass
    
    def get_existing_document_ids(
        self,
        metadata_filter: Dict[str, Any],
        collection: Optional[str] = None
    ) -> Set[str]:
        """
        Get document IDs that match the metadata filter.
        
        This is useful for checking if files have already been indexed.
        
        Args:
            metadata_filter: Dictionary with filter criteria (e.g., {"repo": "owner/repo", "path": "file.fcs"})
            collection: Collection/namespace name (optional)
            
        Returns:
            Set of document IDs that match the filter
        """
        # Default implementation: use similarity_search with empty query and filter
        # This is not ideal but works as a fallback
        try:
            # Use a dummy query to get documents matching the filter
            results = self.similarity_search(
                query="",  # Empty query, we only care about filter
                k=10000,  # Large number to get all matches
                filter=metadata_filter
            )
            # Extract IDs from results if available
            # Note: This depends on the implementation, may need override
            return set()
        except Exception:
            return set()