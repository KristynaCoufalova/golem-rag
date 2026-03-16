"""
Local ChromaDB vector store implementation.
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from langchain_core.documents import Document
from langchain_chroma import Chroma

from .vectorstore_interface import VectorStoreInterface


class LocalChromaVectorStore(VectorStoreInterface):
    """
    Local ChromaDB implementation of VectorStoreInterface.
    
    Uses ChromaDB for local storage (development/cache).
    """
    
    def __init__(
        self,
        persist_directory: str,
        embedding_function,
        collection_name: str = "default"
    ):
        """
        Initialize local ChromaDB vector store.
        
        Args:
            persist_directory: Directory where ChromaDB will persist data
            embedding_function: Embedding function (from embeddings.py)
            collection_name: Name of the collection
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        
        # Initialize ChromaDB
        self._vectorstore = Chroma(
            persist_directory=str(self.persist_directory),
            collection_name=collection_name,
            embedding_function=embedding_function
        )
    
    def similarity_search(
        self, 
        query: str, 
        k: int = 4,
        collection: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for similar documents."""
        try:
            # ChromaDB uses 'where' parameter for metadata filtering
            # But only if filter is provided
            if filter:
                results = self._vectorstore.similarity_search(
                    query=query,
                    k=k,
                    where=filter
                )
            else:
                results = self._vectorstore.similarity_search(
                    query=query,
                    k=k
                )
            return results
        except Exception as e:
            print(f"⚠️  Error in similarity_search: {e}")
            return []
    
    def add_documents(
        self, 
        documents: List[Document],
        collection: Optional[str] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add documents to the vector store."""
        if collection and collection != self.collection_name:
            # ChromaDB doesn't support dynamic collection switching easily
            # For now, we'll use the initialized collection
            print(f"⚠️  Warning: Collection '{collection}' requested, but using '{self.collection_name}'")
        
        try:
            if ids:
                result_ids = self._vectorstore.add_documents(
                    documents=documents,
                    ids=ids
                )
            else:
                result_ids = self._vectorstore.add_documents(documents=documents)
            return result_ids
        except Exception as e:
            print(f"⚠️  Error adding documents: {e}")
            return []
    
    def delete(
        self, 
        ids: List[str],
        collection: Optional[str] = None
    ) -> bool:
        """Delete documents by IDs."""
        try:
            self._vectorstore.delete(ids=ids)
            return True
        except Exception as e:
            print(f"⚠️  Error deleting documents: {e}")
            return False
    
    def delete_by_metadata(
        self, 
        metadata_filter: Dict[str, Any],
        collection: Optional[str] = None
    ) -> int:
        """
        Delete documents by metadata filter.
        
        ChromaDB uses 'where' clause for filtering.
        """
        try:
            # Get all documents matching the filter
            # ChromaDB doesn't have direct delete_by_metadata, so we need to:
            # 1. Query with filter to get IDs
            # 2. Delete those IDs
            
            # For ChromaDB, we'll use get() with where filter
            # Note: This is a workaround - ChromaDB's get() with where might not work perfectly
            # Better approach: query with empty string and filter, then delete results
            
            # Get documents matching filter
            results = self._vectorstore.get(where=metadata_filter)
            
            if results and 'ids' in results:
                ids_to_delete = results['ids']
                if ids_to_delete:
                    self._vectorstore.delete(ids=ids_to_delete)
                    return len(ids_to_delete)
            
            return 0
        except Exception as e:
            print(f"⚠️  Error deleting by metadata: {e}")
            # Fallback: try to delete by individual metadata keys
            try:
                # ChromaDB supports where clauses with specific keys
                # Try to build a proper where clause
                where_clause = {}
                for key, value in metadata_filter.items():
                    if key in ['path', 'repo', 'branch', 'collection', 'embedding_version']:
                        where_clause[key] = value
                
                if where_clause:
                    results = self._vectorstore.get(where=where_clause)
                    if results and 'ids' in results:
                        ids_to_delete = results['ids']
                        if ids_to_delete:
                            self._vectorstore.delete(ids=ids_to_delete)
                            return len(ids_to_delete)
            except Exception as e2:
                print(f"⚠️  Fallback delete_by_metadata also failed: {e2}")
            
            return 0
    
    def get_collection_info(
        self, 
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            # ChromaDB collection info
            collection = self._vectorstore._collection
            count = collection.count()
            
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": str(self.persist_directory),
                "provider": "chroma"
            }
        except Exception as e:
            print(f"⚠️  Error getting collection info: {e}")
            return {
                "collection_name": self.collection_name,
                "document_count": 0,
                "error": str(e)
            }
    
    def collection_exists(
        self,
        collection: Optional[str] = None
    ) -> bool:
        """Check if collection exists."""
        try:
            # ChromaDB collections exist if persist_directory exists
            # and collection can be accessed
            info = self.get_collection_info(collection)
            return info.get("document_count", 0) >= 0  # Even if 0, collection exists
        except Exception:
            return False
    
    def get_existing_document_ids(
        self,
        metadata_filter: Dict[str, Any],
        collection: Optional[str] = None
    ) -> set:
        """
        Get document IDs that match the metadata filter.
        
        Uses ChromaDB's get() method with where clause.
        """
        try:
            # Build where clause for ChromaDB
            where_clause = {}
            for key, value in metadata_filter.items():
                where_clause[key] = value
            
            if not where_clause:
                return set()
            
            # Get documents matching the filter
            results = self._vectorstore.get(where=where_clause)
            
            if results and 'ids' in results:
                return set(results['ids'])
            
            return set()
        except Exception as e:
            # If get() with where doesn't work, try alternative approach
            try:
                # Use similarity_search with very specific filter
                # This is less efficient but works as fallback
                results = self._vectorstore.similarity_search(
                    query="",  # Empty query
                    k=10000,
                    where=where_clause
                )
                # Extract IDs if available in metadata
                ids = set()
                for doc in results:
                    if hasattr(doc, 'metadata') and 'id' in doc.metadata:
                        ids.add(doc.metadata['id'])
                return ids
            except Exception:
                return set()