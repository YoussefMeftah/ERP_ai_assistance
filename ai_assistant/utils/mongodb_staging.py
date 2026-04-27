"""
MongoDB integration for staging large API results.

When API results exceed a threshold (default 50 records), save to MongoDB
for more efficient filtering and querying.
"""

from typing import Any, Dict, List, Optional
from config import config


class MongoDBStaging:
    """Handle MongoDB staging for large result sets."""
    
    def __init__(self):
        """Initialize MongoDB client if configured."""
        self.uri = config.mongodb_uri()
        self.db_name = config.mongodb_db_name()
        self.threshold = config.mongodb_staging_threshold()
        self.client = None
        self.db = None
        
        if self.uri:
            self._connect()
    
    def _connect(self) -> None:
        """Connect to MongoDB."""
        try:
            from pymongo import MongoClient
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.db_name]
            # Test connection
            self.db.command("ping")
        except Exception as e:
            print(f"Warning: Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
    
    def should_stage(self, record_count: int) -> bool:
        """Check if results should be staged to MongoDB.
        
        Args:
            record_count: Number of records in result set
        
        Returns:
            True if record_count >= threshold and MongoDB is available
        """
        return self.uri is not None and record_count >= self.threshold
    
    def stage_results(
        self,
        collection_name: str,
        records: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
    ) -> Optional[str]:
        """Stage records to MongoDB collection.
        
        Args:
            collection_name: MongoDB collection name
            records: List of record dicts to insert
            metadata: Optional metadata (timestamps, source, etc.)
        
        Returns:
            Collection name if successful, None if MongoDB unavailable
        """
        if not self.db:
            return None
        
        try:
            collection = self.db[collection_name]
            
            # Add metadata to each record
            if metadata:
                for record in records:
                    for key, value in metadata.items():
                        if key not in record:
                            record[key] = value
            
            # Insert records
            if records:
                collection.insert_many(records)
            
            # Create TTL index (expire after 24 hours)
            if "_created_at" in (metadata or {}) or "createdAt" in str(records[0]) if records else False:
                collection.create_index("_created_at", expireAfterSeconds=86400)
            
            return collection_name
        except Exception as e:
            print(f"Warning: Failed to stage results to MongoDB: {e}")
            return None
    
    def close(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()


# Global instance (lazy initialization)
_mongodb_staging_instance = None


def _get_mongodb_staging():
    """Lazily initialize MongoDB staging instance.
    
    This allows environment variables to be set before connection is attempted.
    """
    global _mongodb_staging_instance
    if _mongodb_staging_instance is None:
        _mongodb_staging_instance = MongoDBStaging()
    return _mongodb_staging_instance


def get_mongodb_staging():
    """Get MongoDB staging instance for large result sets.
    
    Returns:
        MongoDBStaging instance (lazily initialized)
    """
    return _get_mongodb_staging()


def connect_mongodb():
    """Get MongoDB database connection for NoSQL queries.
    
    Returns:
        MongoDB database object if available, None otherwise
    """
    staging = _get_mongodb_staging()
    return staging.db
