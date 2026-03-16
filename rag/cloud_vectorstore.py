"""
Cloud vector store implementations (Qdrant, pgvector).

This module provides cloud-based vector store implementations.
Currently supports Qdrant and pgvector (Supabase).
"""

from typing import List, Optional, Dict, Any, Set
from langchain_core.documents import Document

from .vectorstore_interface import VectorStoreInterface


class CloudVectorStore(VectorStoreInterface):
    """
    Cloud vector store implementation.
    
    Supports Qdrant and pgvector (Supabase) providers.
    """
    
    def __init__(
        self,
        provider: str,
        collection_name: str,
        embedding_function,
        **kwargs
    ):
        """
        Initialize cloud vector store.
        
        Args:
            provider: "qdrant" or "pgvector"
            collection_name: Name of the collection
            embedding_function: Embedding function
            **kwargs: Provider-specific configuration
                For Qdrant: url, api_key, location, etc.
                For pgvector: connection_string, table_name, etc.
        """
        self.provider = provider.lower()
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self.kwargs = kwargs
        
        # Initialize provider-specific vector store
        self._vectorstore = self._init_provider()
    
    def _init_provider(self):
        """Initialize provider-specific vector store."""
        if self.provider == "qdrant":
            return self._init_qdrant()
        elif self.provider == "pgvector":
            return self._init_pgvector()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _init_qdrant(self):
        """Initialize Qdrant vector store."""
        try:
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client import QdrantClient
            
            # Qdrant configuration
            url = self.kwargs.get("url")
            api_key = self.kwargs.get("api_key")
            location = self.kwargs.get("location")  # For local Qdrant
            
            if url and api_key:
                # Cloud Qdrant
                client = QdrantClient(url=url, api_key=api_key)
            elif location:
                # Local Qdrant
                client = QdrantClient(path=location)
            else:
                raise ValueError("Qdrant requires either (url + api_key) or location")
            
            return QdrantVectorStore(
                client=client,
                collection_name=self.collection_name,
                embedding=self.embedding_function
            )
        except ImportError:
            raise ImportError(
                "Qdrant dependencies not installed. "
                "Install with: pip install langchain-qdrant qdrant-client"
            )
    
    def _init_pgvector(self):
        """Initialize pgvector (Supabase) vector store."""
        try:
            from langchain_postgres import PGVector
            
            # pgvector configuration
            connection_string = self.kwargs.get("connection_string")
            table_name = self.kwargs.get("table_name", "embeddings")
            
            if not connection_string:
                raise ValueError("pgvector requires connection_string")
            
            return PGVector(
                embeddings=self.embedding_function,
                connection=connection_string,
                collection_name=self.collection_name
            )
        except ImportError:
            raise ImportError(
                "pgvector dependencies not installed. "
                "Install with: pip install langchain-postgres psycopg2-binary"
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
            # Provider-specific filter handling
            if self.provider == "qdrant":
                # Qdrant uses filter parameter
                results = self._vectorstore.similarity_search(
                    query=query,
                    k=k,
                    filter=filter
                )
            elif self.provider == "pgvector":
                # pgvector uses metadata filter
                results = self._vectorstore.similarity_search_with_score(
                    query=query,
                    k=k,
                    filter=filter
                )
                # Extract documents from (doc, score) tuples
                results = [doc for doc, score in results]
            else:
                results = self._vectorstore.similarity_search(query=query, k=k)
            
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
        
        Provider-specific implementation.
        """
        try:
            if self.provider == "qdrant":
                # Qdrant: use delete with filter
                # Note: Qdrant filter syntax is different
                # We'll need to convert our filter to Qdrant format
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                
                # Build Qdrant filter
                conditions = []
                for key, value in metadata_filter.items():
                    if key in ['path', 'repo', 'branch', 'collection', 'embedding_version']:
                        conditions.append(
                            FieldCondition(
                                key=f"metadata.{key}",
                                match=MatchValue(value=value)
                            )
                        )
                
                if conditions:
                    qdrant_filter = Filter(must=conditions)
                    # Qdrant delete with filter
                    # Note: This might need adjustment based on Qdrant API
                    deleted = self._vectorstore._collection.delete(
                        points_selector=qdrant_filter
                    )
                    return deleted.operation_id if hasattr(deleted, 'operation_id') else 0
                
            elif self.provider == "pgvector":
                # pgvector: use SQL DELETE with WHERE clause
                # This requires direct SQL access
                # For now, we'll query first, then delete by IDs
                results = self._vectorstore.similarity_search(
                    query="",  # Empty query, just filtering
                    k=10000,  # Large number to get all matches
                    filter=metadata_filter
                )
                # Extract IDs from results and delete
                # Note: This is a workaround - proper implementation needs SQL access
                # For now, return 0 and log warning
                print("⚠️  pgvector delete_by_metadata requires SQL access - not fully implemented")
                return 0
            
            return 0
        except Exception as e:
            print(f"⚠️  Error deleting by metadata: {e}")
            return 0
    
    def get_collection_info(
        self, 
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            if self.provider == "qdrant":
                collection_info = self._vectorstore._collection.get_collection()
                return {
                    "collection_name": self.collection_name,
                    "document_count": collection_info.points_count,
                    "provider": "qdrant"
                }
            elif self.provider == "pgvector":
                # pgvector: query count from database
                # For now, return basic info
                return {
                    "collection_name": self.collection_name,
                    "document_count": "unknown",  # Requires SQL query
                    "provider": "pgvector"
                }
            else:
                return {
                    "collection_name": self.collection_name,
                    "provider": self.provider
                }
        except Exception as e:
            print(f"⚠️  Error getting collection info: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }
    
    def collection_exists(
        self,
        collection: Optional[str] = None
    ) -> bool:
        """Check if collection exists."""
        try:
            info = self.get_collection_info(collection)
            return "error" not in info
        except Exception:
            return False
    
    def get_existing_document_ids(
        self,
        metadata_filter: Dict[str, Any],
        collection: Optional[str] = None
    ) -> Set[str]:
        """
        Get document IDs that match the metadata filter.
        
        Provider-specific implementation.
        """
        try:
            if self.provider == "qdrant":
                # Qdrant: use scroll to get all matching documents
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                
                conditions = []
                for key, value in metadata_filter.items():
                    if key in ['path', 'repo', 'branch', 'collection', 'embedding_version']:
                        conditions.append(
                            FieldCondition(
                                key=f"metadata.{key}",
                                match=MatchValue(value=value)
                            )
                        )
                
                if conditions:
                    qdrant_filter = Filter(must=conditions)
                    # Scroll through all matching points
                    results = self._vectorstore._collection.scroll(
                        scroll_filter=qdrant_filter,
                        limit=10000
                    )
                    # Extract IDs
                    ids = set()
                    for point in results[0]:  # results is (points, next_page_offset)
                        if hasattr(point, 'id'):
                            ids.add(str(point.id))
                    return ids
            
            elif self.provider == "pgvector":
                # pgvector: use similarity_search with filter to get matching docs
                # This is less efficient but works
                results = self.similarity_search(
                    query="",  # Empty query, just filtering
                    k=10000,
                    filter=metadata_filter
                )
                # Extract IDs from metadata if available
                ids = set()
                for doc in results:
                    if hasattr(doc, 'metadata') and 'id' in doc.metadata:
                        ids.add(doc.metadata['id'])
                return ids
            
            return set()
        except Exception as e:
            print(f"⚠️  Error getting existing document IDs: {e}")
            return set()